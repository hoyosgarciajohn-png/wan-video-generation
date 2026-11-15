"""Pinned-profile orchestration rehearsal with synthetic media, never Wan inference."""
from copy import deepcopy
from datetime import timedelta
import io
import json
from pathlib import Path
import subprocess
import tempfile
import unittest

from services.controller.service import ControlService, stamp
from services.controller.studio import StudioWorkspace
from services.controller.worker_transport import WorkerTransport
from src.wan_platform.fake_provider import FakeGpuProvider
from workers.gpu.common import digest, probe, utcnow

ROOT = Path(__file__).resolve().parents[1]


class RealJobsIntegrationTests(unittest.TestCase):
    def setUp(self):
        from services.controller.real_jobs import RealJobBridge
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.control = ControlService(self.root / 'state.sqlite', self.root / 'assets')
        self.studio = StudioWorkspace(self.control)
        self.owner = 'fictional-owner'
        state = self.studio.create(self.owner, 'Synthetic pinned-profile rehearsal', 'music_video', 0)
        p = state['projects'][0]
        self.project = p['bundle']['project']['id']
        shot = deepcopy(json.loads((ROOT / 'fixtures/project.json').read_text())['shots'][0])
        shot.update(project_id=self.project, scene_id=p['scenes'][0]['id'], target_duration_ms=1000)
        shot['settings'].update(width=1280, height=704, steps=50, seed=42)
        p['bundle']['shots'].append(shot)
        state = self.studio.save(self.owner, state, state['revision'])
        self.provider = FakeGpuProvider()
        self.bridge = RealJobBridge.for_testing(self.studio, self.provider)
        profile = dict(model_profile=json.loads((ROOT / 'workers/gpu/model.lock.json').read_text())['profile'],
            image_ref='registry.example/wan@sha256:' + 'a'*64, gpu_type='fictional-gpu', gpu_count=1,
            region='fictional-region', worker_endpoint='https://worker.example', storage_id='fictional-store')
        approval = self.bridge.budget.approve(self.owner, self.project,
            dict(currency='USD',approved_cents=100,max_runtime_seconds=120,
                 valid_until=stamp(utcnow()+timedelta(minutes=10)),profile=profile),'fictional-approval')
        self.request = dict(approval_id=approval['id'],shot_ids=[shot['id']],expected_revision=state['revision'],
                            reservation_cents=80,runtime_seconds=120,idempotency_key='test-batch')

    def test_canonical_completion_cleanup_settlement_and_restore(self):
        from services.controller.real_jobs import RealJobBridge
        from services.controller.backup import create_backup, restore_backup
        reply = self.bridge.submit(self.owner, self.project, self.request)
        batch = reply['batch']['id']
        self.assertEqual(reply['batch']['execution_mode'], 'runpod')
        self.assertEqual(reply['budget']['reserved_cents'], 80)
        with self.assertRaises((ValueError, PermissionError)):
            WorkerTransport(self.control).issue(self.owner, self.project, batch, 'remote-worker')
        self.bridge.provision(self.owner, self.project, batch)
        transport = WorkerTransport(self.control, real_jobs=self.bridge)
        credential = transport.issue(self.owner,self.project,batch,'remote-worker',ttl_seconds=300)
        auth = 'Bearer ' + credential['token']
        claim = transport.call(auth,'claim',{})
        attempt = claim['attempt']
        self.assertEqual(claim['batch']['model_profile'], json.loads((ROOT/'workers/gpu/model.lock.json').read_text())['profile'])
        synthetic = self.root / 'synthetic.mp4'
        subprocess.run(['ffmpeg','-nostdin','-v','error','-f','lavfi','-i','color=c=blue:s=1280x704:r=24',
                        '-frames:v','25','-an','-c:v','libx264','-preset','ultrafast','-pix_fmt','yuv420p',str(synthetic)],
                        check=True,timeout=20)
        media = probe(synthetic,attempt['settings'],25)
        data = synthetic.read_bytes()
        receipt = transport.upload(auth,attempt['id'],attempt['lease_id'],digest(synthetic),len(data),io.BytesIO(data))
        asset = dict(id='synthetic-output',project_id=self.project,owner_id=self.owner,kind='video',
            object_key=receipt['object_key'],mime_type='video/mp4',bytes=len(data),sha256=receipt['sha256'],duration_ms=media['duration_ms'])
        payload = dict(lease_id=attempt['lease_id'],output_asset_manifest=dict(asset=asset,media=media))
        take = transport.call(auth,f"attempts/{attempt['id']}/complete",payload)
        self.assertEqual(transport.call(auth,f"attempts/{attempt['id']}/complete",payload),take)
        status = self.bridge.status(self.owner,self.project,batch)
        self.assertEqual(status['batch']['state'],'succeeded')
        self.assertEqual(status['lifecycle']['state'],'succeeded')
        self.assertEqual(status['budget']['unsettled_count'],1)
        with self.assertRaises(ValueError):
            create_backup(self.control.db_path,self.control.asset_root,self.root/'unsafe-backup')
        self.assertEqual(self.bridge.watchdog(),[])
        self.bridge.settle(self.owner,self.project,batch,60,'fictional-bill','settle')
        restart = RealJobBridge.for_testing(StudioWorkspace(ControlService(self.control.db_path,self.control.asset_root)),self.provider)
        status = restart.status(self.owner,self.project,batch)
        self.assertEqual(status['lifecycle']['cleanup'],'confirmed')
        self.assertEqual(status['budget']['spent_cents'],60)
        self.assertEqual(status['budget']['reserved_cents'],0)
        create_backup(self.control.db_path,self.control.asset_root,self.root/'backup')
        restored = restore_backup(self.root/'backup',self.root/'restore')
        recovered = ControlService(restored['database'],restored['assets'])
        self.assertEqual(len(recovered.bundle(self.owner,self.project)['takes']),1)
        subprocess.run(['ffmpeg','-nostdin','-v','error','-xerror','-i',str(Path(restored['assets'])/asset['object_key']),
                        '-f','null','-'],check=True,timeout=20)
        with recovered.transaction() as db:
            self.assertEqual(db.execute('SELECT revoked FROM worker_credentials').fetchone()[0],1)

    def test_revocation_does_not_cancel_but_explicit_cancel_fences(self):
        batch = self.bridge.submit(self.owner,self.project,self.request)['batch']['id']
        self.bridge.provision(self.owner,self.project,batch)
        transport = WorkerTransport(self.control,real_jobs=self.bridge)
        credential = transport.issue(self.owner,self.project,batch,'worker',ttl_seconds=300)
        auth = 'Bearer ' + credential['token']
        self.bridge.budget.revoke(self.owner,self.project,self.request['approval_id'])
        claim = transport.call(auth,'claim',{})
        self.assertIsNotNone(claim)
        self.bridge.cancel(self.owner,self.project,batch)
        attempt = claim['attempt']
        with self.assertRaises((ValueError,PermissionError)):
            transport.call(auth,f"attempts/{attempt['id']}/heartbeat",dict(lease_id=attempt['lease_id'],progress=0.5))
        self.bridge.watchdog()
        status = self.bridge.status(self.owner,self.project,batch)
        self.assertEqual(status['batch']['state'],'canceled')
        self.assertEqual(status['lifecycle']['cleanup'],'confirmed')
        self.assertEqual(status['budget']['unsettled_count'],1)

    def test_deadline_fences_claim_and_reconciles_cleanup(self):
        from workers.gpu.common import timestamp
        batch = self.bridge.submit(self.owner,self.project,self.request)['batch']
        self.bridge.provision(self.owner,self.project,batch['id'])
        transport = WorkerTransport(self.control,real_jobs=self.bridge)
        credential = transport.issue(self.owner,self.project,batch['id'],'worker',ttl_seconds=300)
        self.control.clock = lambda: timestamp(batch['deadline_at']) + timedelta(seconds=1)
        self.assertIsNone(transport.call('Bearer ' + credential['token'],'claim',{}))
        self.bridge.watchdog()
        status = self.bridge.status(self.owner,self.project,batch['id'])
        self.assertEqual(status['batch']['state'],'failed')
        self.assertEqual(status['lifecycle']['cleanup'],'confirmed')
        self.assertEqual(self.control.bundle(self.owner,self.project)['takes'],[])

    def test_default_disarm_cannot_be_replaced_by_preflight_or_boolean(self):
        from services.controller.real_jobs import RealJobBridge
        from services.controller.preflight import evaluate_plan
        disabled = RealJobBridge(self.studio)
        for request in (self.request,dict(self.request,execution_authorized=True),dict(self.request,preflight=evaluate_plan({}))):
            with self.assertRaises((ValueError,PermissionError)):
                disabled.submit(self.owner,self.project,request)
        with self.assertRaises(TypeError):
            RealJobBridge(self.studio,enabled=True)
        with self.assertRaises((ValueError,TypeError)):
            RealJobBridge.for_testing(self.studio,object())
        self.assertEqual(self.control.bundle(self.owner,self.project)['batches'],[])
