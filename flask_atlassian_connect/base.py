import re
from functools import wraps

from atlassian_jwt import Authenticator
from flask import abort, current_app, jsonify, request
from jwt import decode
from jwt.exceptions import DecodeError
from requests import get
from .default_client import Client


def _relative_to_base(app, path):
    base = app.config['BASE_URL']
    path = '/' + path if not path.startswith('/') else path
    return base + path


class _SimpleAuthenticator(Authenticator):
    """Implementation of Authenticator for Atlassian"""
    def __init__(self, addon, *args, **kwargs):
        super(_SimpleAuthenticator, self).__init__(*args, **kwargs)
        self.addon = addon

    def get_shared_secret(self, client_key):
        """ . """
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
    def __init__(self, app=None, client_class=Client):
        self.app = app
        if app is not None:
            self.init_app(app)
        self.descriptor = {
            "name": app.config.get('ADDON_NAME', ""),
            "description": app.config.get('ADDON_DESCRIPTION', ""),
            "key": app.config.get('ADDON_KEY'),
            "authentication": {"type": "jwt"},
            "baseUrl": _relative_to_base(app, '/'),
            "scopes": app.config.get('ADDON_SCOPES', ["READ"]),
            "vendor": {
                "name": app.config.get('ADDON_VENDOR_NAME'),
                "url": app.config.get('ADDON_VENDOR_URL')
            },
            "lifecycle": {},
            "links": {
                "self": _relative_to_base(app, "/atlassian_connect/descriptor")
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

    def _get_descriptor(self):
        """Output atlassian connector descriptor file"""
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
        if isinstance(ret, tuple):
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
                kwargs['client'] = client
                if kwargs_updator:
                    kwargs.update(kwargs_updator(**kwargs))

                ret = func(**kwargs)
                if isinstance(ret, tuple):
                    return ret
                return '', 204
            self._add_handler(section, name, _handler)
            return func
        return _wrapper

    def _add_handler(self, section, name, handler):
        self.sections.setdefault(section, {})[name] = handler

    def lifecycle(self, name):
        """
        Lifecycle decorator

        :param name:
            Which atlassian connect lifecycle to handle.

            Examples:
                * installed
        :type name: string

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
        Webhook decorator. See external_ documentation

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
        .. _external: https://developer.atlassian.com/jiradev/jira-apis/webhooks
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

    def module(self, key, name=None, location=None, methods=None):
        methods = methods or ['GET', 'POST']
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
