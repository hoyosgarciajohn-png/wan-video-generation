"""Bounded resumable uploads, durable receipts and stage cleanup."""
from copy import deepcopy
from datetime import timedelta
import hashlib
import json
from pathlib import Path
import tempfile
import unittest

from services.controller.service import ControlService
from services.controller.studio import StudioWorkspace, StudioConflict
from services.controller.uploads import ResumableUploads, CHUNK_SIZE, UploadExpired, UploadCapacity
from workers.gpu.common import utcnow

ROOT = Path(__file__).resolve().parents[1]


class UploadTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.control = ControlService(self.root / 'state.sqlite', self.root / 'assets')
        self.studio = StudioWorkspace(self.control)
        self.uploads = ResumableUploads(self.studio)
        self.owner = 'owner-a'
        self.state = self.studio.create(self.owner, 'Upload project', 'music_video', 0)
        self.project = self.state['projects'][0]['bundle']['project']['id']
        self.wav = (ROOT / 'fixtures/media/audio.wav').read_bytes()
        self.request = dict(name='Original.wav', mime_type='audio/wav', bytes=len(self.wav),
                            expected_revision=self.state['revision'], idempotency_key='upload-a')

    def begin(self, request=None):
        return self.uploads.begin(self.owner, self.project, request or self.request)['upload']

    def test_finish_restart_receipt_preserves_concurrent_creator_edit(self):
        upload = self.begin()
        checksum = hashlib.sha256(self.wav).hexdigest()
        reply = self.uploads.chunk(self.owner, self.project, upload['id'], 0, self.wav)
        self.assertEqual(reply['upload']['chunk_sha256'], [checksum])
        state = deepcopy(self.state)
        state['projects'][0]['script'] = 'A creator edit while upload is in progress.'
        self.studio.save(self.owner, state, state['revision'])
        restarted = ResumableUploads(StudioWorkspace(ControlService(self.root / 'state.sqlite', self.root / 'assets')))
        result = restarted.finish(self.owner, self.project, upload['id'], dict(chunk_sha256=[checksum]))
        self.assertEqual(result['asset']['sha256'], checksum)
        self.assertEqual(result['asset']['bytes'], len(self.wav))
        self.assertEqual(result['workspace']['revision'], self.state['revision'] + 2)
        self.assertEqual(result['workspace']['projects'][0]['script'], state['projects'][0]['script'])
        self.assertEqual(restarted.finish(self.owner, self.project, upload['id'], dict(chunk_sha256=[checksum])), result)
        self.assertEqual(restarted.begin(self.owner, self.project, self.request)['upload']['state'], 'completed')
        self.assertFalse((self.root / 'assets/.uploads' / upload['id']).exists())
        with self.assertRaises(StudioConflict):
            restarted.finish(self.owner, self.project, upload['id'], dict(chunk_sha256=['0' * 64]))
        with self.assertRaises(StudioConflict):
            restarted.begin(self.owner, self.project, dict(self.request, name='Different.wav'))

    def test_sequential_chunks_exact_size_conflicts_and_incomplete_finish(self):
        upload = self.begin(dict(self.request, bytes=CHUNK_SIZE + 5))
        with self.assertRaises(StudioConflict):
            self.uploads.chunk(self.owner, self.project, upload['id'], 1, b'12345')
        with self.assertRaises(ValueError):
            self.uploads.chunk(self.owner, self.project, upload['id'], 0, b'short')
        first = b'a' * CHUNK_SIZE
        self.uploads.chunk(self.owner, self.project, upload['id'], 0, first)
        self.uploads.chunk(self.owner, self.project, upload['id'], 0, first)
        with self.assertRaises(StudioConflict):
            self.uploads.chunk(self.owner, self.project, upload['id'], 0, b'b' * CHUNK_SIZE)
        with self.assertRaises(ValueError):
            self.uploads.finish(self.owner, self.project, upload['id'], dict(chunk_sha256=[hashlib.sha256(first).hexdigest()]))
        with self.assertRaises(ValueError):
            self.uploads.chunk(self.owner, self.project, upload['id'], 1, b'123456')
        self.uploads.chunk(self.owner, self.project, upload['id'], 1, b'12345')
        self.assertEqual(self.uploads.get(self.owner, self.project, upload['id'])['upload']['received_bytes'], CHUNK_SIZE + 5)

    def test_staged_corruption_and_interrupted_chunk_write(self):
        upload = self.begin()
        directory = self.root / 'assets/.uploads' / upload['id']
        directory.mkdir()
        (directory / '000.chunk').write_bytes(self.wav)  # published before DB commit
        self.uploads.chunk(self.owner, self.project, upload['id'], 0, self.wav)
        (directory / '000.chunk').write_bytes(b'changed bytes')
        with self.assertRaises(ValueError):
            self.uploads.finish(self.owner, self.project, upload['id'],
                                dict(chunk_sha256=[hashlib.sha256(self.wav).hexdigest()]))
        self.assertEqual(self.control.bundle(self.owner, self.project)['assets'], [])
        self.uploads.abort(self.owner, self.project, upload['id'])
        self.assertFalse(directory.exists())

    def test_expiry_abort_cleanup_and_owner_isolation(self):
        upload = self.begin()
        self.uploads.chunk(self.owner, self.project, upload['id'], 0, self.wav)
        with self.assertRaises(KeyError):
            self.uploads.get('other-owner', self.project, upload['id'])
        with self.assertRaises(KeyError):
            self.uploads.chunk('other-owner', self.project, upload['id'], 0, self.wav)
        with self.assertRaises(KeyError):
            self.uploads.abort('other-owner', self.project, upload['id'])
        future = utcnow() + timedelta(hours=25)
        restarted = ResumableUploads(StudioWorkspace(ControlService(self.root / 'state.sqlite', self.root / 'assets', clock=lambda: future)))
        self.assertEqual(restarted.get(self.owner, self.project, upload['id'])['upload']['state'], 'expired')
        self.assertFalse((self.root / 'assets/.uploads' / upload['id']).exists())
        with self.assertRaises(UploadExpired):
            restarted.chunk(self.owner, self.project, upload['id'], 0, self.wav)
        fresh = self.begin(dict(self.request, idempotency_key='fresh'))
        self.uploads.abort(self.owner, self.project, fresh['id'])
        self.assertEqual(self.uploads.abort(self.owner, self.project, fresh['id'])['upload']['state'], 'aborted')
        with self.assertRaises(StudioConflict):
            self.uploads.chunk(self.owner, self.project, fresh['id'], 0, self.wav)

    def test_restart_removes_terminal_staging_and_uncommitted_publication(self):
        upload = self.begin()
        self.uploads.chunk(self.owner, self.project, upload['id'], 0, self.wav)
        result = self.uploads.finish(self.owner, self.project, upload['id'],
                                     dict(chunk_sha256=[hashlib.sha256(self.wav).hexdigest()]))
        directory = self.root / 'assets/.uploads' / upload['id']
        directory.mkdir()
        (directory / 'verified-input').write_bytes(self.wav)  # crash after DB commit, before cleanup
        ResumableUploads(self.studio)
        self.assertFalse(directory.exists())
        self.assertTrue((self.root / 'assets' / result['asset']['object_key']).exists())
        fresh = self.begin(dict(self.request, expected_revision=result['workspace']['revision'], idempotency_key='orphan'))
        orphan = self.root / 'assets' / f"projects/{self.project}/uploads/asset-{fresh['id']}.wav"
        orphan.write_bytes(self.wav)  # crash before corresponding asset DB commit
        with self.control.transaction() as db:
            db.execute("UPDATE upload_sessions SET state='aborted' WHERE id=?", (fresh['id'],))
        ResumableUploads(self.studio)
        self.assertFalse(orphan.exists())
        self.assertEqual(len(self.control.bundle(self.owner, self.project)['assets']), 1)

    def test_caps_active_session_bound_and_no_full_body_storage(self):
        for changed in ({'bytes':128 * CHUNK_SIZE + 1}, {'bytes':True},
                        {'bytes':CHUNK_SIZE + 1, 'mime_type':'image/png'}):
            with self.subTest(changed=changed), self.assertRaises(ValueError):
                self.begin(dict(self.request, **changed))
        for index in range(4):
            self.begin(dict(self.request, idempotency_key=f'active-{index}'))
        with self.assertRaises(UploadCapacity):
            self.begin(dict(self.request, idempotency_key='overflow'))
        with self.control.transaction() as db:
            requests = db.execute('SELECT request FROM upload_sessions').fetchall()
        self.assertEqual(len(requests), 4)
        self.assertTrue(all(len(row[0]) < 500 for row in requests))


if __name__ == '__main__':
    unittest.main()
