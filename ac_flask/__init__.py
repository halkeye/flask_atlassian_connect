from flask import jsonify, redirect, request, abort
from functools import wraps, partial
from jwt.exceptions import DecodeError
import atlassian_jwt
import httplib
import jwt
import logging
import os
import re
import requests


__version__ = '0.0.2'
__url__ = 'https://github.com/halkeye/ac-flask'
__author__ = 'Gavin Mogan'
__email__ = 'opensource@gavinmogan.com'


class Client(dict):
    def __init__(self, **kwargs):
        self.__dict__.update(**kwargs)

    def __getitem__(self, k):
        return self.__dict__.get(k)


class SimpleAuthenticator(atlassian_jwt.Authenticator):
    def __init__(self, addon, *args, **kwargs):
        super(SimpleAuthenticator, self).__init__()
        self.addon = addon

    def get_shared_secret(self, client_key):
        client = self.addon.get_client_by_id(client_key)
        if client is None:
            raise Exception('No client for ' + client_key)
        if isinstance(client, dict):
            return client.get('sharedSecret')
        return client.sharedSecret


def to_camelcase(s):
    return re.sub(r'(?!^)_([a-zA-Z])', lambda m: m.group(1).upper(), s)


class ACAddon(object):
    """Atlassian Connect Addon"""
    def __init__(self,
                 app=None,
                 key=None,
                 get_client_by_id_func=None,
                 set_client_by_id_func=None,
                 name=None,
                 description=None,
                 config=None,
                 env_prefix="AC_",
                 vendor_url=None,
                 vendor_name=None):
        self.app = app
        self._init_app(app, config, env_prefix)

        self.descriptor = {
            "name": name or app.config.get('ADDON_NAME', ""),
            "description": description or app.config.get('ADDON_DESCRIPTION', ""),
            "key": key or app.config.get('ADDON_KEY'),
            "authentication": {"type": "jwt"},
            "baseUrl": self._relative_to_base('/'),
            "scopes": app.config.get('ADDON_SCOPES', ["READ"]),
            "vendor": {
                "name": vendor_name or app.config.get('ADDON_VENDOR_NAME'),
                "url": vendor_url or app.config.get('ADDON_VENDOR_URL')
            },
            "lifecycle": {},
            "links": {
                "self": self._relative_to_base("/addon/descriptor")
            },
        }
        if not get_client_by_id_func:
            raise Exception("Must provide get client function")
        if not set_client_by_id_func:
            raise Exception("Must provide get client function")
        self.get_client_by_id = get_client_by_id_func
        self.set_client_by_id = set_client_by_id_func
        self.auth = SimpleAuthenticator(addon=self)

        def redirect_to_descriptor():
            return redirect('/addon/descriptor')
        app.route('/', methods=['GET'])(redirect_to_descriptor)

        def get_descriptor():
            return jsonify(self.descriptor)
        app.route('/addon/descriptor', methods=['GET'])(get_descriptor)

    @staticmethod
    def _init_app(app, config, env_prefix):
        app.config.from_object('ac_flask.default_settings')
        if config is not None:
            app.config.from_object(config)

        if env_prefix is not None:
            env_vars = {key[len(env_prefix):]: val for
                        key, val in os.environ.items()}
            app.config.update(env_vars)

    def _installed_wrapper(self, func):
        def inner(*args, **kwargs):
            client = request.get_json()
            response = requests.get(
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
                    jwt.decode(token,
                               stored_client['sharedSecret'],
                               options={"verify_aud": False})
                except (ValueError, DecodeError):
                    # Invalid secret, so things did not get installed
                    return '', 401

            self.set_client_by_id(client)
            kwargs['client'] = client
            return func(*args, **kwargs)
        return inner

    def lifecycle(self, name, path=None):
        if path is None:
            path = "/lifecycle/" + name

        self.descriptor.setdefault('lifecycle', {})[name] = path

        def inner(func):
            if name == 'installed':
                return self.app.route(rule=path, methods=['POST'])(
                    self._installed_wrapper(func))
            else:
                return self.app.route(rule=path, methods=['POST'])(func)

        return inner

    def webhook(self, event, path=None, excludeBody=False,
                filter=None, propertyKeys=None):
        if path is None:
            path = "/webhook/" + event.replace(":", "")

        webhook = {
            "event": event,
            "url": path,
            "excludeBody": excludeBody
        }
        if filter:
            webhook["filter"] = filter
        if propertyKeys:
            webhook["propertyKeys"] = propertyKeys

        self.descriptor.setdefault('modules', {}).setdefault(
            'webhooks', []).append(webhook)

        def inner(func):
            def events_jira_handler(**kwargs):
                content = request.get_json(silent=False)
                ret = func(event=content, **kwargs)
                if isinstance(ret, tuple):
                    return ret
                return '', 204
            return self.route(anonymous=False, rule=path, methods=['POST'])(
                events_jira_handler)

        return inner

    def module(self, func=None, name=None, location=None, key=None, methods=None):
        methods = methods or ['GET', 'POST']
        if func is None:
            return partial(self.module, name=name, location=location,
                           key=key, methods=methods)

        if key is None:
            key = to_camelcase(func.__name__)
        if location is None:
            location = key
        if name is None:
            name = func.__name__

        path = "/module/" + key
        self.descriptor.setdefault('modules', {})[location] = {
            "url": path,
            "name": {"value": name},
            "key": key

        }
        return self.route(anonymous=False, rule=path, methods=methods)(func)

    def webpanel(self, key, name, location, **kwargs):
        if not re.search(r"^[a-zA-Z0-9-]+$", key):
            raise Exception("Webpanel(%s) must match ^[a-zA-Z0-9-]+$" % key)

        path = "/webpanel/" + key

        webpanel_capability = {
            "key": key,
            "name": {"value": name},
            "url": path + '?issueKey={issue.key}',
            "location": location
        }
        if kwargs.get('conditions'):
            webpanel_capability['conditions'] = kwargs.pop('conditions')

        self.descriptor.setdefault(
            'modules', {}
        ).setdefault(
            'webPanels', []
        ).append(webpanel_capability)

        def inner(func):
            return self.route(anonymous=False, rule=path, methods=['GET'])(func)

        return inner

    def _relative_to_base(self, path):
        base = self.app.config['BASE_URL']
        path = '/' + path if not path.startswith('/') else path
        return base + path

    def require_client(self, func):
        @wraps(func)
        def inner(*args, **kwargs):
            client_key = self.auth.authenticate(
                request.method,
                request.url,
                request.headers)
            client = self.get_client_by_id(client_key)
            if not client:
                abort(401)
            kwargs['client'] = client
            return func(*args, **kwargs)

        return inner

    def route(self, anonymous=False, *args, **kwargs):
        """
        Decorator for routes with defaulted required authenticated client
        """
        def inner(func):
            if not anonymous:
                func = self.require_client(func)
            func = self.app.route(*args, **kwargs)(func)
            return func
        return inner
