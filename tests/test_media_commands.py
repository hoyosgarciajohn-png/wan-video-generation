"""Uploads, immutable assembly and durable CPU export without cloud resources."""
import base64
from copy import deepcopy
import json
from pathlib import Path
import tempfile
import subprocess
import unittest

from services.controller.commands import RenderCommands
from services.controller.export_runner import ExportRunner
from services.controller.media_commands import MediaCommands
from services.controller.runner import FixtureRunner
from services.controller.service import ControlService, canonical
from services.controller.studio import StudioWorkspace, StudioConflict

ROOT = Path(__file__).resolve().parents[1]


class MediaCommandTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.control = ControlService(self.root / 'state.sqlite', self.root / 'assets')
        self.studio = StudioWorkspace(self.control)
        self.media = MediaCommands(self.studio)
        self.owner = 'owner-a'
        self.state = self.studio.create(self.owner, 'Film', 'music_video', 0)
        self.project = self.state['projects'][0]['bundle']['project']['id']
        self.audio_request = dict(name='Original test audio', mime_type='audio/wav',
                                 data_base64=base64.b64encode((ROOT / 'fixtures/media/audio.wav').read_bytes()).decode(),
                                 expected_revision=self.state['revision'], idempotency_key='upload-1')

    def ready(self):
        uploaded = self.media.upload(self.owner, self.project, self.audio_request)
        state = uploaded['workspace']
        p = state['projects'][0]
        shot = deepcopy(json.loads((ROOT / 'fixtures/project.json').read_text())['shots'][0])
        shot.update(project_id=self.project, scene_id=p['scenes'][0]['id'])
        p['bundle']['shots'].append(shot)
        state = self.studio.save(self.owner, state, state['revision'])
        commands = RenderCommands(self.studio)
        commands.submit(self.owner, self.project, dict(shot_ids=[shot['id']], expected_revision=state['revision'], idempotency_key='render'))
        self.assertTrue(FixtureRunner(self.control).tick())
        take = self.control.bundle(self.owner, self.project)['takes'][0]
        reviewed = commands.review(self.owner, self.project, take['id'],
                                   dict(decision='approved', expected_revision=state['revision'], idempotency_key='approve'))
        return uploaded['asset'], take, reviewed['workspace']

    def test_upload_verified_and_idempotent_after_restart(self):
        reply = self.media.upload(self.owner, self.project, self.audio_request)
        self.assertEqual(reply['asset']['duration_ms'], 2000)
        self.assertEqual(reply['workspace']['revision'], self.state['revision'] + 1)
        self.assertEqual(reply['workspace']['projects'][0]['assetNames'][reply['asset']['id']], self.audio_request['name'])
        restarted = MediaCommands(StudioWorkspace(ControlService(self.root / 'state.sqlite', self.root / 'assets')))
        self.assertEqual(restarted.upload(self.owner, self.project, self.audio_request)['asset'], reply['asset'])
        with self.assertRaises(StudioConflict):
            restarted.upload(self.owner, self.project, dict(self.audio_request, name='different'))
        with self.control.transaction() as db:
            receipt = db.execute("SELECT request FROM command_receipts WHERE operation='asset'").fetchone()[0]
        self.assertNotIn('data_base64', receipt)
        self.assertIn(reply['asset']['sha256'], receipt)
        self.assertEqual(list((self.root / 'assets/.staging').iterdir()), [])

    def test_all_supported_image_formats_and_dimension_limit(self):
        revision = self.state['revision']
        for suffix, mime in (('png', 'image/png'), ('jpg', 'image/jpeg'), ('webp', 'image/webp')):
            image = self.root / ('reference.' + suffix)
            subprocess.run(['ffmpeg', '-nostdin', '-v', 'error', '-y', '-i',
                            str(ROOT / 'fixtures/media/clip.mp4'), '-frames:v', '1',
                            '-threads', '1', str(image)], check=True)
            payload = dict(name='Reference', mime_type=mime, data_base64=base64.b64encode(image.read_bytes()).decode(),
                           expected_revision=revision, idempotency_key='image-' + suffix)
            result = self.media.upload(self.owner, self.project, payload)
            self.assertEqual(result['asset']['kind'], 'image')
            self.assertIsNone(result['asset']['duration_ms'])
            revision = result['workspace']['revision']
        oversized = self.root / 'wide.png'
        subprocess.run(['ffmpeg', '-nostdin', '-v', 'error', '-y', '-f', 'lavfi', '-i',
                        'color=c=blue:s=4098x2', '-frames:v', '1', '-threads', '1', str(oversized)], check=True)
        with self.assertRaises(ValueError):
            self.media.upload(self.owner, self.project, dict(name='Too wide', mime_type='image/png',
                              data_base64=base64.b64encode(oversized.read_bytes()).decode(),
                              expected_revision=revision, idempotency_key='oversized'))

    def test_upload_rejects_bad_signature_payload_and_cross_owner(self):
        for data, mime in ((b'#EXTM3U\nfile:///etc/passwd', 'audio/wav'), (b'not-a-png','image/png'),
                           ((ROOT / 'fixtures/media/audio.wav').read_bytes(), 'image/png')):
            with self.subTest(mime=mime), self.assertRaises(ValueError):
                self.media.upload(self.owner, self.project, dict(self.audio_request, mime_type=mime,
                                  data_base64=base64.b64encode(data).decode()))
        for changes in ({'data_base64':'%%%%'}, {'mime_type':'text/plain'}, {'data_base64':'A' * (6 * 1024 * 1024)}):
            with self.subTest(changes=list(changes)), self.assertRaises(ValueError):
                self.media.upload(self.owner, self.project, dict(self.audio_request, **changes))
        with self.assertRaises(KeyError):
            self.media.upload('owner-b', self.project, self.audio_request)
        self.assertEqual(self.control.bundle(self.owner, self.project)['assets'], [])
        self.assertEqual(self.studio.get(self.owner)['revision'], self.state['revision'])

    def test_timeline_revision_replay_and_export_resume_frozen_snapshot(self):
        audio, take, state = self.ready()
        request = dict(expected_revision=state['revision'], idempotency_key='timeline-1', audio_asset_id=audio['id'])
        first = self.media.assemble(self.owner, self.project, request)
        second = self.media.assemble(self.owner, self.project, dict(request, expected_revision=first['workspace']['revision'], idempotency_key='timeline-2'))
        self.assertEqual(first['timeline']['id'], second['timeline']['id'])
        self.assertEqual(second['timeline']['revision'], 2)
        self.assertEqual(self.media.assemble(self.owner, self.project, request)['timeline'], first['timeline'])
        export_request = dict(timeline_id=first['timeline']['id'], timeline_revision=1, idempotency_key='export-1')
        queued = self.media.export(self.owner, self.project, export_request)
        def interrupted(*args):
            raise SystemExit('simulated process exit')
        with self.assertRaises(SystemExit):
            ExportRunner(self.control, renderer=interrupted).tick()
        # A later rejection does not change the approval snapshot captured at queue.
        RenderCommands(self.studio).review(self.owner, self.project, take['id'],
            dict(decision='rejected', expected_revision=second['workspace']['revision'], idempotency_key='reject'))
        restarted = ControlService(self.root / 'state.sqlite', self.root / 'assets')
        self.assertTrue(ExportRunner(restarted).tick())
        bundle = restarted.bundle(self.owner, self.project)
        job = bundle['exports'][0]
        self.assertEqual(job['state'], 'succeeded')
        self.assertEqual(job['id'], queued['export']['id'])
        output = next(a for a in bundle['assets'] if a['id'] == job['output_asset_id'])
        self.assertTrue((self.root / 'assets' / output['object_key']).is_file())
        self.assertEqual(self.media.export(self.owner, self.project, export_request)['export'], job)
        self.assertFalse(ExportRunner(restarted).tick())
        self.assertEqual(len([a for a in bundle['assets'] if a['id'] == output['id']]), 1)

    def test_hd_export_and_legacy_snapshot_keep_their_own_resolution(self):
        audio, take, state = self.ready()
        assembled = self.media.assemble(self.owner, self.project, dict(
            expected_revision=state['revision'], idempotency_key='hd-timeline', audio_asset_id=audio['id']))
        request = dict(timeline_id=assembled['timeline']['id'], timeline_revision=1, idempotency_key='hd-export')
        queued = self.media.export(self.owner, self.project, request)['export']
        self.assertEqual((queued['profile']['width'],queued['profile']['height']),(1280,704))
        self.assertTrue(ExportRunner(self.control).tick())
        bundle = self.control.bundle(self.owner,self.project)
        output = next(a for a in bundle['assets'] if a['id']==bundle['exports'][0]['output_asset_id'])
        path=self.control.asset_root/output['object_key']
        ExportRunner.verify(path,assembled['timeline'],queued['profile'])
        legacy=deepcopy(queued['profile']); legacy.update(width=320,height=180)
        with self.assertRaises(ValueError): ExportRunner.verify(path,assembled['timeline'],legacy)
        subprocess.run(['ffmpeg','-nostdin','-v','error','-xerror','-i',str(path),'-f','null','-'],check=True)
        # Simulate an old persisted queued job; upgrading must not rewrite it.
        old=self.media.export(self.owner,self.project,dict(request,idempotency_key='old-queued'))['export']
        with self.control.transaction() as db:
            saved=self.control._load(db,self.owner,self.project)
            next(e for e in saved['exports'] if e['id']==old['id'])['profile']=legacy
            self.control._save(db,saved)
            db.execute('UPDATE export_jobs SET snapshot=? WHERE id=?',(canonical(saved),old['id']))
        self.assertTrue(ExportRunner(self.control).tick())
        bundle=self.control.bundle(self.owner,self.project)
        old_job=next(e for e in bundle['exports'] if e['id']==old['id'])
        self.assertEqual(old_job['state'],'succeeded')
        output=next(a for a in bundle['assets'] if a['id']==old_job['output_asset_id'])
        ExportRunner.verify(self.control.asset_root/output['object_key'],assembled['timeline'],legacy)
        with self.assertRaises(ValueError):
            ExportRunner.verify(self.control.asset_root/output['object_key'],assembled['timeline'],queued['profile'])

    def test_assembly_requires_selection_and_export_project_scope(self):
        with self.assertRaises(ValueError):
            self.media.assemble(self.owner, self.project,
                                dict(expected_revision=self.state['revision'], idempotency_key='empty', audio_asset_id=None))
        audio, take, state = self.ready()
        with self.assertRaises(KeyError):
            self.media.assemble(self.owner, self.project,
                                dict(expected_revision=state['revision'], idempotency_key='foreign-audio', audio_asset_id='foreign'))
        assembled = self.media.assemble(self.owner, self.project,
                                       dict(expected_revision=state['revision'], idempotency_key='silent', audio_asset_id=None))
        request = dict(timeline_id=assembled['timeline']['id'], timeline_revision=1, idempotency_key='export')
        with self.assertRaises(KeyError):
            self.media.export('other-owner', self.project, request)
        with self.assertRaises(KeyError):
            self.media.export(self.owner, self.project, dict(request, timeline_revision=999))
        self.media.export(self.owner, self.project, request)
        with self.assertRaises(StudioConflict):
            self.media.export(self.owner, self.project, dict(request, timeline_revision=2))
        def invalid_output(*args):
            path = self.root / 'invalid.mp4'
            path.write_bytes(b'not video')
            return path
        runner = ExportRunner(self.control, renderer=invalid_output)
        self.assertTrue(runner.tick())
        self.assertEqual(runner.last_error, 'export_failed')
        job = self.control.bundle(self.owner, self.project)['exports'][0]
        self.assertEqual(job['state'], 'failed')
        self.assertIsNone(job['output_asset_id'])


if __name__ == '__main__':
    unittest.main()
