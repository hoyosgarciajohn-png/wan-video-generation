import io
import json
from pathlib import Path
import tempfile
import unittest

from deployment.hosted_app import Application, open_control
from deployment.cleanup_monitor import sweep, CleanupOnlyProvider
from services.controller.http_api import StudioAPI
from services.controller.service import ControlService
from services.controller.studio import StudioWorkspace


class HostedApplicationTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.static = self.root / 'static'
        self.static.mkdir()
        (self.static / 'index.html').write_text('<h1>Fictional Studio</h1>')
        (self.root / 'private.txt').write_text('not served')
        control = ControlService(self.root / 'state.sqlite', self.root / 'assets')
        self.token = 'fictional-test-token-' + 'a' * 32
        self.app = Application(StudioAPI(StudioWorkspace(control), {self.token: 'owner'}, 'https://wan.example.test'), self.static)

    def call(self, path, method='GET', data=b'', **headers):
        env = dict(PATH_INFO=path, REQUEST_METHOD=method, HTTP_HOST='wan.example.test',
                   CONTENT_LENGTH=str(len(data)), CONTENT_TYPE='application/json',
                   REMOTE_ADDR='192.0.2.1', **{'wsgi.input': io.BytesIO(data)})
        env.update(headers)
        result = {}
        def start(status, values): result.update(status=int(status.split()[0]), headers=dict(values))
        result['body'] = b''.join(self.app(env, start))
        return result

    def test_https_session_and_cross_origin_rejection(self):
        result = self.call('/v1/studio/session', 'POST', json.dumps({'token': self.token}).encode(),
                           HTTP_ORIGIN='https://wan.example.test', HTTP_X_WAN_REQUEST='studio')
        self.assertEqual(result['status'], 200)
        self.assertIn('; Secure', result['headers']['Set-Cookie'])
        denied = self.call('/v1/studio/session', 'POST', b'{}', HTTP_ORIGIN='https://other.example.test', HTTP_X_WAN_REQUEST='studio')
        self.assertEqual(denied['status'], 403)
        self.assertEqual(self.call('/v1/studio/projects')['status'], 401)

    def test_static_and_api_do_not_expose_files_or_fall_back(self):
        self.assertEqual(self.call('/')['status'], 200)
        self.assertEqual(self.call('/../private.txt')['status'], 404)
        (self.static / 'linked').symlink_to(self.root / 'private.txt')
        self.assertEqual(self.call('/linked')['status'], 404)
        self.assertEqual(self.call('/v1/unknown')['status'], 401)
        self.assertEqual(self.call('/', HTTP_HOST='evil.example.test')['status'], 403)
        head = self.call('/', 'HEAD')
        self.assertEqual(head['body'], b'')
        self.assertGreater(int(head['headers']['Content-Length']), 0)

    def test_request_bounds_and_health_failure(self):
        self.assertEqual(self.call('/v1/studio/projects', 'POST', CONTENT_LENGTH='999999999')['status'], 413)
        self.assertEqual(self.call('/v1/studio/projects', 'POST', CONTENT_LENGTH='1')['status'], 413)
        self.assertEqual(self.call('/healthz')['status'], 200)
        self.app.healthy = lambda: False
        self.assertEqual(self.call('/healthz')['status'], 503)

    def test_restore_never_silently_opens_an_empty_database(self):
        (self.root / 'RESTORED.json').write_text('{}')
        with self.assertRaises(ValueError): open_control({'WAN_STATE': str(self.root)})
        with self.assertRaises(ValueError):
            open_control({'WAN_STATE': str(self.root), 'WAN_STUDIO_DATABASE': str(self.root / 'missing.sqlite'),
                          'WAN_STUDIO_ASSETS': str(self.root / 'assets')})
        self.assertFalse((self.root / 'missing.sqlite').exists())


class CleanupMonitorTests(unittest.TestCase):
    def setUp(self):
        from tests.test_live_execution import LiveExecutionTests
        self.fixture = LiveExecutionTests()
        self.fixture.setUp()
        self.addCleanup(self.fixture.doCleanups)
        self.addCleanup(self.fixture.tearDown)

    def test_new_monitor_process_cleans_completed_pod_without_create(self):
        f = self.fixture
        f.provision()
        self.assertEqual(len(f.http.pods), 1)
        f.execution.cancel(f.owner, f.project, f.job)
        result = sweep(f.control.db_path, 'fictional-token', transport=f.http)
        self.assertTrue(result['ready'])
        self.assertEqual(f.http.pods, {})
        self.assertEqual(f.http.posts, 1)
        self.assertEqual(f.execution.status(f.owner, f.project, f.job)['batch']['cleanup_state'], 'confirmed')
        self.assertEqual(sweep(f.control.db_path, 'fictional-token', transport=f.http)['due_batches'], 0)

    def test_deadline_cleanup_survives_lost_create_response_and_outage(self):
        f = self.fixture
        f.http.unknown = True
        f.provision()
        now = f.control.clock().timestamp() + 10000
        def unavailable(*_, **__): raise TimeoutError('fictional outage')
        failed = sweep(f.control.db_path, 'fictional-token', transport=unavailable, now=now)
        self.assertFalse(failed['ready'])
        recovered = sweep(f.control.db_path, 'fictional-token', transport=f.http, now=now)
        self.assertTrue(recovered['ready'])
        self.assertEqual(f.http.posts, 1)
        self.assertEqual(f.http.pods, {})

    def test_monitor_transport_refuses_resource_creation(self):
        provider = CleanupOnlyProvider('fictional-token', scope='fictional')
        with self.assertRaises(PermissionError): provider.create('batch', 'batch')
        with self.assertRaises(PermissionError): provider._request('POST', '/pods', {})


if __name__ == '__main__': unittest.main()
