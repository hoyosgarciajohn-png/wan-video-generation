"""Signed fictional song scope: no live account, secrets, or GPU."""
from copy import deepcopy
from datetime import timedelta
import unittest

from tests import test_live_admission
from workers.gpu.tests.test_singing import policy
from workers.gpu.common import utcnow, stamp, validate_claim
from workers.gpu.profiles import singing_profile
from services.controller.allocation_retry import POLICY
from services.controller.live_admission import configuration_hash, HOST_DOMAIN
from services.controller.production import policy as saved_policy
from services.controller.worker_transport import WorkerTransport
from services.controller.live_execution import LiveExecution, PRODUCTION_CMD, BOOTSTRAP_ENTRYPOINT
from tests.test_live_execution import HTTP


class SingingAdmissionTests(unittest.TestCase):
    def setUp(self):
        test_live_admission.LiveAdmissionTests.setUp(self)
        state=self.studio.get(self.owner);bundle=state['projects'][0]['bundle']
        original=deepcopy(bundle['shots'][0]);bundle['shots']=[]
        for i in range(2):
            shot=deepcopy(original);shot.update(id=original['id'] if i==0 else f'song-{i}',revision=original['revision']+1 if i==0 else 1,target_duration_ms=5000,reference_asset_ids=[f'image-{i}',f'audio-{i}'])
            shot['settings']=dict(width=832,height=448,steps=40,seed=i,frame_rate=dict(numerator=16,denominator=1))
            bundle['shots'].append(shot)
            for kind,mime in [('image','image/png'),('audio','audio/wav')]:
                bundle['assets'].append(dict(id=f'{kind}-{i}',project_id=self.project,owner_id=self.owner,kind=kind,
                    object_key=f'projects/{self.project}/{kind}-{i}',mime_type=mime,bytes=160044 if kind=='audio' else 100,
                    sha256='a'*64,duration_ms=5000 if kind=='audio' else None))
        with self.control.transaction() as db:
            saved=self.control._load(db,self.owner,self.project)
            saved['assets']=deepcopy(bundle['assets']);self.control._save(db,saved)
        self.state=self.studio.save(self.owner,state,state['revision'])
        snapshots=[dict(shot_id=s['id'],**{k:v for k,v in s.items() if k not in ('id','project_id','scene_id')}) for s in bundle['shots']]
        self.payload.update(approved_cents=1800,max_runtime_seconds=14400,valid_until=(utcnow()+timedelta(hours=6)).isoformat().replace('+00:00','Z'),
                            continuous_queue=policy(snapshots),capacity_retry=dict(POLICY))
        self.payload['profile'].update(model_profile=singing_profile(),gpu_type='NVIDIA H100 80GB HBM3')
        self.payload['launch_profile'].update(cmd=PRODUCTION_CMD,entrypoint=BOOTSTRAP_ENTRYPOINT)
        self.payload['launch_profile']['gpu']['id']='NVIDIA H100 80GB HBM3'
        self.request.update(shot_ids=[s['id'] for s in bundle['shots']],reservation_cents=1800,runtime_seconds=14400,
                            expected_revision=self.state['revision'])

    def signed(self,*args,**kwargs): return test_live_admission.LiveAdmissionTests.signed(self,*args,**kwargs)

    def test_multishot_admission_scoped_credential_and_no_budget_reset(self):
        self.live.approve(self.owner,self.project,self.signed())
        job=self.live.submit(self.owner,self.project,self.request)
        self.assertEqual(len(job['batch']['shot_snapshots']),2)
        execution=LiveExecution(self.live)
        worker=WorkerTransport(self.control,real_jobs=execution)
        token=worker.issue(self.owner,self.project,job['batch']['id'],'fictional-worker',ttl_seconds=14700)
        self.assertTrue(token['token'])
        with self.control.transaction() as db:
            self.assertEqual(saved_policy(db,job['batch']),self.payload['continuous_queue'])
        self.assertEqual(self.live.submit(self.owner,self.project,self.request)['batch']['id'],job['batch']['id'])
        self.live.cancel(self.owner,self.project,job['batch']['id'])
        with self.assertRaisesRegex(ValueError,'already consumed'):
            self.live.submit(self.owner,self.project,dict(self.request,idempotency_key='reset-attempt'))

    def test_frozen_shots_and_dollar_ceiling_reject_changes(self):
        for key,value in [('gpu_cap_cents',2000),('max_runtime_seconds',14401),('total_cap_cents',2100)]:
            payload=deepcopy(self.payload);payload['continuous_queue'][key]=value
            with self.assertRaises(ValueError):self.live.approve(self.owner,self.project,self.signed(payload))
        self.live.approve(self.owner,self.project,self.signed())
        with self.assertRaises(ValueError):self.live.submit(self.owner,self.project,dict(self.request,reservation_cents=1801))
        with self.assertRaises(ValueError):self.live.submit(self.owner,self.project,dict(self.request,shot_ids=self.request['shot_ids'][::-1]))
        with self.control.transaction() as db:
            self.assertEqual(db.execute('SELECT COUNT(*) FROM live_reservations').fetchone()[0],0)

    def test_serial_claims_durable_metrics_retry_and_cleanup(self):
        from unittest.mock import patch
        from workers.gpu.worker import run_once
        from workers.gpu.common import frame_count
        import subprocess
        self.live.approve(self.owner,self.project,self.signed())
        batch=self.live.submit(self.owner,self.project,self.request)['batch']['id']
        http=HTTP();self.live._host_keys={'fictional':(self.owner,self.secret)};self.live._build_evidence='fictional'
        execution=LiveExecution(self.live,runpod_token='fictional',transport=http,candidate_check=lambda *a:True)
        workers=WorkerTransport(self.control,real_jobs=execution)
        token=workers.issue(self.owner,self.project,batch,'song-worker',ttl_seconds=14700)['token']
        auth='Bearer '+token
        host=dict(owner=self.owner,project=self.project,config_hash=configuration_hash(self.payload['profile'],
            self.payload['launch_profile'],None,None,self.payload['continuous_queue']),source_sha256=self.payload['source_sha256'],
            build_manifest_sha256='a'*64,valid_until=self.payload['valid_until'],worker_endpoint=self.profile['worker_endpoint'],storage_id=self.profile['storage_id'])
        with patch('services.controller.live_admission._build',return_value={'manifest_sha256':'a'*64}):
            execution.provision(self.owner,self.project,batch,self.signed(host,HOST_DOMAIN),worker_token=token)
        outer=self
        class Client:
            def claim(self):return workers.call(auth,'claim',{})
            def heartbeat(self,a,p):return workers.call(auth,f"attempts/{a['id']}/heartbeat",dict(lease_id=a['lease_id'],progress=p))
            def fail(self,a,c):return workers.call(auth,f"attempts/{a['id']}/fail",dict(lease_id=a['lease_id'],code=c))
            def telemetry(self,a,m):return workers.call(auth,f"attempts/{a['id']}/telemetry",dict(lease_id=a['lease_id'],metrics=m))
            def complete(self,a,m):return workers.call(auth,f"attempts/{a['id']}/complete",dict(lease_id=a['lease_id'],output_asset_manifest=m))
            def upload(self,a,m,p):
                with open(p,'rb') as f:return workers.upload(auth,a['id'],a['lease_id'],m['asset']['sha256'],m['asset']['bytes'],f)
        client=Client()
        def render(c,path,*args):
            subprocess.run(['ffmpeg','-v','error','-y','-f','lavfi','-i','color=c=blue:s=832x448:r=16',
                '-frames:v',str(frame_count(c['shot_snapshot'],'runpod')),'-an','-c:v','libx264','-threads','1','-pix_fmt','yuv420p',str(path)],check=True)
            return dict(model_profile=deepcopy(c['batch']['model_profile']),model_load_seconds=1,generation_seconds=2,
                decode_encode_seconds=1,gpu_peak_allocated_bytes=100,gpu_peak_reserved_bytes=200,process_start='warm')
        first=client.claim();validate_claim(first)
        self.assertEqual(client.claim()['attempt']['id'],first['attempt']['id'])
        other=workers.issue(self.owner,self.project,batch,'other-song-worker',ttl_seconds=14700)['token']
        self.assertIsNone(workers.call('Bearer '+other,'claim',{}))
        with patch('workers.gpu.worker.render',side_effect=render):
            result=run_once(first,client,self.control.asset_root.parent/'worker')
        second=client.claim();validate_claim(second)
        self.assertNotEqual(first['shot_snapshot']['shot_id'],second['shot_snapshot']['shot_id'])
        client.fail(second['attempt'],'gpu_out_of_memory')
        self.assertIsNone(client.claim());execution.watchdog()
        self.assertEqual(http.posts,1);self.assertEqual(http.pods,{})
        self.assertEqual(len(self.control.bundle(self.owner,self.project)['takes']),1)
        with self.control.transaction() as db:
            self.assertEqual(db.execute('SELECT count(*) FROM worker_telemetry').fetchone()[0],1)
