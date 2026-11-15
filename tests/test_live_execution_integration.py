"""Signed fictional authority + mocked HTTP + actual synthetic HD output; no cloud calls."""
from copy import deepcopy
from datetime import timedelta
import hashlib
import hmac
import io
import json
from pathlib import Path
import subprocess
import tempfile
import unittest
from unittest.mock import patch
from urllib.error import HTTPError

from services.controller.live_admission import LiveAdmission, APPROVAL_DOMAIN, HOST_DOMAIN, configuration_hash
from services.controller.live_execution import LiveExecution, WORKER_CMD
from services.controller.live_billing import BILLING_DOMAIN
from services.controller.preflight import _sources
from services.controller.service import ControlService, canonical, stamp
from services.controller.studio import StudioWorkspace
from services.controller.worker_transport import WorkerTransport
from workers.gpu.common import LOCK, digest, probe, utcnow

ROOT=Path(__file__).resolve().parents[1]

class Reply(io.BytesIO):
    def __init__(self,value=None,status=200):
        super().__init__(b'' if value is None else json.dumps(value).encode());self.status=status

class LiveExecutionIntegrationTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.addCleanup(self.temp.cleanup);self.root=Path(self.temp.name)
        self.control=ControlService(self.root/'db.sqlite',self.root/'assets');self.studio=StudioWorkspace(self.control)
        self.owner='fictional-owner';self.ownerkey=b'o'*40;self.hostkey=b'h'*40;self.billkey=b'b'*40
        state=self.studio.create(self.owner,'Synthetic live-path rehearsal','music_video',0)
        p=state['projects'][0];self.project=p['bundle']['project']['id']
        shot=deepcopy(json.loads((ROOT/'fixtures/project.json').read_text())['shots'][0])
        shot.update(project_id=self.project,scene_id=p['scenes'][0]['id'],target_duration_ms=1000)
        shot['settings'].update(width=1280,height=704,steps=50)
        p['bundle']['shots'].append(shot);state=self.studio.save(self.owner,state,state['revision'])
        self.admission=LiveAdmission(self.studio,approval_keys={'owner':(self.owner,self.ownerkey)},
                                    host_keys={'host':(self.owner,self.hostkey)},build_evidence='fictional-mocked-evidence')
        profile=dict(model_profile=LOCK['profile'],image_ref='example/wan@sha256:'+'a'*64,gpu_type='fictional-gpu',gpu_count=1,
                     region='fictional-dc',worker_endpoint='https://worker.example',storage_id='fictional-store')
        launch=dict(image=profile['image_ref'],gpu={'id':'fictional-gpu','count':1},cloud='SECURE',disk=50,
                    dataCenterIds=['fictional-dc'],mounts={},ports=[],env={},cmd=WORKER_CMD)
        self.grant=dict(id='fictional-grant',owner=self.owner,project=self.project,currency='USD',approved_cents=100,
                       max_runtime_seconds=180,valid_until=stamp(utcnow()+timedelta(minutes=10)),profile=profile,
                       launch_profile=launch,source_sha256=_sources())
        self.admission.approve(self.owner,self.project,self.sign(self.grant,APPROVAL_DOMAIN,'owner',self.ownerkey))
        self.request=dict(approval_id=self.grant['id'],shot_ids=[shot['id']],expected_revision=state['revision'],
                          reservation_cents=80,runtime_seconds=180,idempotency_key='live-test')
        self.batch=self.admission.submit(self.owner,self.project,self.request)['batch']['id']
        self.host=self.sign(dict(owner=self.owner,project=self.project,config_hash=configuration_hash(profile,launch),
            source_sha256=self.grant['source_sha256'],build_manifest_sha256='c'*64,valid_until=self.grant['valid_until'],
            worker_endpoint=profile['worker_endpoint'],storage_id=profile['storage_id']),HOST_DOMAIN,'host',self.hostkey)
        self.pods={};self.calls=[];self.timeout_create=False;self.fail_delete=False;self.on_create=None
        self.execution=self.make_execution(self.admission)
        self.workers=WorkerTransport(self.control,real_jobs=self.execution)
        self.credential=self.workers.issue(self.owner,self.project,self.batch,'synthetic-worker',ttl_seconds=300)
        self.auth='Bearer '+self.credential['token']

    @staticmethod
    def sign(payload,domain,key_id,key):
        return dict(key_id=key_id,payload=payload,signature=hmac.new(key,(domain+'\n'+canonical(payload)).encode(),hashlib.sha256).hexdigest())

    def make_execution(self,admission):
        return LiveExecution(admission,runpod_token='fictional-account-token',transport=self.transport,
                             billing_keys={'bill':(self.owner,self.billkey)})

    def transport(self,request,timeout):
        method=request.get_method();path=request.full_url.split('/v2',1)[1];self.calls.append((method,path))
        if method=='POST':
            payload=json.loads(request.data)
            self.assertEqual(payload['env']['WAN_WORKER_TOKEN'],self.credential['token'])
            if self.on_create:self.on_create()
            self.pods['fictional-pod']=dict(id='fictional-pod',name=payload['name'])
            if self.timeout_create:raise TimeoutError('Synthetic unknown create')
            return Reply(self.pods['fictional-pod'],201)
        if path=='/pods':return Reply(dict(pods=list(self.pods.values()),pagination=dict(hasNextPage=False,nextCursor=None)))
        if method=='GET':
            if self.pods:return Reply(self.pods['fictional-pod'])
            raise HTTPError(request.full_url,404,'Absent',{},io.BytesIO())
        if method=='DELETE':
            if self.fail_delete:self.fail_delete=False;raise HTTPError(request.full_url,503,'Synthetic outage',{},io.BytesIO())
            self.pods.clear();return Reply(status=204)
        raise AssertionError('Unexpected provider method')

    def provision(self):
        with patch('services.controller.live_admission._build',return_value={'manifest_sha256':'c'*64}):
            return self.execution.provision(self.owner,self.project,self.batch,self.host,worker_token=self.credential['token'])

    def bill(self,identity,kind,amount):
        payload=dict(id=identity,owner=self.owner,project=self.project,batch=self.batch,kind=kind,amount_cents=amount,
            bill_reference='fictional-provider-evidence',valid_until=self.grant['valid_until'],provider_resource_id='fictional-pod',currency='USD')
        return self.execution.ingest_bill(self.owner,self.project,self.sign(payload,BILLING_DOMAIN,'bill',self.billkey))

    def test_completion_cleanup_settlement_restore_and_late_overrun(self):
        from services.controller.backup import create_backup,restore_backup
        self.on_create=lambda:self.assertIsNone(self.workers.call(self.auth,'claim',{}))
        self.provision();claim=self.workers.call(self.auth,'claim',{});attempt=claim['attempt']
        video=self.root/'synthetic.mp4'
        subprocess.run(['ffmpeg','-nostdin','-v','error','-f','lavfi','-i','color=c=green:s=1280x704:r=24',
            '-frames:v','25','-an','-c:v','libx264','-preset','ultrafast','-pix_fmt','yuv420p',str(video)],check=True,timeout=20)
        media=probe(video,attempt['settings'],25);data=video.read_bytes()
        receipt=self.workers.upload(self.auth,attempt['id'],attempt['lease_id'],digest(video),len(data),io.BytesIO(data))
        asset=dict(id='synthetic-hd',project_id=self.project,owner_id=self.owner,kind='video',mime_type='video/mp4',
                   object_key=receipt['object_key'],bytes=len(data),sha256=receipt['sha256'],duration_ms=media['duration_ms'])
        body=dict(lease_id=attempt['lease_id'],output_asset_manifest=dict(asset=asset,media=media))
        take=self.workers.call(self.auth,f"attempts/{attempt['id']}/complete",body)
        self.assertEqual(self.workers.call(self.auth,f"attempts/{attempt['id']}/complete",body),take)
        self.bill('interim','charge',30)
        with self.assertRaises(ValueError):self.bill('premature','settlement',60)
        self.fail_delete=True;self.assertEqual(self.execution.watchdog(),[self.batch]);self.assertTrue(self.pods)
        self.assertEqual(self.execution.watchdog(),[])
        self.assertEqual(self.execution.status(self.owner,self.project,self.batch)['budget']['unsettled_count'],1)
        with self.assertRaises(ValueError):create_backup(self.control.db_path,self.control.asset_root,self.root/'unsettled')
        self.bill('final','settlement',60);self.bill('late','charge',50);self.bill('late','charge',50)
        status=self.execution.status(self.owner,self.project,self.batch)
        self.assertEqual(status['budget']['spent_cents'],110);self.assertEqual(status['budget']['reserved_cents'],0)
        with self.assertRaises(ValueError):self.admission.submit(self.owner,self.project,dict(self.request,idempotency_key='overrun',reservation_cents=1))
        create_backup(self.control.db_path,self.control.asset_root,self.root/'backup')
        restored=restore_backup(self.root/'backup',self.root/'restore')
        control=ControlService(restored['database'],restored['assets'])
        self.assertEqual(len(control.bundle(self.owner,self.project)['takes']),1)
        subprocess.run(['ffmpeg','-nostdin','-v','error','-xerror','-i',str(Path(restored['assets'])/asset['object_key']),'-f','null','-'],check=True,timeout=20)
        with control.transaction() as db:
            self.assertEqual(db.execute('SELECT revoked FROM live_approvals').fetchone()[0],1)
            self.assertEqual(db.execute('SELECT revoked FROM worker_credentials').fetchone()[0],1)
        self.assertNotIn(self.credential['token'].encode(),Path(self.control.db_path).read_bytes())
        with self.control.transaction() as db:
            db.execute("UPDATE live_billing_events SET amount_cents=1 WHERE id='final'")
        with self.assertRaises(ValueError):create_backup(self.control.db_path,self.control.asset_root,self.root/'tampered-bill')

    def test_unknown_create_restart_cleanup_ignores_revoked_keys_and_current_model(self):
        self.timeout_create=True;self.provision()
        self.assertEqual(sum(method=='POST' for method,_ in self.calls),1)
        self.admission.revoke(self.owner,self.project,self.grant['id'])
        replacement=LiveAdmission(self.studio)
        self.execution=self.make_execution(replacement)
        self.execution.provision(self.owner,self.project,self.batch)
        self.execution.cancel(self.owner,self.project,self.batch)
        with patch('services.controller.real_jobs.LOCK',{'profile':{'id':'changed-model'}}):
            self.assertEqual(self.execution.watchdog(),[])
        self.assertEqual(sum(method=='POST' for method,_ in self.calls),1)
        self.assertFalse(self.pods)
        self.assertEqual(self.execution.status(self.owner,self.project,self.batch)['budget']['unsettled_count'],1)
