import tempfile
import threading
from pathlib import Path
import unittest

from deployment.host_acceptance import Client, fictional_flow, verify_restored
from services.controller.backup import create_backup
from services.controller.export_runner import ExportRunner
from services.controller.http_api import StudioAPI, make_server
from services.controller.runner import FixtureRunner
from services.controller.service import ControlService
from services.controller.studio import StudioWorkspace


class HostedRecoveryRehearsalTests(unittest.TestCase):
    def test_actual_http_fixture_workflow_and_independent_restore(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            control = ControlService(root / 'source.sqlite', root / 'assets')
            token = 'fictional-operator-token-' + 'x' * 40
            api = StudioAPI(StudioWorkspace(control), {token: 'fictional-owner'})
            server = make_server(api, ('127.0.0.1', 0))
            origin = f'http://127.0.0.1:{server.server_port}'
            api.origin, api.allowed_hosts = origin, {f'127.0.0.1:{server.server_port}'}
            stop = threading.Event()
            workers = [threading.Thread(target=runner.serve, args=(stop,), daemon=True)
                       for runner in (FixtureRunner(control), ExportRunner(control))]
            thread = threading.Thread(target=server.serve_forever, daemon=True)
            thread.start()
            for worker in workers:
                worker.start()
            try:
                result = fictional_flow(Client(origin), token, root / 'evidence')
                create_backup(control.db_path, control.asset_root, root / 'backup')
                verified = verify_restored(root / 'backup', root / 'restored', result)
                self.assertTrue(verified['media_decoded'])
                self.assertTrue(verified['owner_isolation'])
                with self.assertRaises(FileExistsError):
                    fictional_flow(Client(origin), token, root / 'evidence')
                self.assertEqual(len(StudioWorkspace(control).get('fictional-owner')['projects']), 1)
            finally:
                stop.set()
                server.shutdown()
                server.server_close()
                thread.join(timeout=5)
                for worker in workers:
                    worker.join(timeout=5)


if __name__ == '__main__':
    unittest.main()
