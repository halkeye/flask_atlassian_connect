import unittest
import json
import requests_mock
import requests
from flask import Flask, render_template_string
from .. import AtlassianConnect
from ..base import AtlassianConnectClient
from atlassian_jwt.encode import encode_token

consumer_info_response = """<?xml version="1.0" encoding="UTF-8"?>
    <consumer>
    <key>abc123</key>
    <name>JIRA</name>
    <publicKey>public123</publicKey>
    <description>Atlassian JIRA at https://gavindev.atlassian.net </description>
    </consumer>"""


def decorator_noop(**kwargs):
    """NOOOOOOO OPERATION"""
    del kwargs
    return '', 204


def decorator_a_string(**kwargs):
    """This is just a simple function to prove something happens"""
    del kwargs
    return render_template_string('<h1>Something</h1> URL: {{atlassian_jwt_post_url}}')


def decorator_none(**kwargs):
    """This is a decorator that doesn't return"""
    del kwargs


class _TestClient(AtlassianConnectClient):
    @staticmethod
    def reset():
        """Clear all clients out of internal storage"""
        AtlassianConnectClient._clients = {}


class ACFlaskTestCase(unittest.TestCase):
    """Test Case"""
    def setUp(self):
        self.app = Flask("app")
        self.app.testing = True
        self.ac = AtlassianConnect(self.app, client_class=_TestClient)
        _TestClient.reset()
        self.client = self.app.test_client()
        self.ac.lifecycle('installed')(decorator_noop)

    def tearDown(self):
        pass

    def _request_get(self, clientKey, url):
        client = _TestClient(
            baseUrl='https://gavindev.atlassian.net',
            clientKey=clientKey,
            publicKey='public123',
            sharedSecret='myscret')
        _TestClient.save(client)
        auth = encode_token(
            'GET', url,
            client.clientKey,
            client.sharedSecret)
        return self.client.get(
            url,
            content_type='application/json',
            headers={'Authorization': 'JWT ' + auth})

    def _request_post(self, clientKey, url, body):
        client = _TestClient(
            baseUrl='https://gavindev.atlassian.net',
            clientKey='test_webook',
            publicKey='public123',
            sharedSecret='myscret')
        _TestClient.save(client)
        auth = encode_token(
            'POST',
            '/atlassian_connect/webhook/jiraissue_created',
            client.clientKey,
            client.sharedSecret)
        return self.client.post(
            url,
            data=json.dumps(body),
            content_type='application/json',
            headers={'Authorization': 'JWT ' + auth})

    def test_descriptor_stuff(self):
        """Grab the descriptor and make sure its valid"""
        response = self.client.get('/atlassian_connect/descriptor')
        self.assertEquals(200, response.status_code)
        self.assertEquals(
            {"type": "jwt"},
            json.loads(response.get_data())['authentication']
        )

    @unittest.skip("slow")
    def test_descriptor_should_validate(self):
        rv = self.client.get('/atlassian_connect/descriptor')
        self.assertEquals(200, rv.status_code)
        rv = requests.post(
            'https://atlassian-connect-validator.herokuapp.com/validate',
            data={'descriptor': rv.data, 'product': 'jira'}
        )
        self.assertIn('Validation passed', rv.text)

    def test_lifecycle_installed(self):
        """Do the lifecycle test"""
        with requests_mock.mock() as m:
            m.get('https://gavindev.atlassian.net/plugins/servlet/oauth/consumer-info',
                  text=consumer_info_response)
            client = dict(
                baseUrl='https://gavindev.atlassian.net',
                clientKey='abc123',
                publicKey='public123')
            response = self.client.post(
                '/atlassian_connect/lifecycle/installed',
                data=json.dumps(client),
                content_type='application/json')
            self.assertEquals(204, response.status_code)

    def test_lifecycle_installed_multiple_no_auth(self):
        """Multiple requests should fail unless auth is provided the second time"""
        with requests_mock.mock() as m:
            m.get('https://gavindev.atlassian.net/plugins/servlet/oauth/consumer-info',
                  text=consumer_info_response)

            client = dict(
                baseUrl='https://gavindev.atlassian.net',
                clientKey='abc123',
                publicKey='public123')
            rv = self.client.post('/atlassian_connect/lifecycle/installed',
                                  data=json.dumps(client),
                                  content_type='application/json')
            self.assertEquals(204, rv.status_code)
            rv = self.client.post('/atlassian_connect/lifecycle/installed',
                                  data=json.dumps(client),
                                  content_type='application/json')
            self.assertEquals(401, rv.status_code)

    def test_lifecycle_installed_multiple_with_auth(self):
        """Multiple requests  should update if the second time has auth"""
        with requests_mock.mock() as m:
            m.get('https://gavindev.atlassian.net/plugins/servlet/oauth/consumer-info',
                  text=consumer_info_response)

            client = dict(
                baseUrl='https://gavindev.atlassian.net',
                clientKey='abc123',
                publicKey='public123',
                sharedSecret='myscret')
            rv = self.client.post('/atlassian_connect/lifecycle/installed',
                                  data=json.dumps(client),
                                  content_type='application/json')
            self.assertEquals(204, rv.status_code)
            # Add auth
            auth = encode_token(
                'GET',
                '/lifecycle/installed',
                client['clientKey'],
                client['sharedSecret'])
            rv = self.client.post('/atlassian_connect/lifecycle/installed',
                                  data=json.dumps(client),
                                  content_type='application/json',
                                  headers={'Authorization': 'JWT ' + auth})
            self.assertEquals(204, rv.status_code)

    @requests_mock.Mocker()
    def test_lifecycle_installed_multiple_invalid_auth(self, m):
        """Multiple requests should error if second update is untrusted"""
        m.get('https://gavindev.atlassian.net/plugins/servlet/oauth/consumer-info',
              text=consumer_info_response)
        client = dict(
            baseUrl='https://gavindev.atlassian.net',
            clientKey='abc123',
            publicKey='public123',
            sharedSecret='myscret')
        rv = self.client.post('/atlassian_connect/lifecycle/installed',
                              data=json.dumps(client),
                              content_type='application/json')
        self.assertEquals(204, rv.status_code)
        # Add auth
        auth = encode_token(
            'GET',
            '/lifecycle/installed',
            client['clientKey'],
            'some other secret')
        rv = self.client.post('/atlassian_connect/lifecycle/installed',
                              data=json.dumps(client),
                              content_type='application/json',
                              headers={'Authorization': 'JWT ' + auth})
        self.assertEquals(401, rv.status_code)

    def test_webook(self):
        self.ac.webhook('jira:issue_created', filter="project is 'IM'")(
            decorator_noop)

        response = self.client.get('/atlassian_connect/descriptor')
        self.assertEquals(200, response.status_code)
        self.assertIn({
            u"event": u"jira:issue_created",
            u"excludeBody": False,
            u"filter": u"project is 'IM'",
            u"url": u"/atlassian_connect/webhook/jiraissue_created"
        }, json.loads(response.data)["modules"]["webhooks"])

        response = self._request_post(
            'test_webhook',
            '/atlassian_connect/webhook/jiraissue_created',
            json.dumps({
                "key": "value",
                "foo": "bar"
            })  # FIXME - not a real event
        )
        self.assertEquals(204, response.status_code)

    def test_webpanel(self):
        """Confirm webpanel decorator works right"""
        self.ac.webpanel(
            key="userPanel",
            name="Bamboo Employee Information",
            location="atl.jira.view.issue.right.context",
            conditions=[{
                "condition": "project_type",
                "params": {"projectTypeKey": "service_desk"}
            }])(decorator_a_string)

        response = self.client.get('/atlassian_connect/descriptor')
        self.assertEquals(200, response.status_code)
        self.assertIn({
            "conditions": [
                {
                    "condition": "project_type",
                    "params": {"projectTypeKey": "service_desk"}
                }
            ],
            "key": "userPanel",
            "location": "atl.jira.view.issue.right.context",
            "name": {"value": "Bamboo Employee Information"},
            "url": "/atlassian_connect/webpanel/userPanel?issueKey={issue.key}"
        }, json.loads(response.data)["modules"]["webPanels"])

        response = self._request_get(
            'test_webpanel',
            '/atlassian_connect/webpanel/userPanel?issueKey=TEST-1')
        self.assertEquals(200, response.status_code)
        self.assertIn('<h1>Something</h1>', response.data)

    def test_module(self):
        """Confirm webpanel decorator works right"""
        self.ac.module(name="Configure", key="configurePage")(decorator_noop)

        response = self.client.get('/atlassian_connect/descriptor')
        self.assertEquals(200, response.status_code)
        self.assertEquals({
            u"key": u"configurePage",
            u"name": {u"value": u"Configure"},
            u"url": "/atlassian_connect/module/configurePage"
        }, json.loads(response.data)["modules"]["configurePage"])

        response = self._request_get(
            'test_module',
            "/atlassian_connect/module/configurePage")
        self.assertEquals(204, response.status_code)

    def test_decorator_return_values(self):
        """Confirm webpanel decorator works right"""
        self.ac.webpanel(key="aString")(decorator_a_string)
        self.ac.webpanel(key="noop")(decorator_noop)
        self.ac.webpanel(key="none")(decorator_none)

        response = self._request_get(
            'test_decorator_return_values',
            '/atlassian_connect/webpanel/aString?issueKey=TEST-1')
        self.assertEquals(200, response.status_code)
        self.assertIn('<h1>Something</h1>', response.data)
        self.assertIn('/atlassian_connect/webpanel/aString?jwt=', response.data)

        response = self._request_get(
            'test_decorator_return_values',
            '/atlassian_connect/webpanel/noop?issueKey=TEST-1')
        self.assertEquals(204, response.status_code)
        self.assertEquals('', response.data)

        response = self._request_get(
            'test_decorator_return_values',
            '/atlassian_connect/webpanel/none?issueKey=TEST-1')
        self.assertEquals(204, response.status_code)
        self.assertEquals('', response.data)


if __name__ == '__main__':
    unittest.main()
