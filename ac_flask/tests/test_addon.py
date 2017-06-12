import unittest
import json
import requests_mock
import requests
from flask import Flask
from .. import ACAddon
from atlassian_jwt.encode import encode_token

consumer_info_response = """<?xml version="1.0" encoding="UTF-8"?>
    <consumer>
    <key>abc123</key>
    <name>JIRA</name>
    <publicKey>public123</publicKey>
    <description>Atlassian JIRA at https://gavindev.atlassian.net </description>
    </consumer>"""


def decorator_noop(**kwargs):
    return '', 204


class ACFlaskTestCase(unittest.TestCase):
    def set_client(self, client):
        self.clients[client['clientKey']] = client

    def get_client(self, clientKey):
        return self.clients.get(clientKey)

    def setUp(self):
        self.app = Flask("app")
        self.clients = {}
        self.ac = ACAddon(self.app,
                          set_client_by_id_func=self.set_client,
                          get_client_by_id_func=self.get_client)
        self.client = self.app.test_client()
        self.ac.lifecycle('installed')(decorator_noop)

    def tearDown(self):
        pass

    def request_get(self, clientKey, url):
        client = dict(
            baseUrl='https://gavindev.atlassian.net',
            clientKey=clientKey,
            publicKey='public123',
            sharedSecret='myscret')
        self.set_client(client)
        auth = encode_token(
            'GET', url,
            client['clientKey'], client['sharedSecret'])
        return self.client.get(
            url,
            content_type='application/json',
            headers={'Authorization': 'JWT ' + auth})

    def test_index_redirects(self):
        rv = self.client.get('/')
        self.assertEquals(302, rv.status_code)
        self.assertEquals(
            'http://localhost/addon/descriptor', rv.headers['Location'])
        rv = self.client.get('/', follow_redirects=True)
        self.assertEquals(200, rv.status_code)
        self.assertEquals(
            {"type": "jwt"},
            json.loads(rv.get_data())['authentication']
        )

    def test_descriptor_stuff(self):
        rv = self.client.get('/addon/descriptor')
        self.assertEquals(200, rv.status_code)
        self.assertEquals(
            {"type": "jwt"},
            json.loads(rv.get_data())['authentication']
        )

    @unittest.skip("slow")
    def test_descriptor_should_validate(self):
        rv = self.client.get('/addon/descriptor')
        self.assertEquals(200, rv.status_code)
        rv = requests.post(
            'https://atlassian-connect-validator.herokuapp.com/validate',
            data={'descriptor': rv.data, 'product': 'jira'}
        )
        self.assertIn('Validation passed', rv.text)

    def test_lifecycle_installed(self):
        with requests_mock.mock() as m:
            m.get('https://gavindev.atlassian.net/plugins/servlet/oauth/consumer-info',
                  text=consumer_info_response)

            client = dict(
                baseUrl='https://gavindev.atlassian.net',
                clientKey='abc123',
                publicKey='public123')
            rv = self.client.post('/lifecycle/installed',
                                  data=json.dumps(client),
                                  content_type='application/json')
            self.assertEquals(204, rv.status_code)

    def test_lifecycle_installed_multiple_no_auth(self):
        """Multiple requests should fail unless auth is provided the second time"""
        with requests_mock.mock() as m:
            m.get('https://gavindev.atlassian.net/plugins/servlet/oauth/consumer-info',
                  text=consumer_info_response)

            client = dict(
                baseUrl='https://gavindev.atlassian.net',
                clientKey='abc123',
                publicKey='public123')
            rv = self.client.post('/lifecycle/installed',
                                  data=json.dumps(client),
                                  content_type='application/json')
            self.assertEquals(204, rv.status_code)
            rv = self.client.post('/lifecycle/installed',
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
            rv = self.client.post('/lifecycle/installed',
                                  data=json.dumps(client),
                                  content_type='application/json')
            self.assertEquals(204, rv.status_code)
            # Add auth
            auth = encode_token(
                'GET',
                '/lifecycle/installed',
                client['clientKey'],
                client['sharedSecret'])
            rv = self.client.post('/lifecycle/installed',
                                  data=json.dumps(client),
                                  content_type='application/json',
                                  headers={'Authorization': 'JWT ' + auth})
            self.assertEquals(204, rv.status_code)

    def test_lifecycle_installed_multiple_invalid_auth(self):
        """Multiple requests should error if second update is untrusted"""
        with requests_mock.mock() as m:
            m.get('https://gavindev.atlassian.net/plugins/servlet/oauth/consumer-info',
                  text=consumer_info_response)

            client = dict(
                baseUrl='https://gavindev.atlassian.net',
                clientKey='abc123',
                publicKey='public123',
                sharedSecret='myscret')
            rv = self.client.post('/lifecycle/installed',
                                  data=json.dumps(client),
                                  content_type='application/json')
            self.assertEquals(204, rv.status_code)
            # Add auth
            auth = encode_token(
                'GET',
                '/lifecycle/installed',
                client['clientKey'],
                'some other secret')
            rv = self.client.post('/lifecycle/installed',
                                  data=json.dumps(client),
                                  content_type='application/json',
                                  headers={'Authorization': 'JWT ' + auth})
            self.assertEquals(401, rv.status_code)

    def test_webook(self):
        self.ac.webhook('jira:issue_created', filter="project is 'IM'")(
            decorator_noop)

        rv = self.client.get('/addon/descriptor')
        self.assertEquals(200, rv.status_code)
        self.assertIn({
            "event": "jira:issue_created",
            "excludeBody": False,
            "filter": "project is 'IM'",
            "url": "/webhook/jiraissue_created"
        }, json.loads(rv.data)["modules"]["webhooks"])

        client = dict(
            baseUrl='https://gavindev.atlassian.net',
            clientKey='test_webook',
            publicKey='public123',
            sharedSecret='myscret')
        self.set_client(client)
        auth = encode_token(
            'POST',
            '/webhook/jiraissue_created',
            client['clientKey'],
            client['sharedSecret'])
        rv = self.client.post('/webhook/jiraissue_created',
                              data=json.dumps(client),
                              content_type='application/json',
                              headers={'Authorization': 'JWT ' + auth})
        self.assertEquals(204, rv.status_code)

    def test_webpanel(self):
        """Confirm webpanel decorator works right"""
        self.ac.webpanel(
            key="userPanel",
            name="Bamboo Employee Information",
            location="atl.jira.view.issue.right.context",
            conditions=[{
                "condition": "project_type",
                "params": {"projectTypeKey": "service_desk"}
                }])(decorator_noop)

        response = self.client.get('/addon/descriptor')
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
            "url": "/webpanel/userPanel?issueKey={issue.key}"
        }, json.loads(response.data)["modules"]["webPanels"])

        response = self.request_get('test_webpanel',
                                    '/webpanel/userPanel?issueKey=TEST-1')
        self.assertEquals(204, response.status_code)

    def test_module(self):
        """Confirm webpanel decorator works right"""
        self.ac.module(name="Configure", key="configurePage")(decorator_noop)

        response = self.client.get('/addon/descriptor')
        self.assertEquals(200, response.status_code)
        self.assertEquals({
            "key": "configurePage",
            "name": {"value": "Configure"},
            "url": "/module/configurePage"
        }, json.loads(response.data)["modules"]["configurePage"])

        response = self.request_get('test_module', "/module/configurePage")
        self.assertEquals(204, response.status_code)


if __name__ == '__main__':
    unittest.main()
