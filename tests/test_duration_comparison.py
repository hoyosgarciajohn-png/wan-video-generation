"""Fictional two-duration live-scope rehearsal; no cloud credentials or GPU use."""
from copy import deepcopy
from datetime import timedelta
import io
import json
from pathlib import Path
import subprocess
import unittest
from unittest.mock import patch

from tests import test_live_admission
from tests.test_live_execution import HTTP
from services.controller.live_admission import HOST_DOMAIN, configuration_hash
from services.controller.live_execution import LiveExecution, COMPARISON_CMD, BOOTSTRAP_ENTRYPOINT
from services.controller.allocation_retry import POLICY
from services.controller.worker_transport import WorkerTransport, WorkerAccessError
from services.controller import backup
from workers.gpu.common import frame_count, validate_claim, utcnow, digest
from workers.gpu.comparison import policy, PROMPT, SETTINGS, GPU, continuation_gate
from workers.gpu.worker import run_once
from workers.gpu.cli import remote_run


class DurationComparisonTests(unittest.TestCase):
    signed=test_live_admission.LiveAdmissionTests.signed
    def setUp(self):
        test_live_admission.LiveAdmissionTests.setUp(self)
        self.control.max_attempts=1
        workspace=self.studio.get(self.owner)
        project=next(p for p in workspace['projects'] if p['bundle']['project']['id']==self.project)
        first=deepcopy(project['bundle']['shots'][0])
        first.update(id='duration-05',prompt=PROMPT,target_duration_ms=5000,settings=deepcopy(SETTINGS),reference_asset_ids=[])
        second=deepcopy(first);second.update(id='duration-15',target_duration_ms=15000)
        project['bundle']['shots'].extend([first,second])
        workspace=self.studio.save(self.owner,workspace,workspace['revision'])
        self.profile.update(gpu_type=GPU)
        self.payload.update(approved_cents=400,max_runtime_seconds=2700,valid_until=(utcnow()+timedelta(hours=2)).isoformat(),capacity_retry=dict(POLICY),
                            duration_comparison=policy(['duration-05','duration-15'],self.profile['image_ref']))
        self.payload['launch_profile'].update(gpu={'id':GPU,'count':1},cmd=COMPARISON_CMD,entrypoint=BOOTSTRAP_ENTRYPOINT)
        self.live.approve(self.owner,self.project,self.signed())
        self.request.update(shot_ids=['duration-05','duration-15'],runtime_seconds=2700,reservation_cents=400,expected_revision=workspace['revision'])
        self.job=self.live.submit(self.owner,self.project,self.request)['batch']['id']
        self.http=HTTP()
        self.live._host_keys={'fictional':(self.owner,self.secret)}
        self.live._build_evidence='fictional'
        self.execution=LiveExecution(self.live,runpod_token='fictional',transport=self.http,candidate_check=lambda *a:True)
        self.workers=WorkerTransport(self.control,real_jobs=self.execution)
        token=self.workers.issue(self.owner,self.project,self.job,'comparison-worker',ttl_seconds=3000)['token']
        self.auth='Bearer '+token
        host=dict(owner=self.owner,project=self.project,config_hash=configuration_hash(self.profile,self.payload['launch_profile'],None,self.payload['duration_comparison']),
                  source_sha256=self.payload['source_sha256'],build_manifest_sha256='a'*64,valid_until=self.payload['valid_until'],
                  worker_endpoint=self.profile['worker_endpoint'],storage_id=self.profile['storage_id'])
        with patch('services.controller.live_admission._build',return_value={'manifest_sha256':'a'*64}):
            self.execution.provision(self.owner,self.project,self.job,self.signed(host,HOST_DOMAIN),worker_token=token)
        outer=self
        class Client:
            binding='fictional-comparison-session'
            def claim(self):return outer.workers.call(outer.auth,'claim',{})
            def heartbeat(self,a,p):return outer.workers.call(outer.auth,f"attempts/{a['id']}/heartbeat",dict(lease_id=a['lease_id'],progress=p))
            def fail(self,a,code):return outer.workers.call(outer.auth,f"attempts/{a['id']}/fail",dict(lease_id=a['lease_id'],code=code))
            def telemetry(self,a,m):return outer.workers.call(outer.auth,f"attempts/{a['id']}/telemetry",dict(lease_id=a['lease_id'],metrics=m))
            def complete(self,a,m):return outer.workers.call(outer.auth,f"attempts/{a['id']}/complete",dict(lease_id=a['lease_id'],output_asset_manifest=m))
            def upload(self,a,m,p):
                with open(p,'rb') as source:return outer.workers.upload(outer.auth,a['id'],a['lease_id'],m['asset']['sha256'],m['asset']['bytes'],source)
        self.client=Client()
        self.worker_root=self.control.asset_root.parent/'fictional-worker'
        self.render_patch=patch('workers.gpu.worker.render',side_effect=self.render)
        self.render_patch.start();self.addCleanup(self.render_patch.stop)
    def render(self,claim,path,*args):
        subprocess.run(['ffmpeg','-v','error','-nostdin','-y','-f','lavfi','-i','color=c=blue:s=1280x704:r=24',
                        '-frames:v',str(frame_count(claim['shot_snapshot'],'runpod')),'-an','-c:v','libx264','-threads','1',
                        '-pix_fmt','yuv420p','-movflags','+faststart',str(path)],check=True)
        return dict(gpu_name=GPU,gpu_total_bytes=80*1024**3,driver_version='570.0',model_load_seconds=10,
                    generation_seconds=20,decode_encode_seconds=2,gpu_peak_allocated_bytes=10*1024**3,
                    gpu_peak_reserved_bytes=12*1024**3,gpu_model_loaded_reserved_bytes=2*1024**3,
                    torch_version='2.8.0+cu128',cuda_version='12.8',memory_policy='sequential-gpu-text-bf16-vae-v1',
                    model_profile=deepcopy(claim['batch']['model_profile']))
    def run_first(self):
        claim=self.client.claim()
        return claim,run_once(claim,self.client,self.worker_root)
    def test_order_telemetry_completion_and_cleanup_survive_restart(self):
        claim,first=self.run_first()
        self.assertEqual(claim['shot_snapshot']['target_duration_ms'],5000)
        with self.control.transaction() as db:
            self.assertEqual(db.execute('SELECT count(*) FROM worker_telemetry').fetchone()[0],1)
        next_claim=self.client.claim()
        self.assertEqual(next_claim['shot_snapshot']['target_duration_ms'],15000)
        validate_claim(next_claim)
        ordinary=deepcopy(next_claim);ordinary.pop('duration_comparison')
        with self.assertRaises(ValueError):validate_claim(ordinary)
        second=run_once(next_claim,self.client,self.worker_root)
        self.assertNotEqual(first['asset']['id'],second['asset']['id'])
        self.assertEqual(self.execution.status(self.owner,self.project,self.job)['batch']['state'],'succeeded')
        self.assertEqual(self.execution.watchdog(),[])
        self.assertEqual(self.http.posts,1)
        self.assertEqual(self.http.pods,{})
        self.assertIsNone(self.client.claim())
        destination=self.control.asset_root.parent/'comparison-backup'
        backup.create_backup(self.control.db_path,self.control.asset_root,destination)
        restored=backup.restore_backup(destination,self.control.asset_root.parent/'comparison-restored')
        import sqlite3
        with sqlite3.connect(restored['database']) as db:
            self.assertEqual(db.execute('SELECT count(*) FROM worker_telemetry').fetchone()[0],2)
    def test_lost_telemetry_ack_replays_without_render_or_new_claim(self):
        original=self.client.telemetry
        def lost(a,m):original(a,m);raise ConnectionError('fictional acknowledgement loss')
        with patch.object(self.client,'telemetry',side_effect=lost):
            with self.assertRaises(ConnectionError):remote_run(self.client,self.worker_root,self.worker_root/'result.json',comparison_pair=True)
        # Reconcile first output without regenerating it, then stop before second render.
        saved=json.loads((self.worker_root/'worker-claim.json').read_text())
        with patch('workers.gpu.worker.render',side_effect=AssertionError('must not regenerate')):
            first=run_once(saved['claim'],self.client,self.worker_root)
        with self.control.transaction() as db:
            metrics=json.loads(db.execute('SELECT payload FROM worker_telemetry').fetchone()[0])
        metrics['generation_seconds']+=1
        with self.assertRaises(WorkerAccessError):self.client.telemetry(saved['claim']['attempt'],metrics)
        self.assertEqual(first['take']['attempt_id'],saved['claim']['attempt']['id'])
    def test_no_second_worker_claim_before_first_completes_and_failure_preserves_first(self):
        claim=self.client.claim()
        other=self.workers.issue(self.owner,self.project,self.job,'other-worker',ttl_seconds=3000)
        self.assertIsNone(self.workers.call('Bearer '+other['token'],'claim',{}))
        first=run_once(claim,self.client,self.worker_root)
        second=self.client.claim();self.client.fail(second['attempt'],'gpu_out_of_memory')
        self.assertIsNone(self.client.claim())
        self.execution.watchdog()
        self.assertEqual(self.http.pods,{})
        self.assertEqual(len(self.control.bundle(self.owner,self.project)['takes']),1)
        self.assertEqual(digest(self.control.asset_root/first['asset']['object_key']),first['asset']['sha256'])
    def test_remaining_time_gate_skips_second_without_losing_first(self):
        self.run_first()
        self.control.clock=lambda:utcnow()+timedelta(seconds=2200)
        self.assertIsNone(self.client.claim())
        status=self.execution.status(self.owner,self.project,self.job)
        self.assertEqual(status['batch']['state'],'failed')
        self.assertEqual(len(self.control.bundle(self.owner,self.project)['takes']),1)
    def test_memory_and_timing_projections_refuse_unsafe_long_attempt(self):
        m=dict(model_load_seconds=10,generation_seconds=20,decode_encode_seconds=2,upload_seconds=1,
               gpu_model_loaded_reserved_bytes=2,gpu_peak_reserved_bytes=12,gpu_total_bytes=80)
        self.assertTrue(continuation_gate(m,1000)['allowed'])
        self.assertFalse(continuation_gate(m,500)['allowed'])
        self.assertFalse(continuation_gate(dict(m,gpu_peak_reserved_bytes=40),2000)['allowed'])
