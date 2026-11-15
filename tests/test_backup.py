"""Backup integrity, snapshot boundaries and non-destructive restore."""
from copy import deepcopy
import hashlib
import json
import os
from pathlib import Path
import shutil
import sqlite3
import tempfile
import unittest
from unittest.mock import patch

from services.controller import backup
from services.controller.service import ControlService, canonical
from services.controller.studio import StudioWorkspace

ROOT = Path(__file__).resolve().parents[1]


class BackupTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.database = self.root / 'source.sqlite'
        self.assets = self.root / 'source-assets'
        shutil.copytree(ROOT / 'fixtures/media', self.assets / 'media')
        self.control = ControlService(self.database, self.assets)
        self.fixture = json.loads((ROOT / 'fixtures/project.json').read_text())
        self.owner = self.fixture['project']['owner_id']
        self.project = self.fixture['project']['id']
        self.control.seed(self.owner, self.fixture)
        self.studio = StudioWorkspace(self.control)
        self.studio.get(self.owner)
        self.output = self.root / 'backup'

    def create(self):
        return backup.create_backup(self.database, self.assets, self.output)

    def rewrite_manifest(self, edit):
        path = self.output / 'manifest.json'
        value = json.loads(path.read_text())
        edit(value)
        raw = (canonical(value) + '\n').encode()
        path.write_bytes(raw)
        (self.output / 'COMPLETE').write_text(hashlib.sha256(raw).hexdigest() + '\n')

    def test_restore_checksums_and_empty_destination_no_overwrite(self):
        manifest = self.create()
        self.assertEqual(len(manifest['files']), 3)
        restored = backup.restore_backup(self.output, self.root / 'restored')
        service = ControlService(restored['database'], restored['assets'])
        self.assertEqual(service.bundle(self.owner, self.project), self.control.bundle(self.owner, self.project))
        for asset in self.control.bundle(self.owner, self.project)['assets']:
            self.assertEqual((Path(restored['assets']) / asset['object_key']).read_bytes(), (self.assets / asset['object_key']).read_bytes())
        with self.assertRaises(ValueError):
            backup.restore_backup(self.output, self.root / 'restored')
        with self.assertRaises(ValueError):
            backup.create_backup(self.database, self.assets, self.output)
        self.assertTrue((self.root / 'restored/RESTORED.json').exists())

    def test_wal_snapshot_is_self_contained_without_sidecar_files(self):
        writer = sqlite3.connect(self.database)
        self.addCleanup(writer.close)
        self.assertEqual(writer.execute('PRAGMA journal_mode=WAL').fetchone()[0], 'wal')
        bundle = self.control.bundle(self.owner, self.project)
        bundle['project']['title'] = 'Committed in WAL'
        writer.execute('UPDATE projects SET bundle=? WHERE id=?', (canonical(bundle), self.project))
        writer.commit()
        self.create()
        restored = backup.restore_backup(self.output, self.root / 'restored-wal')
        self.assertEqual(ControlService(restored['database'], restored['assets']).bundle(self.owner, self.project)['project']['title'],
                         'Committed in WAL')
        self.assertFalse((self.output / 'database.sqlite-wal').exists())
        self.assertFalse((self.output / 'database.sqlite-shm').exists())

    def test_source_updates_after_snapshot_do_not_change_backup(self):
        original = backup._copy
        mutated = False
        def copy_while_service_writes(*args, **kwargs):
            nonlocal mutated
            if not mutated:
                mutated = True
                state = self.studio.get(self.owner)
                state['projects'][0]['bundle']['project']['title'] = 'Title committed after snapshot'
                self.studio.save(self.owner, state, state['revision'])
            return original(*args, **kwargs)
        with patch.object(backup, '_copy', side_effect=copy_while_service_writes):
            self.create()
        restored = backup.restore_backup(self.output, self.root / 'restored')
        bundle = ControlService(restored['database'], restored['assets']).bundle(self.owner, self.project)
        self.assertEqual(bundle['project']['title'], self.fixture['project']['title'])
        self.assertEqual(self.control.bundle(self.owner, self.project)['project']['title'], 'Title committed after snapshot')

    def test_corrupt_database_or_asset_rejected_before_restore(self):
        self.create()
        target = self.root / 'restored'
        db = self.output / backup.DB_NAME
        original = db.read_bytes()
        db.write_bytes(original[:-1] + bytes([original[-1] ^ 1]))
        with self.assertRaises(ValueError):
            backup.restore_backup(self.output, target)
        self.assertFalse(target.exists())
        db.write_bytes(original)
        asset = self.output / 'assets/media/clip.mp4'
        asset.write_bytes(b'corrupt')
        with self.assertRaises(ValueError):
            backup.restore_backup(self.output, target)
        self.assertFalse(target.exists())

    def test_manifest_tamper_traversal_and_unlisted_file(self):
        self.create()
        original = (self.output / 'manifest.json').read_bytes()
        (self.output / 'manifest.json').write_bytes(original + b' ')
        with self.assertRaises(ValueError):
            backup.restore_backup(self.output, self.root / 'restore-1')
        (self.output / 'manifest.json').write_bytes(original)
        self.rewrite_manifest(lambda manifest: manifest['files'][1].update(path='../source.sqlite'))
        with self.assertRaises(ValueError):
            backup.restore_backup(self.output, self.root / 'restore-2')
        (self.output / 'manifest.json').write_bytes(original)
        (self.output / 'COMPLETE').write_text(hashlib.sha256(original).hexdigest() + '\n')
        (self.output / 'extra.txt').write_text('not inventoried')
        with self.assertRaises(ValueError):
            backup.restore_backup(self.output, self.root / 'restore-3')

    def test_symlinks_and_hardlinks_are_not_restored(self):
        self.create()
        path = self.output / 'assets/media/clip.mp4'
        path.unlink()
        path.symlink_to(self.assets / 'media/clip.mp4')
        with self.assertRaises(ValueError):
            backup.restore_backup(self.output, self.root / 'symlink-restore')
        path.unlink()
        os.link(self.assets / 'media/clip.mp4', path)
        with self.assertRaises(ValueError):
            backup.restore_backup(self.output, self.root / 'hardlink-restore')
        target_link = self.root / 'target-link'
        target_link.symlink_to(self.assets, target_is_directory=True)
        with self.assertRaises(ValueError):
            backup.restore_backup(self.output, target_link)

    def test_uncertain_provider_obligations_and_unknown_tables_rejected(self):
        from services.controller.lifecycle import Lifecycle
        from src.wan_platform.fake_provider import FakeGpuProvider
        lifecycle = Lifecycle(self.database, FakeGpuProvider())
        lifecycle.admit(self.project, 'pending', {}, 100, 0)
        with self.assertRaises(ValueError):
            self.create()
        self.assertFalse((self.output / 'COMPLETE').exists())
        with self.control.transaction() as db:
            db.execute('DELETE FROM pod_batches')
            db.execute('CREATE TABLE credentials (secret TEXT)')
        with self.assertRaises(ValueError):
            backup.create_backup(self.database, self.assets, self.root / 'unknown-table-backup')


if __name__ == '__main__':
    unittest.main()
