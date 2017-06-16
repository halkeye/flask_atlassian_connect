import re
from functools import partial, update_wrapper, wraps

from atlassian_jwt import Authenticator
from flask import abort, current_app, jsonify, redirect, request
from jwt import decode
from jwt.exceptions import DecodeError
from requests import get


def _relative_to_base(app, path):
    base = app.config['BASE_URL']
    path = '/' + path if not path.startswith('/') else path
    return base + path


class Client(dict):
    """Default implementation of Client object"""
    def __init__(self, *args, **kwargs):
        super(Client, self).__init__(*args, **kwargs)
        self.__dict__.update(**kwargs)

    def __getitem__(self, k):
        return self.__dict__.get(k)


class SimpleAuthenticator(Authenticator):
    """Implementation of Authenticator for Atlassian"""
    def __init__(self, addon, *args, **kwargs):
        super(SimpleAuthenticator, self).__init__(*args, **kwargs)
        self.addon = addon

    def get_shared_secret(self, client_key):
        """ . """
        client = self.addon.get_client_by_id(client_key)
        if client is None:
            raise Exception('No client for ' + client_key)
        if isinstance(client, dict):
            return client.get('sharedSecret')
        return client.sharedSecret


class AtlassianConnect(object):
    """Atlassian Connect Addon"""
    def __init__(self,
                 app=None,
                 get_client_by_id_func=None,
                 set_client_by_id_func=None):
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
        if not get_client_by_id_func:
            raise Exception("Must provide get client function")
        if not set_client_by_id_func:
            raise Exception("Must provide get client function")
        self.get_client_by_id = get_client_by_id_func
        self.set_client_by_id = set_client_by_id_func
        self.auth = SimpleAuthenticator(addon=self)
        self.sections = {}

    def init_app(self, app):
        """
        Initialize Application object stuff

        :param app:
            App Object
        :type app: App Object
        """
        app.config.setdefault('BASE_URL', u"http://localhost:5000")
        app.route('/atlassian_connect/descriptor',
                  methods=['GET'])(self.get_descriptor)
        app.route('/atlassian_connect/<section>/<name>',
                  methods=['GET', 'POST'])(self.handler_router)

    def get_descriptor(self):
        """Output atlassian connector descriptor file"""
        return jsonify(self.descriptor)

    def handler_router(self, section, name):
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
                client = self.get_client_by_id(client_key)
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
            client = request.get_json()
            response = get(
                client['baseUrl'].rstrip('/') +
                '/plugins/servlet/oauth/consumer-info')
            response.raise_for_status()

            key = re.search(r"<key>(.*)</key>", response.text).groups()[0]
            publicKey = re.search(
                r"<publicKey>(.*)</publicKey>", response.text
            ).groups()[0]

            if key != client['clientKey'] or publicKey != client['publicKey']:
                raise Exception("Invalid Credentials")

            stored_client = self.get_client_by_id(client['clientKey'])
            if stored_client:
                token = request.headers.get('authorization', '').lstrip('JWT ')
                if not token:
                    # Is not first install, but did not sign the request
                    # properly for an update
                    return '', 401
                try:
                    decode(
                        token,
                        stored_client['sharedSecret'],
                        options={"verify_aud": False})
                except (ValueError, DecodeError):
                    # Invalid secret, so things did not get installed
                    return '', 401

            self.set_client_by_id(client)
            kwargs['client'] = client
            return func(*args, **kwargs)
        return inner

    def webhook(self, event, path=None, exclude_body=False,
                filter=None, property_keys=None):
        """
        Webhook decorator

        :param event:
            Which event do we want to listen to
        :type event: string

        :param path:
            Which event do we want to listen to

            Defa
        :type event: string
        """
        section = 'webhook'

        webhook = {
            "event": event,
            "url": AtlassianConnect._make_path(section, event.replace(":", "")),
            "excludeBody": exclude_body
        }
        if filter:
            webhook["filter"] = filter
        if property_keys:
            webhook["propertyKeys"] = property_keys

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
