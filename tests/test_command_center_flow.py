"""Actual fixture worker, durable controller and CPU exporter integration."""
import copy
from datetime import timedelta
import json
from pathlib import Path
import shutil
import subprocess
import tempfile
import unittest
from unittest.mock import patch

from services.controller.service import ControlService
from workers.gpu.common import digest, utcnow
from workers.gpu.worker import run_once
from workers.media.export import export_bundle

ROOT = Path(__file__).resolve().parents[1]


class CommandCenterFlow(unittest.TestCase):
    def test_render_review_export_survives_restart(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            media = root / 'assets'
            shutil.copytree(ROOT / 'fixtures/media', media / 'media')
            source = json.loads((ROOT / 'fixtures/project.json').read_text())
            owner, project = source['project']['owner_id'], source['project']['id']
            db = root / 'controller.sqlite'
            controller = ControlService(db, media)
            controller.seed(owner, source)
            request = copy.deepcopy(source['batches'][0])
            request['deadline_at'] = (utcnow() + timedelta(minutes=2)).isoformat()
            batch = controller.admit(owner, project, request)
            client = controller.worker_client(owner, project, batch['id'], 'fixture-worker')
            claim = client.claim()
            result = run_once(claim, client, media)
            controller = ControlService(db, media)
            client = controller.worker_client(owner, project, batch['id'], 'fixture-worker')
            with patch('workers.gpu.worker.render', side_effect=AssertionError('duplicate render')):
                replay = run_once(claim, client, media)
            self.assertEqual(result['take'], replay['take'])
            self.assertIsNone(client.claim())
            self.assertEqual(len(controller.bundle(owner, project)['takes']), 1)
            with self.assertRaises(KeyError):
                controller.bundle('different-owner', project)
            controller.review(owner, project, result['take']['id'], 'approved')
            timeline = copy.deepcopy(source['timelines'][0])
            timeline['items'][0]['take_id'] = result['take']['id']
            controller.save_timeline(owner, project, timeline)
            bundle = controller.bundle(owner, project)
            export = copy.deepcopy(source['exports'][0])
            bundle['exports'] = [export]
            output = export_bundle(bundle, export['id'], project, media, root / 'jobs')
            target = media / 'projects' / project / 'exports' / 'export-1.mp4'
            target.parent.mkdir(parents=True)
            shutil.copyfile(output, target)
            asset = dict(id='final-export', project_id=project, owner_id=owner,
                         kind='video', object_key=target.relative_to(media).as_posix(),
                         mime_type='video/mp4', bytes=target.stat().st_size,
                         sha256=digest(target), duration_ms=2000)
            export.update(state='succeeded', output_asset_id=asset['id'])
            controller.save_export(owner, project, export, asset)
            saved = ControlService(db, media).bundle(owner, project)
            self.assertEqual(saved['exports'][0]['state'], 'succeeded')
            self.assertEqual(saved['batches'][0]['budget']['spent_cents'], 0)
            self.assertEqual(saved['timelines'][0]['items'][0]['take_id'], result['take']['id'])
            subprocess.run(['ffmpeg', '-v', 'error', '-xerror', '-i', str(target),
                            '-f', 'null', '-'], check=True, timeout=30)
