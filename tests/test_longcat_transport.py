"""Fictional signed scopes and real CPU media; no credentials or rented GPUs."""
from copy import deepcopy
from datetime import datetime, timezone
import hashlib
import hmac
import io
import json
from pathlib import Path
import subprocess
import tempfile
import threading
import unittest
import wave

from PIL import Image
from services.controller.http_api import StudioAPI, make_server, body_limit
from services.controller.longcat import LongCatTransport, OWNER_DOMAIN, HOST_DOMAIN, CLEANUP_DOMAIN, source_digest, pod_name
from services.controller.service import ControlService, canonical
from services.controller.studio import StudioWorkspace
from services.controller.worker_transport import WorkerAccessError
from workers.gpu.common import digest
from workers.gpu.longcat_batch import PROTOCOL, BatchJournal, fingerprint, verify_output
from workers.gpu.longcat_client import LongCatClient
from workers.gpu.client import WorkerAPIError
from deployment.hosted_app import Application


class LongCatTransportTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.media_tmp = tempfile.TemporaryDirectory(); cls.media = Path(cls.media_tmp.name)/'synthetic.mp4'
        subprocess.run(['ffmpeg','-v','error','-f','lavfi','-i','color=c=blue:s=864x448:r=25',
                        '-frames:v','93','-c:v','libx264','-pix_fmt','yuv420p',str(cls.media)],check=True)
        cls.video = cls.media.read_bytes(); cls.hash = digest(cls.media)

    @classmethod
    def tearDownClass(cls): cls.media_tmp.cleanup()

    def setUp(self):
        temp=tempfile.TemporaryDirectory(); self.addCleanup(temp.cleanup); self.root=Path(temp.name)
        self.now=1001
        self.control=ControlService(self.root/'state.sqlite',self.root/'assets',
                                   clock=lambda:datetime.fromtimestamp(self.now,timezone.utc))
        self.studio=StudioWorkspace(self.control); self.owner='fictional-owner'
        state=self.studio.create(self.owner,'Fictional LongCat music','music_video',0)
        self.project=state['projects'][0]['bundle']['project']['id']
        self.inputs=self.root/'inputs'; self.inputs.mkdir()
        Image.new('RGB',(864,448),'blue').save(self.inputs/'scene.png')
        with wave.open(str(self.inputs/'audio.wav'),'wb') as w:
            w.setparams((1,2,16000,0,'NONE','not compressed')); w.writeframes(b'\0'*151040)
        self.manifest=dict(protocol=PROTOCOL,project_id=self.project,batch_id='fictional-batch',
                           fps=25,duration_frames=246,shots=[])
        for i in range(3):
            self.manifest['shots'].append(dict(id=f'S{i+1}',frames=82,in_frame=82*i,trim_in_frames=0,
                audio_start_frame=82*i,seed=i,prompt='Fictional blue stage, performer wears a cap',headwear_required=True,
                image=dict(path='scene.png',sha256=digest(self.inputs/'scene.png')),
                audio=dict(path='audio.wav',sha256=digest(self.inputs/'audio.wav'))))
        self.execution=dict(protocol=PROTOCOL,admitted_at=1000,deadline=5800,gpu_count=2,max_hourly_cents=878,
            compute_cap_cents=1171,scope_id='fictional-scope',guard_run_id='fictional-guard',manifest_sha256=fingerprint(self.manifest))
        self.grant=dict(owner=self.owner,project=self.project,execution=self.execution,
            image_ref='ghcr.io/hoyosgarciajohn-png/wan-video-generation-gpu@sha256:'+'a'*64,
            source_sha256=source_digest(),budget_id='fictional-budget',budget_total_cents=2000,
            prior_committed_cents=800,storage_reserve_cents=29)
        self.key=b'fictional owner key never installed'+b'x'*32
        self.host_key=b'fictional host key never installed'+b'y'*32
        self.transport=LongCatTransport(self.control)

    def sign(self,payload,domain,key):
        return dict(key_id='fixture',payload=deepcopy(payload),
                    signature=hmac.new(key,(domain+'\n'+canonical(payload)).encode(),hashlib.sha256).hexdigest())

    def admit(self,grant=None,host_change=None):
        grant=grant or self.grant
        host=dict(owner=self.owner,project=self.project,grant_sha256=fingerprint(grant),
                  source_sha256=grant['source_sha256'],image_ref=grant['image_ref'],
                  guard_run_id=grant['execution']['guard_run_id'],deadline=grant['execution']['deadline'],
                  pod_name=pod_name(grant['execution']['scope_id']),
                  image_import_verified=True,guard_ready=True,storage_verified=True)
        if host_change: host.update(host_change)
        result=self.transport.admit(self.owner,self.manifest,self.inputs,
            self.sign(grant,OWNER_DOMAIN,self.key),self.sign(host,HOST_DOMAIN,self.host_key),
            approval_keys={'fixture':(self.owner,self.key)},host_keys={'fixture':(self.owner,self.host_key)})
        self.token=result['token']; self.auth='Bearer '+self.token
        return result

    def upload(self,shot='S1',data=None):
        data=self.video if data is None else data
        return self.transport.upload(self.auth,shot,hashlib.sha256(data).hexdigest(),len(data),io.BytesIO(data))

    def test_durable_takes_assemble_into_one_review_with_complete_master(self):
        from workers.media.longcat_assemble import assemble_review
        from workers.media.export import probe
        self.admit();receipts=[]
        for shot in self.manifest['shots']:
            self.transport.start(self.auth,shot['id']);receipts.append(self.upload(shot['id']))
        master=self.root/'master.wav'
        with wave.open(str(master),'wb') as audio:
            audio.setparams((2,2,48000,0,'NONE','not compressed'))
            audio.writeframes(b'\0'*(self.manifest['duration_frames']*1920*4))
        checksum=digest(master);output=self.root/'review.mp4'
        with self.assertRaises(ValueError):assemble_review(self.manifest,receipts[:-1],self.control.asset_root,master,checksum,output)
        swapped=deepcopy(receipts);swapped[1]['scope_id']='foreign'
        with self.assertRaises(ValueError):assemble_review(self.manifest,swapped,self.control.asset_root,master,checksum,output)
        result=assemble_review(self.manifest,receipts,self.control.asset_root,master,checksum,output)
        self.assertEqual(result['status'],'REVIEW_VIDEO_ASSEMBLED_NOT_CREATIVE_APPROVAL')
        self.assertEqual(int(probe(output,'v:0')['nb_frames']),246)
        self.assertAlmostEqual(float(probe(output,'a:0')['duration']),246/25,places=2)
        self.assertEqual(digest(master),checksum)
        with self.assertRaises(ValueError):assemble_review(self.manifest,receipts,self.control.asset_root,master,checksum,output)

    def test_backup_preserves_inputs_receipts_budget_and_fences_cleaned_scope(self):
        from services.controller.backup import create_backup,restore_backup
        self.admit();self.transport.start(self.auth,'S1');receipt=self.upload()
        with self.assertRaises(ValueError):create_backup(self.control.db_path,self.control.asset_root,self.root/'unclosed')
        proof=dict(owner=self.owner,scope_id=self.execution['scope_id'],grant_sha256=fingerprint(self.grant),
                   guard_run_id=self.execution['guard_run_id'],pod_name=pod_name(self.execution['scope_id']),
                   absence_confirmed=True,confirmed_at=self.now)
        changed=dict(proof,pod_name='foreign')
        with self.assertRaises(ValueError):self.transport.confirm_cleanup(self.owner,self.execution['scope_id'],
            self.sign(changed,CLEANUP_DOMAIN,self.host_key),host_keys={'fixture':(self.owner,self.host_key)})
        self.transport.confirm_cleanup(self.owner,self.execution['scope_id'],self.sign(proof,CLEANUP_DOMAIN,self.host_key),
                                       host_keys={'fixture':(self.owner,self.host_key)})
        create_backup(self.control.db_path,self.control.asset_root,self.root/'backup')
        restored=restore_backup(self.root/'backup',self.root/'restored')
        recovered=LongCatTransport(ControlService(restored['database'],restored['assets'],clock=self.control.clock))
        with self.assertRaises(WorkerAccessError):recovered.configuration(self.auth)
        with recovered.control.transaction() as db:
            self.assertEqual(db.execute('SELECT reserved,revoked FROM longcat_scopes').fetchone(),(1171,1))
            self.assertEqual(json.loads(db.execute('SELECT receipt FROM longcat_shots').fetchone()[0]),receipt)
        self.assertEqual(digest(Path(restored['assets'])/receipt['object_key']),self.hash)
        self.assertEqual(digest(Path(restored['assets'])/f'longcat/{self.project}/fictional-batch/inputs/scene.png'),
                         digest(self.inputs/'scene.png'))

    def test_authentication_owner_scope_and_no_public_admission(self):
        self.admit()
        with self.assertRaises(WorkerAccessError): self.transport.configuration('Bearer '+'z'*43)
        with self.assertRaises(WorkerAccessError): self.transport.start(self.auth,'foreign-shot')
        with self.control.transaction() as db:
            raw=db.execute('SELECT token_hash,grant,host FROM longcat_scopes').fetchone()
            self.assertNotIn(self.token,repr(raw))
        api=StudioAPI(self.studio,{'s'*32:self.owner})
        headers={'Host':'127.0.0.1:5173','Authorization':self.auth}
        self.assertEqual(api.dispatch('POST','/v1/longcat/admit',headers,b'{}').status,404)
        headers['Origin']='https://foreign.example'
        self.assertEqual(api.dispatch('GET','/v1/longcat/configuration',headers).status,403)

    def test_signed_host_build_guard_source_and_budget_boundaries(self):
        with self.assertRaises(ValueError): self.admit(host_change={'guard_ready':False})
        for change in [dict(source_sha256='0'*64),dict(prior_committed_cents=900),dict(storage_reserve_cents=0)]:
            with self.assertRaises(ValueError): self.admit({**self.grant,**change})
        wrong=deepcopy(self.grant); wrong['execution']['manifest_sha256']='0'*64
        with self.assertRaises(ValueError): self.admit(wrong)
        self.assertFalse((self.control.asset_root/'longcat'/self.project/'fictional-batch'/'inputs').exists())

    def test_no_scope_replay_budget_reset_or_refund_on_revoke(self):
        self.admit()
        with self.assertRaises(ValueError): self.admit()
        self.transport.revoke(self.owner,'fictional-scope')
        with self.assertRaises(WorkerAccessError): self.transport.configuration(self.auth)
        self.manifest['batch_id']='fictional-batch-two'
        changed=deepcopy(self.grant);changed['execution'].update(scope_id='second',manifest_sha256=fingerprint(self.manifest))
        with self.assertRaisesRegex(ValueError,'budget'): self.admit(changed)
        changed.update(budget_id='reset-budget')
        with self.assertRaisesRegex(ValueError,'budget ledger'): self.admit(changed)
        with self.control.transaction() as db:
            self.assertEqual(db.execute('SELECT SUM(reserved) FROM longcat_scopes').fetchone()[0],1171)

    def test_interrupted_render_is_durable_and_never_automatically_restarted(self):
        self.admit(); self.transport.start(self.auth,'S1')
        restarted=LongCatTransport(self.control)
        with self.assertRaises(WorkerAccessError): restarted.start(self.auth,'S1')
        with self.assertRaises(ValueError): restarted.start(self.auth,'S2')
        self.assertIsNone(restarted.receipt(self.auth,'S1'))

    def test_real_video_receipt_replay_conflict_corruption_and_expiry(self):
        self.admit();self.transport.start(self.auth,'S1');receipt=self.upload()
        self.assertEqual(self.upload(),receipt)
        self.assertEqual(self.transport.receipt(self.auth,'S1'),receipt)
        self.assertEqual(verify_output(self.control.asset_root/receipt['object_key'])['width'],864)
        with self.assertRaises(ValueError): self.upload(data=b'changed')
        self.now=5770
        with self.assertRaises(WorkerAccessError): self.transport.start(self.auth,'S2')
        self.assertEqual(self.transport.receipt(self.auth,'S1'),receipt)
        (self.control.asset_root/receipt['object_key']).write_bytes(b'corrupt')
        with self.assertRaises(ValueError): self.transport.receipt(self.auth,'S1')

    def test_hash_failure_and_revocation_during_verification_leave_no_take(self):
        self.admit();self.transport.start(self.auth,'S1')
        with self.assertRaises(ValueError): self.transport.upload(self.auth,'S1','0'*64,len(self.video),io.BytesIO(self.video))
        def revoke(path):
            result=verify_output(path);self.transport.revoke(self.owner,'fictional-scope');return result
        self.transport.verify=revoke
        with self.assertRaises(WorkerAccessError):self.upload()
        with self.control.transaction() as db:
            self.assertIsNone(db.execute('SELECT receipt FROM longcat_shots').fetchone()[0])
        self.assertEqual(list(self.transport.root(self.project,'fictional-batch').glob('staging/*')),[])

    def test_http_client_full_queue_and_recovery_after_local_journal_loss(self):
        self.admit();api=StudioAPI(self.studio,{'s'*32:self.owner})
        server=make_server(api,('127.0.0.1',0))
        thread=threading.Thread(target=server.serve_forever,daemon=True);thread.start()
        self.addCleanup(server.server_close);self.addCleanup(server.shutdown)
        client=LongCatClient(f'http://127.0.0.1:{server.server_port}',self.token,allow_local_http=True)
        config=client.configuration();self.assertEqual(config['execution'],self.execution)
        client.download(config['manifest'],self.root/'worker-inputs')
        journal=BatchJournal(self.root/'worker-output',self.manifest,self.execution,clock=lambda:self.now)
        for shot in self.manifest['shots']:
            self.assertEqual(journal.decision(shot),'render');client.start(shot['id'])
            path=journal.output_path(shot);path.parent.mkdir(parents=True,exist_ok=True);path.write_bytes(self.video)
            journal.rendered(shot,verify_output(path));journal.publish(shot,client.publish)
        recovered=BatchJournal(self.root/'replacement-output',self.manifest,self.execution,clock=lambda:self.now)
        for shot in self.manifest['shots']:
            recovered.restore_published(shot,client.receipt(shot['id']))
            self.assertEqual(recovered.decision(shot),'skip')
        self.assertEqual(len(recovered.state['shots']),3)
        with self.assertRaises(WorkerAPIError): client.start('S1')

    def test_wsgi_artifact_stream_uses_large_body_path(self):
        self.admit();self.transport.start(self.auth,'S1')
        api=StudioAPI(self.studio,{'s'*32:self.owner},'https://wan.example.test')
        static=self.root/'static';static.mkdir();(static/'index.html').write_text('fictional')
        app=Application(api,static);status=[]
        env=dict(PATH_INFO='/v1/longcat/shots/S1/artifact',REQUEST_METHOD='PUT',HTTP_HOST='wan.example.test',
                 HTTP_AUTHORIZATION=self.auth,HTTP_X_WAN_SHA256=self.hash,CONTENT_TYPE='video/mp4',
                 CONTENT_LENGTH=str(len(self.video)),**{'wsgi.input':io.BytesIO(self.video)})
        body=b''.join(app(env,lambda s,h:status.append(s)))
        self.assertTrue(status[0].startswith('200'));self.assertEqual(json.loads(body)['sha256'],self.hash)
        self.assertEqual(body_limit(env['PATH_INFO']),32*1024*1024)


if __name__ == '__main__': unittest.main()
