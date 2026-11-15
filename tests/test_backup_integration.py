"""Independent recovery rehearsal with actual synthetic worker and CPU export."""
import hashlib
import json
from pathlib import Path
import shutil
import subprocess
import tempfile
import unittest

from services.controller.service import ControlService
from services.controller.studio import StudioWorkspace
from services.controller.commands import RenderCommands
from services.controller.media_commands import MediaCommands
from services.controller.runner import FixtureRunner
from services.controller.export_runner import ExportRunner
from services.controller.uploads import ResumableUploads
from workers.gpu.common import digest


class BackupIntegrationTests(unittest.TestCase):
    def test_actual_project_export_and_pending_work_restore(self):
        from services.controller.backup import create_backup, restore_backup
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            repository = Path(__file__).resolve().parents[1]
            source = json.loads((repository / 'fixtures/project.json').read_text())
            assets = root / 'source/assets'
            shutil.copytree(repository / 'fixtures/media', assets / 'media')
            database = root / 'source/state.sqlite'
            control = ControlService(database, assets)
            owner, project = source['project']['owner_id'], source['project']['id']
            control.seed(owner, source)
            studio = StudioWorkspace(control)
            commands, media = RenderCommands(studio), MediaCommands(studio)
            commands.submit(owner, project, {'shot_ids': ['shot-1'], 'expected_revision': 0,
                                             'idempotency_key': 'recovery-render'})
            self.assertTrue(FixtureRunner(control).tick())
            take = control.bundle(owner, project)['takes'][0]
            reviewed = commands.review(owner, project, take['id'], {'decision': 'approved',
                                      'expected_revision': 0, 'idempotency_key': 'recovery-review'})
            timeline = media.assemble(owner, project, {'expected_revision': reviewed['workspace']['revision'],
                                     'audio_asset_id': 'asset-audio', 'idempotency_key': 'recovery-timeline'})['timeline']
            export_payload = {'timeline_id': timeline['id'], 'timeline_revision': timeline['revision'],
                              'idempotency_key': 'recovery-export'}
            first_export = media.export(owner, project, export_payload)['export']
            self.assertTrue(ExportRunner(control).tick())
            original = control.bundle(owner, project)
            completed_asset = next(a for a in original['assets'] if a['id'] == original['exports'][0]['output_asset_id'])
            original_hash = digest(assets / completed_asset['object_key'])
            # Capture a second queued export and an interrupted active render.
            queued = media.export(owner, project, dict(export_payload, idempotency_key='queued-export'))['export']
            second = commands.submit(owner, project, {'shot_ids': ['shot-1'],
                        'expected_revision': studio.get(owner)['revision'], 'idempotency_key': 'interrupted-render'})['batch']
            client = control.worker_client(owner, project, second['id'], 'interrupted-worker')
            claim = client.claim()
            uploads = ResumableUploads(studio)
            pending = uploads.begin(owner, project, {'name': 'Partial.wav', 'mime_type': 'audio/wav',
                        'bytes': 1048577, 'expected_revision': studio.get(owner)['revision'],
                        'idempotency_key': 'pending-upload'})['upload']
            uploads.chunk(owner, project, pending['id'], 0, b'x' * 1048576)
            before = control.bundle(owner, project)
            backup = root / 'backup'
            create_backup(database, assets, backup)
            # Snapshot normalization must not alter the running source.
            self.assertEqual(control.bundle(owner, project), before)
            self.assertEqual(uploads.get(owner, project, pending['id'])['upload']['state'], 'uploading')
            restored_paths = restore_backup(backup, root / 'restored')
            recovered = ControlService(restored_paths['database'], restored_paths['assets'])
            recovered_studio = StudioWorkspace(recovered)
            recovered_bundle = recovered.bundle(owner, project)
            self.assertEqual(recovered_bundle['takes'], before['takes'])
            self.assertEqual(recovered_bundle['timelines'], before['timelines'])
            self.assertEqual(recovered_bundle['reviews'], before['reviews'])
            old_attempt = next(a for a in recovered_bundle['attempts'] if a['id'] == claim['attempt']['id'])
            self.assertEqual(old_attempt['state'], 'failed')
            self.assertEqual(ResumableUploads(recovered_studio).get(owner, project, pending['id'])['upload']['state'], 'aborted')
            with self.assertRaises(KeyError):
                recovered.bundle('foreign-owner', project)
            recovered_assets = Path(restored_paths['assets'])
            self.assertEqual(digest(recovered_assets / completed_asset['object_key']), original_hash)
            self.assertTrue(FixtureRunner(recovered).tick())
            self.assertTrue(ExportRunner(recovered).tick())
            final = recovered.bundle(owner, project)
            self.assertEqual(len(final['takes']), 2)
            self.assertEqual(next(e for e in final['exports'] if e['id'] == queued['id'])['state'], 'succeeded')
            self.assertEqual(next(e for e in final['exports'] if e['id'] == first_export['id'])['state'], 'succeeded')
            for export in final['exports']:
                asset = next(a for a in final['assets'] if a['id'] == export['output_asset_id'])
                subprocess.run(['ffmpeg', '-nostdin', '-v', 'error', '-xerror', '-i',
                                str(recovered_assets / asset['object_key']), '-map', '0', '-f', 'null', '-'],
                               check=True, timeout=20)
            # Replaying original commands after restore returns persisted records.
            self.assertEqual(MediaCommands(recovered_studio).export(owner, project, export_payload)['export']['id'], first_export['id'])
            with self.assertRaises((ValueError, FileExistsError)):
                restore_backup(backup, root / 'restored')
            self.assertEqual(digest(recovered_assets / completed_asset['object_key']), original_hash)
            # A self-consistent marker must not turn an unsafe manifest path into
            # permission to escape the restore destination.
            manifest = json.loads((backup / 'manifest.json').read_text())
            manifest['files'][1]['path'] = 'assets/../../escaped.mp4'
            encoded = json.dumps(manifest).encode()
            (backup / 'manifest.json').write_bytes(encoded)
            (backup / 'COMPLETE').write_text(hashlib.sha256(encoded).hexdigest() + '\n')
            with self.assertRaises(ValueError):
                restore_backup(backup, root / 'unsafe-restore')
            self.assertFalse((root / 'unsafe-restore').exists())
            self.assertFalse((root / 'escaped.mp4').exists())


if __name__ == '__main__':
    unittest.main()
