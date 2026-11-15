"""Local TCP evidence for Studio auth, tenancy and persisted revision boundaries."""
from concurrent.futures import ThreadPoolExecutor
from copy import deepcopy
from http.client import HTTPConnection
import json
from pathlib import Path
import shutil
import tempfile
import threading
import unittest

from services.controller.http_api import MAX_BODY, StudioAPI, make_server
from services.controller.service import ControlService
from services.controller.studio import StudioWorkspace


class StudioHTTPTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.now = 1000.0
        self.tokens = {'a' * 40: 'owner-alpha', 'b' * 40: 'owner-beta'}
        self.studio = StudioWorkspace(ControlService(self.root / 'db.sqlite', self.root / 'assets'))
        self.api = StudioAPI(self.studio, self.tokens, clock=lambda: self.now)
        self.server = make_server(self.api, ('127.0.0.1', 0))
        self.thread = threading.Thread(target=self.server.serve_forever, daemon=True)
        self.thread.start()
        self.addCleanup(self.stop_server)

    def stop_server(self):
        self.server.shutdown()
        self.server.server_close()
        self.thread.join(timeout=5)

    def request(self, method, path='/v1/studio/workspaces/default', value=None, cookie=None,
                headers=None, raw=None):
        request_headers = {'Origin': self.api.origin, 'X-WAN-Request': 'studio',
                           'Content-Type': 'application/json'}
        if cookie:
            request_headers['Cookie'] = cookie
        request_headers.update(headers or {})
        request_headers = {k: v for k, v in request_headers.items() if v is not None}
        body = raw if raw is not None else json.dumps(value).encode() if value is not None else b''
        connection = HTTPConnection(*self.server.server_address, timeout=5)
        try:
            connection.request(method, path, body=body, headers=request_headers)
            response = connection.getresponse()
            content = response.read()
            data = json.loads(content) if response.getheader('Content-Type') == 'application/json' else content
            return response.status, data, dict(response.getheaders())
        finally:
            connection.close()

    def login(self, token='a' * 40):
        status, data, headers = self.request('POST', '/v1/studio/session', {'token': token})
        self.assertEqual(status, 200, data)
        self.assertIn('HttpOnly', headers['Set-Cookie'])
        self.assertIn('SameSite=Strict', headers['Set-Cookie'])
        self.assertEqual(headers['Cache-Control'], 'no-store')
        return headers['Set-Cookie'].split(';')[0]

    def create(self, cookie, expected=0):
        status, data, _ = self.request('POST', '/v1/studio/workspaces',
                                      {'title': 'Fictional film', 'kind': 'short_film',
                                       'expected_revision': expected}, cookie)
        self.assertEqual(status, 201, data)
        return data['workspace']

    def test_login_csrf_and_host_boundaries(self):
        for headers in ({'Origin': None}, {'Origin': 'http://evil.example'},
                        {'X-WAN-Request': None}, {'Host': 'evil.example'}):
            with self.subTest(headers=headers):
                status, _, _ = self.request('POST', '/v1/studio/session',
                                             {'token': 'a' * 40}, headers=headers)
                self.assertEqual(status, 403)
        self.assertFalse(self.api.sessions)
        self.assertEqual(self.request('POST', '/v1/studio/session', {'token': 'a' * 40},
                                     headers={'Content-Type': 'text/plain'})[0], 415)
        cookie = self.login()
        self.assertEqual(self.request('PUT', value={}, cookie=cookie,
                                     headers={'Origin': 'null'})[0], 403)
        self.assertEqual(self.request('GET', cookie=cookie, headers={'Host': 'evil.example'})[0], 403)

    def test_authentication_cookie_expiry_and_logout(self):
        self.assertEqual(self.request('GET')[0], 401)
        self.assertEqual(self.request('GET', cookie='wan_studio_session=forged')[0], 401)
        cookie = self.login()
        self.assertEqual(self.request('GET', '/v1/studio/session', cookie=cookie)[1],
                         {'owner_id': 'owner-alpha'})
        self.assertEqual(self.request('DELETE', '/v1/studio/session', cookie=cookie)[0], 200)
        self.assertEqual(self.request('GET', cookie=cookie)[0], 401)
        cookie = self.login()
        self.now += 1801
        self.assertEqual(self.request('GET', cookie=cookie)[0], 401)
        secure_api = StudioAPI(self.studio, self.tokens, origin='https://studio.example')
        self.assertIn('; Secure', secure_api.cookie('fictional'))

    def test_cross_owner_workspace_cannot_be_read_or_written(self):
        alpha, beta = self.login(), self.login('b' * 40)
        workspace = self.create(alpha)
        status, data, _ = self.request('GET', cookie=beta)
        self.assertEqual(status, 200)
        self.assertEqual(data['workspace']['projects'], [])
        forged = deepcopy(workspace)
        forged['revision'] = 0
        status, _, _ = self.request('PUT', value={'workspace': forged, 'expected_revision': 0}, cookie=beta)
        self.assertIn(status, (404, 422))
        self.assertEqual(self.request('GET', cookie=alpha)[1]['workspace'], workspace)
        self.assertEqual(self.request('GET', cookie=beta)[1]['workspace']['revision'], 0)
        forged = deepcopy(workspace)
        forged['projects'][0]['bundle']['project']['owner_id'] = 'owner-beta'
        self.assertEqual(self.request('PUT', value={'workspace': forged, 'expected_revision': 1},
                                     cookie=alpha)[0], 422)

    def test_revision_conflict_preserves_data_and_restart(self):
        cookie = self.login()
        workspace = self.create(cookie)
        workspace['projects'][0]['script'] = 'A fictional moonlit scene.'
        payload = {'workspace': workspace, 'expected_revision': 1}
        status, data, _ = self.request('PUT', value=payload, cookie=cookie)
        self.assertEqual(status, 200, data)
        saved = data['workspace']
        self.assertEqual(saved['revision'], 2)
        self.assertEqual(self.request('PUT', value=payload, cookie=cookie)[0], 409)
        self.assertEqual(self.request('POST', '/v1/studio/workspaces',
                                     {'title': 'Stale', 'kind': 'cartoon', 'expected_revision': 1}, cookie)[0], 409)
        restarted = StudioWorkspace(ControlService(self.root / 'db.sqlite', self.root / 'assets'))
        self.assertEqual(restarted.get('owner-alpha'), saved)

    def test_concurrent_revision_writes_commit_once(self):
        cookie = self.login()
        workspace = self.create(cookie)
        def save(script):
            update = deepcopy(workspace)
            update['projects'][0]['script'] = script
            return self.request('PUT', value={'workspace': update, 'expected_revision': 1}, cookie=cookie)[0]
        with ThreadPoolExecutor(max_workers=2) as pool:
            self.assertEqual(sorted(pool.map(save, ['First', 'Second'])), [200, 409])
        saved = self.request('GET', cookie=cookie)[1]['workspace']
        self.assertEqual(saved['revision'], 2)
        self.assertIn(saved['projects'][0]['script'], ['First', 'Second'])

    def test_client_cannot_inject_execution_or_preview_authority(self):
        cookie = self.login()
        workspace = self.create(cookie)
        project = workspace['projects'][0]
        for collection in ('batches', 'attempts', 'takes', 'reviews', 'timelines', 'exports', 'assets'):
            project['bundle'][collection] = [{'id': 'forged'}]
        project['media'] = {'forged': 'https://evil.example/track'}
        project['shotHistory'] = [{'id': 'forged'}]
        status, data, _ = self.request('PUT', value={'workspace': workspace, 'expected_revision': 1}, cookie=cookie)
        self.assertEqual(status, 200, data)
        saved = data['workspace']['projects'][0]
        for collection in ('batches', 'attempts', 'takes', 'reviews', 'timelines', 'exports', 'assets'):
            self.assertEqual(saved['bundle'][collection], [])
        self.assertEqual(saved['media'], {})
        self.assertEqual(saved['shotHistory'], [])

    def test_bad_payloads_and_login_rate_limit(self):
        cookie = self.login()
        for raw in (b'{', b'[]', b'null', b'\xff'):
            self.assertEqual(self.request('PUT', cookie=cookie, raw=raw)[0], 422)
        self.assertEqual(self.request('PUT', cookie=cookie, raw=b'',
                                     headers={'Content-Length': str(MAX_BODY + 1)})[0], 413)
        for _ in range(10):
            self.assertEqual(self.request('POST', '/v1/studio/session', {'token': 'invalid'})[0], 401)
        self.assertEqual(self.request('POST', '/v1/studio/session', {'token': 'a' * 40})[0], 429)
        self.now += 61
        self.login()

    def test_asset_download_tenancy_ranges_and_path_confinement(self):
        repository = Path(__file__).resolve().parents[1]
        fixture = json.loads((repository / 'fixtures/project.json').read_text())
        fixture['project']['owner_id'] = 'owner-alpha'
        for asset in fixture['assets']:
            asset['owner_id'] = 'owner-alpha'
        shutil.copytree(repository / 'fixtures/media', self.root / 'assets/media')
        self.studio.control.seed('owner-alpha', fixture)
        alpha, beta = self.login(), self.login('b' * 40)
        asset = fixture['assets'][0]
        path = f"/v1/studio/projects/{fixture['project']['id']}/assets/{asset['id']}/content"
        source = self.root / 'assets' / asset['object_key']
        expected = source.read_bytes()
        status, data, headers = self.request('GET', path, cookie=alpha)
        self.assertEqual((status, data), (200, expected))
        self.assertEqual(headers['Cache-Control'], 'no-store')
        self.assertEqual(headers['X-Content-Type-Options'], 'nosniff')
        self.assertIn('sandbox', headers['Content-Security-Policy'])
        self.assertEqual(self.request('GET', path)[0], 401)
        self.assertEqual(self.request('GET', path, cookie=beta)[0], 404)
        for requested, expected_slice in [('bytes=0-31', expected[:32]), ('bytes=-10', expected[-10:]),
                                          ('bytes=10-', expected[10:])]:
            status, data, headers = self.request('GET', path, cookie=alpha, headers={'Range': requested})
            self.assertEqual((status, data), (206, expected_slice))
            self.assertIn('Content-Range', headers)
        for requested in ('bytes=999999999-', 'bytes=5-2', 'bytes=-0', 'bytes=0-1,4-5'):
            self.assertEqual(self.request('GET', path, cookie=alpha, headers={'Range': requested})[0], 416)
        outside = self.root / 'outside.mp4'
        source.replace(outside)
        source.symlink_to(outside)
        self.assertEqual(self.request('GET', path, cookie=alpha)[0], 404)


if __name__ == '__main__':
    unittest.main()
