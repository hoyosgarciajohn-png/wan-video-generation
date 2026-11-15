"""Actual local TCP admission with fictional installed keys; no provider dispatch."""
from copy import deepcopy
from datetime import timedelta
from http.client import HTTPConnection
import hashlib
import hmac
import json
from pathlib import Path
import tempfile
import threading
import unittest

from services.controller.http_api import StudioAPI, make_server
from services.controller.live_admission import LiveAdmission, APPROVAL_DOMAIN
from services.controller.preflight import _sources
from services.controller.service import ControlService, canonical, stamp
from services.controller.studio import StudioWorkspace
from workers.gpu.common import LOCK, utcnow

ROOT=Path(__file__).resolve().parents[1]


class LiveAdmissionIntegrationTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory(); self.addCleanup(self.temp.cleanup)
        self.root=Path(self.temp.name)
        self.control=ControlService(self.root/'db.sqlite',self.root/'assets')
        self.studio=StudioWorkspace(self.control)
        self.owner='fictional-owner'; self.key=b'fictional-test-only-signing-key-0000000000'
        state=self.studio.create(self.owner,'Signed admission test','music_video',0)
        p=state['projects'][0]; self.project=p['bundle']['project']['id']
        shot=deepcopy(json.loads((ROOT/'fixtures/project.json').read_text())['shots'][0])
        shot.update(project_id=self.project,scene_id=p['scenes'][0]['id'],target_duration_ms=1000)
        shot['settings'].update(width=1280,height=704,steps=50)
        p['bundle']['shots'].append(shot); state=self.studio.save(self.owner,state,state['revision'])
        self.live=LiveAdmission(self.studio,approval_keys={'test-key':(self.owner,self.key)})
        profile=dict(model_profile=LOCK['profile'],image_ref='example/wan@sha256:'+'a'*64,gpu_type='fictional-gpu',
                     gpu_count=1,region='fictional-dc',worker_endpoint='https://worker.example',storage_id='fictional-store')
        self.grant=dict(id='fictional-grant',owner=self.owner,project=self.project,currency='USD',approved_cents=100,
            max_runtime_seconds=120,valid_until=stamp(utcnow()+timedelta(minutes=10)),profile=profile,
            launch_profile=dict(image=profile['image_ref'],gpu={'id':'fictional-gpu','count':1},cloud='SECURE',disk=50,
                                dataCenterIds=['fictional-dc'],mounts={},ports=[],env={}),source_sha256=_sources())
        self.envelope=self.sign(self.grant)
        self.payload=dict(approval_id=self.grant['id'],shot_ids=[shot['id']],expected_revision=state['revision'],
                          reservation_cents=80,runtime_seconds=120,idempotency_key='live-request')
        self.api=StudioAPI(self.studio,{'a'*40:self.owner,'b'*40:'foreign-owner'},live_admission=self.live)
        self.server=make_server(self.api,('127.0.0.1',0))
        self.thread=threading.Thread(target=self.server.serve_forever,daemon=True);self.thread.start()
        self.addCleanup(self.stop)
        self.cookie=self.login('a'*40);self.foreign=self.login('b'*40)
        self.base=f'/v1/studio/projects/{self.project}/live'

    def sign(self,payload):
        return dict(key_id='test-key',payload=payload,signature=hmac.new(self.key,(APPROVAL_DOMAIN+'\n'+canonical(payload)).encode(),hashlib.sha256).hexdigest())

    def stop(self):
        self.server.shutdown();self.server.server_close();self.thread.join(timeout=5)

    def request(self,path,payload=None,cookie=None,method='POST'):
        headers={'Origin':self.api.origin,'X-WAN-Request':'studio','Content-Type':'application/json'}
        if cookie:headers['Cookie']=cookie
        connection=HTTPConnection(*self.server.server_address,timeout=10)
        try:
            connection.request(method,path,body=json.dumps(payload or {}).encode(),headers=headers)
            response=connection.getresponse();data=response.read()
            return response.status,json.loads(data) if data else None,dict(response.getheaders())
        finally:connection.close()

    def login(self,token):
        status,_,headers=self.request('/v1/studio/session',{'token':token});self.assertEqual(status,200)
        return headers['Set-Cookie'].split(';')[0]

    def test_session_signature_and_replay_boundaries(self):
        path=self.base+'/approvals'
        self.assertEqual(self.request(path,self.envelope)[0],401)
        self.assertEqual(self.request(path,self.envelope,self.foreign)[0],404)
        tampered=deepcopy(self.envelope);tampered['payload']['approved_cents']=999999
        self.assertIn(self.request(path,tampered,self.cookie)[0],(403,404))
        self.assertIn(self.request(path,self.envelope,self.cookie)[0],(200,201))
        status,first,_=self.request(self.base+'/batches',self.payload,self.cookie)
        self.assertIn(status,(200,201,202),first)
        status,again,_=self.request(self.base+'/batches',self.payload,self.cookie)
        self.assertEqual(first['batch']['id'],again['batch']['id'])
        self.assertFalse(first['dispatch_enabled'])
        injected=dict(self.payload,owner_id=self.owner,execution_enabled=True)
        self.assertEqual(self.request(self.base+'/batches',injected,self.cookie)[0],422)
        batch=first['batch']['id']
        self.assertEqual(self.request(self.base+f'/batches/{batch}/cancel',{},self.foreign)[0],404)
        status,canceled,_=self.request(self.base+f'/batches/{batch}/cancel',{},self.cookie)
        self.assertEqual(status,200);self.assertEqual(canceled['reservation_state'],'released')
        self.assertIsNone(canceled['batch']['provider_resource_id'])
        self.assertEqual(self.control.bundle(self.owner,self.project)['attempts'],[])

    def test_backup_revokes_copied_authority_without_changing_source(self):
        from services.controller.backup import create_backup,restore_backup
        self.live.approve(self.owner,self.project,self.envelope)
        batch=self.live.submit(self.owner,self.project,self.payload)['batch']['id']
        with self.assertRaises(ValueError):create_backup(self.control.db_path,self.control.asset_root,self.root/'pending')
        self.live.cancel(self.owner,self.project,batch)
        create_backup(self.control.db_path,self.control.asset_root,self.root/'backup')
        result=restore_backup(self.root/'backup',self.root/'restored')
        restored=ControlService(result['database'],result['assets'])
        copied=LiveAdmission(StudioWorkspace(restored),approval_keys={'test-key':(self.owner,self.key)})
        with self.assertRaises(ValueError):copied.approve(self.owner,self.project,self.envelope)
        with self.assertRaises(ValueError):copied.submit(self.owner,self.project,dict(self.payload,idempotency_key='new-job'))
        self.assertEqual(copied.status(self.owner,self.project,batch)['reservation_state'],'released')
        self.assertEqual(self.live.approve(self.owner,self.project,self.envelope)['id'],self.grant['id'])
        with restored.transaction() as db:
            self.assertEqual(db.execute('SELECT revoked FROM live_approvals').fetchone()[0],1)
        self.assertNotIn(self.key,Path(self.control.db_path).read_bytes())

    def test_backup_refuses_released_record_with_any_dispatch_evidence(self):
        from services.controller.backup import create_backup
        self.live.approve(self.owner,self.project,self.envelope)
        batch=self.live.submit(self.owner,self.project,self.payload)['batch']['id']
        self.live.cancel(self.owner,self.project,batch)
        with self.control.transaction() as db:
            db.execute("UPDATE live_job_links SET dispatch_state='started' WHERE batch=?",(batch,))
        with self.assertRaises(ValueError):
            create_backup(self.control.db_path,self.control.asset_root,self.root/'unsafe')
