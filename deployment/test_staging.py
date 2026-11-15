import http.client
import json
import os
import socket
import subprocess
import sys
import time
from pathlib import Path
import tempfile
import threading
import unittest

from deployment.check_artifacts import check, check_runtime_imports
from deployment.local_stage import create_server, validate_origin
from deployment.prepare import prepare
from services.controller.service import ControlService
from services.controller.studio import StudioWorkspace

TOKEN = 'fictional-stage-token-at-least-32-characters'


class StagingTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        self.static = self.root / 'dist'
        self.static.mkdir()
        (self.static / 'index.html').write_text('<!doctype html><title>Fixture studio</title>')
        (self.static / 'app.js').write_text('console.log("fictional");')
        (self.root / 'secret').write_text('private')
        (self.static / 'escape').symlink_to(self.root / 'secret')
        (self.static / '.env').write_text('private')
        self.control = ControlService(self.root / 'state.sqlite', self.root / 'assets')
        self.server = create_server(self.control, {TOKEN: 'fictional-owner'}, self.static,
                                    'http://127.0.0.1:8080', ('127.0.0.1', 0))
        self.thread = threading.Thread(target=self.server.serve_forever, daemon=True)
        self.thread.start()

    def tearDown(self):
        self.server.shutdown()
        self.server.server_close()
        self.thread.join()
        self.temp.cleanup()

    def request(self, path, method='GET', body=None, headers=None):
        connection = http.client.HTTPConnection(*self.server.server_address, timeout=5)
        connection.request(method, path, body=body, headers=headers or {})
        response = connection.getresponse()
        result = response.status, dict(response.getheaders()), response.read()
        connection.close()
        return result

    def test_static_health_and_confinement(self):
        status, headers, body = self.request('/')
        self.assertEqual(status, 200)
        self.assertIn(b'Fixture studio', body)
        self.assertEqual(headers['X-Content-Type-Options'], 'nosniff')
        self.assertIn("frame-ancestors 'none'", headers['Content-Security-Policy'])
        self.assertEqual(self.request('/app.js')[0], 200)
        self.assertEqual(self.request('/healthz')[0], 200)
        for path in ['/../secret', '/%2e%2e/secret', '/escape', '/.env', '/missing']:
            self.assertEqual(self.request(path)[0], 404, path)
        self.assertEqual(self.request('/', headers={'Host': 'evil.invalid'})[0], 403)
        self.assertEqual(self.request('/v1/not-an-api')[0], 401)
        self.assertEqual(self.request('/v1/studio/session', method='HEAD')[0], 405)
        self.assertEqual(self.request('/', method='HEAD')[2], b'')

    def test_same_origin_login_and_creator_persistence(self):
        headers = {'Origin': 'http://127.0.0.1:8080', 'Content-Type': 'application/json', 'X-WAN-Request': 'studio'}
        status, response, _ = self.request('/v1/studio/session', 'POST', json.dumps({'token': TOKEN}), headers)
        self.assertEqual(status, 200)
        self.assertIn('HttpOnly', response['Set-Cookie'])
        headers['Cookie'] = response['Set-Cookie'].split(';')[0]
        payload = json.dumps({'title': 'Fictional staging project', 'kind': 'music_video', 'expected_revision': 0})
        self.assertEqual(self.request('/v1/studio/workspaces', 'POST', payload, headers)[0], 201)
        self.assertTrue((self.root / 'state.sqlite').exists())
        self.assertEqual(len(json.loads(self.request('/v1/studio/workspaces/default', headers=headers)[2])['workspace']['projects']), 1)
        headers['Origin'] = 'http://evil.invalid'
        self.assertEqual(self.request('/v1/studio/workspaces', 'POST', payload, headers)[0], 403)

    def test_health_tracks_dead_worker(self):
        self.server.worker_threads = [threading.Thread(target=lambda: None)]
        self.assertEqual(self.request('/healthz')[0], 503)


