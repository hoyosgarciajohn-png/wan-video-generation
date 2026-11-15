"""Private credential scope and immutable fixture artifact transfer boundaries."""
from concurrent.futures import ThreadPoolExecutor
from copy import deepcopy
from datetime import timedelta
import hashlib
import io
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from services.controller.commands import RenderCommands
from services.controller.service import ControlService
from services.controller.studio import StudioWorkspace
from services.controller.worker_transport import WorkerTransport, WorkerAccessError
from workers.gpu.common import utcnow

ROOT = Path(__file__).resolve().parents[1]


class WorkerTransportTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.now = utcnow()
        self.control = ControlService(self.root / 'state.sqlite', self.root / 'assets', clock=lambda: self.now)
        self.studio = StudioWorkspace(self.control)
        self.owner = 'owner-a'
        state = self.studio.create(self.owner, 'Remote fixture', 'music_video', 0)
        p = state['projects'][0]
        self.project = p['bundle']['project']['id']
        fixture = json.loads((ROOT / 'fixtures/project.json').read_text())
        shot = deepcopy(fixture['shots'][0])
        shot.update(project_id=self.project, scene_id=p['scenes'][0]['id'])
        p['bundle']['shots'].append(shot)
        state = self.studio.save(self.owner, state, state['revision'])
        self.batch = RenderCommands(self.studio).submit(self.owner, self.project,
            dict(shot_ids=[shot['id']], expected_revision=state['revision'], idempotency_key='render'))['batch']['id']
        self.transport = WorkerTransport(self.control)
        self.credential = self.transport.issue(self.owner, self.project, self.batch, 'worker-a', ttl_seconds=300)
        self.auth = 'Bearer ' + self.credential['token']
        self.bytes = (ROOT / 'fixtures/media/clip.mp4').read_bytes()
        self.checksum = hashlib.sha256(self.bytes).hexdigest()
        self.media = {k: fixture['takes'][0][k] for k in ('duration_ms','width','height','frame_rate')}

    def claim(self, auth=None):
        return self.transport.call(auth or self.auth, 'claim', {})

    def upload(self, claim, auth=None):
        a = claim['attempt']
        return self.transport.upload(auth or self.auth, a['id'], a['lease_id'], self.checksum, len(self.bytes), io.BytesIO(self.bytes))

    def manifest(self, claim):
        a = claim['attempt']
        return dict(asset=dict(id='output-' + a['id'], project_id=self.project, owner_id=self.owner,
                              kind='video', object_key=f"projects/{self.project}/attempts/{a['id']}/output.mp4",
                              mime_type='video/mp4', bytes=len(self.bytes), sha256=self.checksum, duration_ms=self.media['duration_ms']),
                    media=deepcopy(self.media))

    def complete(self, claim, auth=None):
        a = claim['attempt']
        return self.transport.call(auth or self.auth, f"attempts/{a['id']}/complete",
                dict(lease_id=a['lease_id'], output_asset_manifest=self.manifest(claim)))

    def test_hash_only_credentials_scope_expiry_and_revocation(self):
        with self.control.transaction() as db:
            row = db.execute('SELECT token_hash,owner,project,batch,worker FROM worker_credentials').fetchone()
        self.assertEqual(row[0], hashlib.sha256(self.credential['token'].encode()).hexdigest())
        self.assertNotEqual(row[0], self.credential['token'])
        with self.assertRaises(KeyError):
            self.transport.issue('other-owner', self.project, self.batch, 'worker')
        self.transport.revoke(self.owner, self.project, self.credential['id'])
        with self.assertRaises(WorkerAccessError) as error:
            self.claim()
        self.assertEqual(error.exception.status, 401)
        fresh = self.transport.issue(self.owner, self.project, self.batch, 'worker-a', ttl_seconds=1)
        self.now += timedelta(seconds=2)
        with self.assertRaises(WorkerAccessError) as error:
            self.claim('Bearer ' + fresh['token'])
        self.assertEqual(error.exception.status, 401)

    def test_claim_replay_concurrency_and_expired_attempt_replacement(self):
        with ThreadPoolExecutor(max_workers=3) as pool:
            claims = list(pool.map(lambda _: self.claim(), range(3)))
        self.assertEqual(len({c['attempt']['id'] for c in claims}), 1)
        other = self.transport.issue(self.owner, self.project, self.batch, 'worker-b')
        self.assertIsNone(self.claim('Bearer ' + other['token']))
        first = claims[0]
        self.now += timedelta(seconds=31)
        second = self.claim()
        self.assertNotEqual(second['attempt']['id'], first['attempt']['id'])
        with self.assertRaises(WorkerAccessError):
            self.upload(first)

    def test_upload_replay_immutable_content_and_independent_completion(self):
        claim = self.claim()
        result = self.upload(claim)
        self.assertEqual(result, self.upload(claim))
        malformed = self.manifest(claim)
        malformed['media']['width'] = 640
        with self.assertRaises(WorkerAccessError):
            self.transport.call(self.auth, f"attempts/{claim['attempt']['id']}/complete",
                 dict(lease_id=claim['attempt']['lease_id'], output_asset_manifest=malformed))
        take = self.complete(claim)
        self.now += timedelta(seconds=31)
        self.assertEqual(self.complete(claim), take)
        self.assertEqual(len(self.control.bundle(self.owner, self.project)['takes']), 1)
        self.assertEqual(list((self.root / 'assets/.worker-staging').iterdir()), [])

    def test_stream_expiry_cleanup_and_non_mp4_rejection(self):
        claim = self.claim()
        credential = self.transport.issue(self.owner, self.project, self.batch, 'worker-a', ttl_seconds=1)
        class Expiring(io.BytesIO):
            def read(inner, amount=-1):
                chunk = super(Expiring, inner).read(amount)
                self.now += timedelta(seconds=2)
                return chunk
        with self.assertRaises(WorkerAccessError) as error:
            self.transport.upload('Bearer ' + credential['token'], claim['attempt']['id'], claim['attempt']['lease_id'],
                                  self.checksum, len(self.bytes), Expiring(self.bytes))
        self.assertEqual(error.exception.status, 401)
        path = self.root / 'assets' / self.manifest(claim)['asset']['object_key']
        self.assertFalse(path.exists())
        playlist = b'#EXTM3U\nfile:///etc/passwd\n'
        with self.assertRaises(ValueError):
            self.transport.upload(self.auth, claim['attempt']['id'], claim['attempt']['lease_id'],
                                  hashlib.sha256(playlist).hexdigest(), len(playlist), io.BytesIO(playlist))
        self.assertFalse(path.exists())
        self.assertEqual(list((self.root / 'assets/.worker-staging').iterdir()), [])

    def test_expiry_during_media_probe_rolls_back_commit(self):
        import services.controller.service as service_module
        claim = self.claim()
        self.upload(claim)
        credential = self.transport.issue(self.owner, self.project, self.batch, 'worker-a', ttl_seconds=1)
        original = service_module.probe
        def slow_probe(*args):
            result = original(*args)
            self.now += timedelta(seconds=2)
            return result
        with patch.object(service_module, 'probe', side_effect=slow_probe):
            with self.assertRaises(WorkerAccessError) as error:
                self.complete(claim, 'Bearer ' + credential['token'])
        self.assertEqual(error.exception.status, 401)
        bundle = self.control.bundle(self.owner, self.project)
        self.assertEqual(bundle['takes'], [])
        self.assertEqual(bundle['assets'], [])
        self.assertEqual(bundle['attempts'][0]['state'], 'claimed')
        with self.control.transaction() as db:
            self.assertEqual(db.execute('SELECT count(*) FROM completions').fetchone()[0], 0)
        self.assertEqual(self.complete(claim)['attempt_id'], claim['attempt']['id'])


if __name__ == '__main__':
    unittest.main()
