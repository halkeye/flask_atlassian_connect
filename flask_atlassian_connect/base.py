import re
from functools import wraps

from atlassian_jwt import Authenticator, encode_token
from flask import abort, current_app, jsonify, request, g
from jwt import decode
from jwt.exceptions import DecodeError
from requests import get
from .client import AtlassianConnectClient

try:
    # python2
    from urllib import urlencode
except ImportError:
    # python3
    from urllib.parse import urlencode


def _relative_to_base(app, path):
    base = app.config.get('BASE_URL', '/')
    path = '/' + path if not path.startswith('/') else path
    return base + path


class _SimpleAuthenticator(Authenticator):
    """Implementation of Authenticator for Atlassian"""
    def __init__(self, addon, *args, **kwargs):
        super(_SimpleAuthenticator, self).__init__(*args, **kwargs)
        self.addon = addon

    def get_shared_secret(self, client_key):
        """ I actually don't fully understand this. Go see atlassian_jwt """
        client = self.addon.client_class.load(client_key)
        if client is None:
            raise Exception('No client for ' + client_key)
        if isinstance(client, dict):
            return client.get('sharedSecret')
        return client.sharedSecret


class AtlassianConnect(object):
    """This class is used to make creating an Atlassian Connect based
    addon a lot simplier and more straight forward. It takes care of all
    the authentication and authorization for you.

    You will need to provide a Client class that
    contains load(id) and save(client) methods.
    """
    def __init__(self, app=None, client_class=AtlassianConnectClient):
        self.app = app
        if app is not None:
            self.init_app(app)
        self.descriptor = {
            "name": app.config.get('ADDON_NAME', ""),
            "description": app.config.get('ADDON_DESCRIPTION', ""),
            "key": app.config.get('ADDON_KEY'),
            "authentication": {"type": "jwt"},
            "scopes": app.config.get('ADDON_SCOPES', ["READ"]),
            "vendor": {
                "name": app.config.get('ADDON_VENDOR_NAME'),
                "url": app.config.get('ADDON_VENDOR_URL')
            },
            "lifecycle": {},
            "links": {
            },
        }
        self.client_class = client_class
        self.auth = _SimpleAuthenticator(addon=self)
        self.sections = {}

    def init_app(self, app):
        """
        Initialize Application object stuff

        :param app:
            App Object
        :type app: :py:class:`flask.Flask`
        """
        app.config.setdefault('BASE_URL', u"http://localhost:5000")
        app.route('/atlassian_connect/descriptor',
                  methods=['GET'])(self._get_descriptor)
        app.route('/atlassian_connect/<section>/<name>',
                  methods=['GET', 'POST'])(self._handler_router)
        app.context_processor(self._atlassian_jwt_post_token)

    def _atlassian_jwt_post_token(self):
        if not getattr(g, 'ac_client', None):
            return dict()

        args = request.args.copy()
        try:
            del args['jwt']
        except KeyError:
            pass

        signature = encode_token(
            'POST',
            request.path + '?' + urlencode(args),
            g.ac_client.clientKey,
            g.ac_client.sharedSecret)
        args['jwt'] = signature
        return dict(atlassian_jwt_post_url=request.path + '?' + urlencode(args))

    def _get_descriptor(self):
        """Output atlassian connector descriptor file"""
        app = self.app or current_app
        self.descriptor["baseUrl"] = _relative_to_base(app, '/')
        self.descriptor["links"]["self"] = _relative_to_base(
            app,
            "/atlassian_connect/descriptor")
        return jsonify(self.descriptor)

    def _handler_router(self, section, name):
        """
        Main Router for Atlassian Connect plugin

        TODO: Rest of params
        """
        method = self.sections.get(section, {}).get(name)
        if method is None:
            (self.app or current_app).logger.error(
                'Invalid handler for %s -- %s' % (section, name))
            print (section, name, self.sections)
            abort(404)
        ret = method()
        if ret is not None:
            return ret
        return '', 204

    @staticmethod
    def _make_path(section, name):
        return "/atlassian_connect/" + "/".join([section, name])

    def _provide_client_handler(self, section, name, kwargs_updator=None):
        def _wrapper(func):
            @wraps(func)
            def _handler(**kwargs):
                client_key = self.auth.authenticate(
                    request.method,
                    request.url,
                    request.headers)
                client = self.client_class.load(client_key)
                if not client:
                    abort(401)
                g.ac_client = client
                kwargs['client'] = client
                if kwargs_updator:
                    kwargs.update(kwargs_updator(**kwargs))

                ret = func(**kwargs)
                if ret is not None:
                    return ret
                return '', 204
            self._add_handler(section, name, _handler)
            return func
        return _wrapper

    def _add_handler(self, section, name, handler):
        self.sections.setdefault(section, {})[name] = handler

    def lifecycle(self, name):
        """
        Lifecycle decorator. See `external lifecycle`_ documentation

        Example::

            @ac.lifecycle("installed")
            def lifecycle_installed(client):
                print "New client installed!!!!"
                print client

        Payload::

            {
                "key": "installed-addon-key",
                "clientKey": "unique-client-identifier",
                "sharedSecret": "a-secret-key-not-to-be-lost",
                "serverVersion": "server-version",
                "pluginsVersion": "version-of-connect",
                "baseUrl": "http://example.atlassian.net",
                "productType": "jira",
                "description": "Atlassian JIRA at https://example.atlassian.net",
                "serviceEntitlementNumber": "SEN-number",
                "eventType": "installed"
            }

        :param name:
            Which atlassian connect lifecycle to handle.

            At time of writing, the following are the only options:
                * installed
                * uninstalled
                * enabled
                * disabled

            Each of the above will call your Client's save and load methods
        :type name: string

        .. _external lifecycle: https://developer.atlassian.com/static/connect/docs/beta/modules/lifecycle.html
        """
        section = "lifecycle"

        self.descriptor.setdefault('lifecycle', {})[
            name] = AtlassianConnect._make_path(section, name)

        def _decorator(func):
            if name == "installed":
                self._add_handler(section, name,
                                  self._installed_wrapper(func))
            else:
                self._add_handler(section, name, func)
            return func
        return _decorator

    def _installed_wrapper(self, func):
        @wraps(func)
        def inner(*args, **kwargs):
            client = self.client_class(**request.get_json())
            response = get(
                client.baseUrl.rstrip('/') +
                '/plugins/servlet/oauth/consumer-info')
            response.raise_for_status()

            key = re.search(r"<key>(.*)</key>", response.text).groups()[0]
            public_key = re.search(
                r"<publicKey>(.*)</publicKey>", response.text
            ).groups()[0]

            if key != client.clientKey or public_key != client.publicKey:
                raise Exception("Invalid Credentials")

            stored_client = self.client_class.load(client.clientKey)
            if stored_client:
                token = request.headers.get('authorization', '').lstrip('JWT ')
                if not token:
                    # Is not first install, but did not sign the request
                    # properly for an update
                    return '', 401
                try:
                    decode(
                        token,
                        stored_client.sharedSecret,
                        options={"verify_aud": False})
                except (ValueError, DecodeError):
                    # Invalid secret, so things did not get installed
                    return '', 401

            self.client_class.save(client)
            kwargs['client'] = client
            return func(*args, **kwargs)
        return inner

    def webhook(self, event, exclude_body=False, **kwargs):
        """
        Webhook decorator. See `external webhooks`_ documentation

        Example::

            @ac.webhook("jira:issue_created")
            def jira_issue_created(client, event):
                print "An issue was just created!"
                print "Take a look at this:"
                print event

        :param event:
            Specifies the named event you would like to listen to
            (e.g., "enabled", "jira:issue_created", etc.)
        :type event: string

        :param exclude_body:
            Specifies if webhook will send JSON body when triggered.
            By default, a webhook will send a request with a JSON body.
        :type event: bool

        :param filter:
            Filter for entities that the webhook will be triggered for.
            Refer to the documentation on filtering_ for details.
        :type event: string

        :param propertyKeys:
            Specifies entity properties which will be returned inside JSON body.
            If not specified no properties will be returned.
        :type event: array

        .. _filtering: https://developer.atlassian.com/static/connect/docs/beta/modules/common/webhook.html#Filtering
        .. _external webhooks: https://developer.atlassian.com/jiradev/jira-apis/webhooks
        """
        section = 'webhook'

        webhook = {
            "event": event,
            "url": AtlassianConnect._make_path(section, event.replace(":", "")),
            "excludeBody": exclude_body
        }
        if kwargs.get('filter'):
            webhook["filter"] = kwargs.pop('filter')
        if kwargs.get('propertyKeys'):
            webhook["propertyKeys"] = kwargs.pop('propertyKeys')

        self.descriptor.setdefault('modules', {}).setdefault(
            'webhooks', []).append(webhook)

        def _wrapper(**kwargs):
            del kwargs
            content = request.get_json(silent=False)
            return {"event": content}

        return self._provide_client_handler(
            section, event.replace(":", ""), kwargs_updator=_wrapper)

    def module(self, key, name=None, location=None):
        """
        Module decorator. See `external modules`_ documentation

        Example::

            @ac.module("configurePage", name="Configure")
            def configure_page(client):
                return '<h1>Configure Page</h1>', 200

        :param key:
            A key to identify this module.

            This key must be unique relative to the add on, with the exception
            of Confluence macros: Their keys need to be globally unique.

            Keys must only contain alphanumeric characters and dashes.
        :type event: string

        :param location:
            The location in the application interface where the web section
            should appear.
            For the Atlassian application interface, a location is something
            like the coordinates on a map.
            It points to a particular drop-down menu or navigation list in
            the UI.
        :type event: string

        :param name:
            A human readable name.
        :type event: string

        .. _external modules: https://developer.atlassian.com/static/connect/docs/beta/modules/common/web-section.html
        """
        name = name or key
        location = location or key
        section = 'module'

        self.descriptor.setdefault('modules', {})[location] = {
            "url": AtlassianConnect._make_path(section, key),
            "name": {"value": name},
            "key": key

        }

        return self._provide_client_handler(section, key)

    def webpanel(self, key, name=None, location=None, **kwargs):
        """
        Webpanel decorator. See `external webpanel`_ documentation

        Example::

            @ac.webpanel(key="userPanel",
                name="Employee Information",
                location="atl.jira.view.issue.right.context",
                conditions=[{
                    "condition": "project_type",
                    "params": {"projectTypeKey": "service_desk"}
                }])
            def employee_information_panel(client):
                return 'this is issue %s' % request.args.get('issueKey')

        :param key:
            A key to identify this module.

            This key must be unique relative to the add on, with the exception
            of Confluence macros: Their keys need to be globally unique.

            Keys must only contain alphanumeric characters and dashes.
        :type event: string

        :param location:
            The location in the application interface where the web section
            should appear.
            For the Atlassian application interface, a location is something
            like the coordinates on a map.
            It points to a particular drop-down menu or navigation list in
            the UI.
        :type event: string

        :param name:
            A human readable name.
        :type event: string

        Anything else from the `external webpanel`_ docs should also work

        .. _external webpanel: https://developer.atlassian.com/static/connect/docs/beta/modules/common/web-panel.html
        """
        name = name or key
        location = location or key
        section = 'webpanel'

        if not re.search(r"^[a-zA-Z0-9-]+$", key):
            raise Exception("Webpanel(%s) must match ^[a-zA-Z0-9-]+$" % key)

        webpanel_capability = {
            "key": key,
            "name": {"value": name},
            "url": AtlassianConnect._make_path(section, key) + '?issueKey={issue.key}',
            "location": location
        }
        if kwargs.get('conditions'):
            webpanel_capability['conditions'] = kwargs.pop('conditions')

        self.descriptor.setdefault(
            'modules', {}
        ).setdefault(
            'webPanels', []
        ).append(webpanel_capability)
        return self._provide_client_handler(section, key)

    def tasks(self):
        """Function that turns a collection of tasks
        suitable for pyinvoke_

        Example::

            from app.web import ac
            ns = Collection()
            ns.add_collection(ac.tasks())

        .. _pyinvoke: http://www.pyinvoke.org/
        """
        from invoke import task, Collection

        @task
        def list(ctx):
            """Show all clients in the database"""
            from json import dumps
            with (self.app or current_app).app_context():
                print dumps([
                    dict(c) for c in self.client_class.all()
                ])

        @task
        def show(ctx, clientKey):
            """Lookup one client from the database"""
            from json import dumps
            with (self.app or current_app).app_context():
                print dumps(dict(self.client_class.load(clientKey)))

        @task
        def install(ctx, data):
            """Add a given client from the database"""
            from json import loads
            with (self.app or current_app).app_context():
                client = loads(data)
                self.client_class.save(client)
                print "Added"

        @task()
        def uninstall(ctx, clientKey):
            """Remove a given client from the database"""
            with (self.app or current_app).app_context():
                self.client_class.delete(clientKey)
                print "Deleted"

        ns = Collection('clients')
        ns.add_task(list)
        ns.add_task(show)
        ns.add_task(install)
        ns.add_task(uninstall)
        return ns
