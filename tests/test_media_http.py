"""TCP upload, timeline and queued CPU export acceptance using synthetic media."""
import base64
import hashlib
from pathlib import Path
import subprocess
import unittest

import test_render_http as harness
from services.controller.service import ControlService
from services.controller.runner import FixtureRunner


class MediaHTTPTests(unittest.TestCase):
    setUp = harness.RenderHTTPTests.setUp
    stop_server = harness.RenderHTTPTests.stop_server
    request = harness.RenderHTTPTests.request
    login = harness.RenderHTTPTests.login
    workspace = harness.RenderHTTPTests.workspace
    admit = harness.RenderHTTPTests.admit

    def upload_payload(self):
        media = Path(__file__).resolve().parents[1] / 'fixtures/media/audio.wav'
        return {'name': 'Fictional soundtrack.wav', 'mime_type': 'audio/wav',
                'data_base64': base64.b64encode(media.read_bytes()).decode(),
                'expected_revision': self.workspace()['revision'], 'idempotency_key': 'soundtrack-1'}

    def post(self, suffix, payload, expected=(200, 201, 202)):
        status, data, _ = self.request('POST', f'/v1/studio/projects/{self.project}/{suffix}', payload, self.cookie)
        self.assertIn(status, expected, data)
        return data

    def test_upload_timeline_export_restart_and_scoped_download(self):
        upload_request = self.upload_payload()
        uploaded = self.post('assets', upload_request)
        asset = uploaded['asset']
        self.assertEqual(asset['owner_id'], self.owner)
        self.assertTrue(asset['object_key'].startswith(f'projects/{self.project}/'))
        self.assertEqual(self.post('assets', upload_request)['asset']['id'], asset['id'])
        self.payload['expected_revision'] = self.workspace()['revision']
        self.admit()
        self.assertTrue(FixtureRunner(self.control).tick())
        workspace = self.workspace()
        take = workspace['projects'][0]['bundle']['takes'][0]
        self.post(f"takes/{take['id']}/review", {'decision': 'approved',
                  'expected_revision': workspace['revision'], 'idempotency_key': 'media-review-1'})
        timeline_request = {'expected_revision': self.workspace()['revision'],
                            'idempotency_key': 'timeline-1', 'audio_asset_id': asset['id']}
        self.post('timelines', dict(timeline_request, audio_asset_id='foreign-asset'), expected=(404, 422))
        self.assertEqual(self.request('POST', f'/v1/studio/projects/{self.project}/timelines',
                                      timeline_request, self.foreign_cookie)[0], 404)
        timeline = self.post('timelines', timeline_request)['timeline']
        self.assertEqual(self.post('timelines', timeline_request)['timeline'], timeline)
        self.assertEqual(timeline['audio'][0]['asset_id'], asset['id'])
        self.post('timelines', dict(timeline_request, expected_revision=self.workspace()['revision'],
                                   idempotency_key='timeline-2'))
        self.assertEqual(self.post('timelines', timeline_request)['timeline'], timeline)
        self.assertEqual(len(self.workspace()['projects'][0]['bundle']['timelines']), 2)
        export_request = {'timeline_id': timeline['id'], 'timeline_revision': timeline['revision'],
                          'idempotency_key': 'export-1'}
        self.assertEqual(self.request('POST', f'/v1/studio/projects/{self.project}/exports',
                                      export_request, self.foreign_cookie)[0], 404)
        export = self.post('exports', export_request)['export']
        self.assertEqual(export['state'], 'queued')
        self.assertEqual(self.post('exports', export_request)['export']['id'], export['id'])
        from services.controller.export_runner import ExportRunner
        # Fresh service/runner reads the queued job from persisted state.
        restarted = ControlService(self.root / 'db.sqlite', self.root / 'assets')
        self.assertTrue(ExportRunner(restarted).tick())
        bundle = self.workspace()['projects'][0]['bundle']
        self.assertEqual(len(bundle['exports']), 1)
        completed = bundle['exports'][0]
        self.assertEqual(completed['state'], 'succeeded', completed)
        self.assertEqual(completed['timeline_revision'], timeline['revision'])
        path = f"/v1/studio/projects/{self.project}/assets/{completed['output_asset_id']}/content"
        status, output, _ = self.request('GET', path, cookie=self.cookie)
        self.assertEqual(status, 200)
        output_asset = next(a for a in bundle['assets'] if a['id'] == completed['output_asset_id'])
        self.assertEqual(hashlib.sha256(output).hexdigest(), output_asset['sha256'])
        self.assertEqual(self.request('GET', path, cookie=self.foreign_cookie)[0], 404)
        source = self.root / 'assets' / asset['object_key']
        self.assertEqual(hashlib.sha256(source.read_bytes()).hexdigest(), asset['sha256'])
        subprocess.run(['ffmpeg', '-nostdin', '-v', 'error', '-xerror', '-i',
                        str(self.root / 'assets' / output_asset['object_key']), '-map', '0',
                        '-f', 'null', '-'], check=True, timeout=20)
        self.assertEqual(self.post('exports', export_request)['export']['id'], export['id'])
        self.assertFalse(ExportRunner(restarted).tick())

    def test_invalid_upload_formats_and_foreign_media_are_rejected(self):
        upload_path = f'/v1/studio/projects/{self.project}/assets'
        payload = self.upload_payload()
        self.assertEqual(self.request('POST', upload_path, payload)[0], 401)
        self.assertEqual(self.request('POST', upload_path, payload, self.foreign_cookie)[0], 404)
        original = self.workspace()
        invalids = [dict(payload, data_base64='not-valid-base64!'),
                    dict(payload, mime_type='text/html'),
                    dict(payload, mime_type='image/png'),
                    dict(payload, data_base64=base64.b64encode(b'#EXTM3U\nhttp://127.0.0.1:9/secret\n').decode())]
        for invalid in invalids:
            with self.subTest(mime=invalid['mime_type']):
                self.assertEqual(self.request('POST', upload_path, invalid, self.cookie)[0], 422)
        self.assertEqual(self.workspace(), original)
        self.post('assets', payload)
        changed = dict(payload, name='Changed name.wav')
        self.assertEqual(self.request('POST', upload_path, changed, self.cookie)[0], 409)
        self.post('timelines', {'expected_revision': self.workspace()['revision'],
                               'idempotency_key': 'foreign-audio', 'audio_asset_id': 'foreign-asset'},
                  expected=(404, 422))
        self.post('exports', {'timeline_id': 'foreign-timeline', 'timeline_revision': 1,
                             'idempotency_key': 'foreign-export'}, expected=(404, 422))


if __name__ == '__main__':
    unittest.main()