class ConfigurationTests(unittest.TestCase):
    def test_cli_sigterm_preserves_external_state(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            static = root / 'dist'
            static.mkdir()
            (static / 'index.html').write_text('<title>Fictional staging</title>')
            token_file = root / 'tokens.json'
            token_file.write_text(json.dumps({TOKEN: 'fictional-owner'}))
            token_file.chmod(0o600)
            with socket.socket() as reservation:
                reservation.bind(('127.0.0.1', 0))
                port = reservation.getsockname()[1]
            environment = {**os.environ, 'WAN_STUDIO_TOKEN_FILE': str(token_file),
                           'WAN_STUDIO_ORIGIN': f'http://127.0.0.1:{port}'}
            restored = root / 'state'
            restored.mkdir()
            restored_database = restored / 'database.sqlite'
            restored_control = ControlService(restored_database, restored / 'assets')
            StudioWorkspace(restored_control).create('fictional-owner', 'Recovered project', 'music_video', 0)
            (restored / 'RESTORED.json').write_text('{}')
            refused = subprocess.run([sys.executable, '-m', 'deployment.local_stage', '--state', str(restored), '--static', str(static)],
                                     cwd=Path(__file__).resolve().parents[1], env={**environment, 'WAN_STUDIO_DATABASE': ''},
                                     capture_output=True, text=True, timeout=10)
            self.assertNotEqual(refused.returncode, 0)
            self.assertIn('explicit --database', refused.stderr)
            self.assertFalse((restored / 'studio.sqlite').exists())

            process = subprocess.Popen([sys.executable, '-m', 'deployment.local_stage',
                                        '--state', str(restored), '--database', str(restored_database), '--assets', str(restored / 'assets'), '--static', str(static), '--port', str(port)],
                                       cwd=Path(__file__).resolve().parents[1], env=environment,
                                       stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
            try:
                for _ in range(100):
                    if process.poll() is not None:
                        self.fail(process.communicate()[1])
                    try:
                        connection = http.client.HTTPConnection('127.0.0.1', port, timeout=1)
                        connection.request('GET', '/healthz')
                        response = connection.getresponse()
                        ready = response.status == 200
                        response.read()
                        connection.close()
                        if ready:
                            break
                    except OSError:
                        pass
                    time.sleep(.05)
                else:
                    self.fail('Staging health timeout')
                connection = http.client.HTTPConnection('127.0.0.1', port, timeout=3)
                connection.request('POST', '/v1/studio/session', json.dumps({'token': TOKEN}),
                                   {'Origin': environment['WAN_STUDIO_ORIGIN'], 'Content-Type': 'application/json', 'X-WAN-Request': 'studio'})
                response = connection.getresponse()
                self.assertEqual(response.status, 200)
                cookie = response.getheader('Set-Cookie').split(';')[0]
                response.read()
                connection.close()
                connection = http.client.HTTPConnection('127.0.0.1', port, timeout=3)
                connection.request('GET', '/v1/studio/workspaces/default', headers={'Cookie': cookie})
                response = connection.getresponse()
                self.assertEqual(response.status, 200)
                self.assertEqual(json.loads(response.read())['workspace']['projects'][0]['bundle']['project']['title'], 'Recovered project')
                connection.close()
                process.terminate()
                process.wait(timeout=10)
                self.assertEqual(process.returncode, 0)
                self.assertTrue(restored_database.is_file())
                self.assertFalse((restored / 'studio.sqlite').exists())
                self.assertEqual(StudioWorkspace(restored_control).get('fictional-owner')['projects'][0]['bundle']['project']['title'], 'Recovered project')
            finally:
                if process.poll() is None:
                    process.kill()
                    process.wait()
                process.communicate()

    def test_pinned_source_inputs(self):
        self.assertEqual(check(), (3, 6))

    def test_runtime_copy_sources_import_in_isolation(self):
        check_runtime_imports()

    def test_origin_is_loopback_only(self):
        for value in ['https://example.com', 'http://0.0.0.0:8080', 'http://127.0.0.1:8080/path', 'http://u@localhost:8080']:
            with self.assertRaises(ValueError):
                validate_origin(value)

    def test_secret_preparation_is_external_private_and_non_destructive(self):
        with tempfile.TemporaryDirectory() as directory:
            env = prepare(Path(directory) / 'staging', 'fictional-owner')
            token_file = env.parent / 'tokens.json'
            self.assertEqual(token_file.stat().st_mode & 0o777, 0o600)
            self.assertEqual(list(json.loads(token_file.read_text()).values()), ['fictional-owner'])
            self.assertNotIn(next(iter(json.loads(token_file.read_text()))), env.read_text())
            original = token_file.read_bytes()
            with self.assertRaises(ValueError):
                prepare(env.parent, 'replacement-owner')
            self.assertEqual(original, token_file.read_bytes())
        with self.assertRaises(ValueError):
            prepare(Path(__file__).resolve().parent / 'state', 'fictional-owner')


if __name__ == '__main__':
    unittest.main()
