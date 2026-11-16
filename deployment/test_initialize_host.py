from pathlib import Path
import sqlite3
import tempfile
import unittest
from deployment.initialize_host import initialize
from deployment.cleanup_monitor import sweep


class InitializeHostTests(unittest.TestCase):
    def test_cleanup_schema_is_ready_without_network_or_authority(self):
        with tempfile.TemporaryDirectory() as folder:
            result = initialize({'WAN_STATE': folder})
            self.assertFalse(result['paid_dispatch'])
            self.assertFalse(result['approval_keys_installed'])
            def forbidden(*args, **kwargs):
                self.fail('Empty state must not call a provider')
            database = Path(folder) / 'studio.sqlite'
            self.assertTrue(sweep(database, 'fictional-token', transport=forbidden)['ready'])
            with sqlite3.connect(database) as db:
                self.assertEqual(db.execute('SELECT COUNT(*) FROM live_approvals').fetchone()[0], 0)
                db.execute("CREATE TABLE preserved (value TEXT)")
                db.execute("INSERT INTO preserved VALUES ('fictional retained data')")
            initialize({'WAN_STATE': folder})
            with sqlite3.connect(database) as db:
                self.assertEqual(db.execute('SELECT value FROM preserved').fetchone()[0], 'fictional retained data')

    def test_restored_state_requires_explicit_paths(self):
        with tempfile.TemporaryDirectory() as folder:
            (Path(folder) / 'RESTORED.json').write_text('{}')
            with self.assertRaises(ValueError): initialize({'WAN_STATE': folder})
            self.assertFalse((Path(folder) / 'studio.sqlite').exists())
