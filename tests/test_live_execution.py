"""Fictional HTTP and delegated signatures only; never a Runpod request."""
from copy import deepcopy
from datetime import timedelta
import hashlib
import hmac
import io
import json
from unittest.mock import patch
import unittest
from urllib.error import HTTPError

from tests import test_live_admission
from services.controller.live_admission import HOST_DOMAIN, configuration_hash
from services.controller.live_billing import BILLING_DOMAIN
from services.controller.live_execution import LiveExecution, WORKER_CMD
from services.controller.service import canonical, stamp
from services.controller.worker_transport import WorkerTransport
from services.controller import backup
from workers.gpu.common import utcnow


class HTTP:
    def __init__(self):
        self.pods={}; self.posts=0; self.unknown=False; self.on_create=None
    def __call__(self,request,timeout):
        method=request.get_method(); path=request.full_url.split('/v2')[1]
        if method=='POST':
            self.posts+=1
            record=dict(id='fictional-pod-'+str(self.posts),name=json.loads(request.data)['name'])
            self.pods[record['id']]=record
            if self.on_create:self.on_create(request)
            if self.unknown:
                self.unknown=False; raise TimeoutError('fictional lost response')
            status,payload=201,record
        elif path=='/pods':status,payload=200,dict(pods=list(self.pods.values()),pagination=dict(hasNextPage=False,nextCursor=None))
        else:
            identity=path.rsplit('/',1)[1]
            if identity not in self.pods:raise HTTPError(request.full_url,404,'fictional',{},None)
            if method=='DELETE':
                del self.pods[identity];status,payload=204,None
            else:status,payload=200,self.pods[identity]
        response=io.BytesIO(json.dumps(payload).encode());response.status=status;return response


class LiveExecutionTests(unittest.TestCase):
    def setUp(self):
        test_live_admission.LiveAdmissionTests.setUp(self)
        self.payload['launch_profile']['cmd']=WORKER_CMD
        self.live.approve(self.owner,self.project,self.signed())
        self.http=HTTP();self.billing_secret=b'fictional-billing-key-distinct-12345678'
        self.live._host_keys={'fictional':(self.owner,self.secret)}
        self.live._build_evidence='fictional-evidence'
        self.execution=LiveExecution(self.live,runpod_token='fictional-token',transport=self.http,
                                    billing_keys={'billing':(self.owner,self.billing_secret)})
        self.workers=WorkerTransport(self.control,real_jobs=self.execution)
        self.job=self.live.submit(self.owner,self.project,self.request)['batch']['id']
        self.credential=self.workers.issue(self.owner,self.project,self.job,'worker',ttl_seconds=300)
        self.auth='Bearer '+self.credential['token']
        host=dict(owner=self.owner,project=self.project,config_hash=configuration_hash(self.profile,self.payload['launch_profile']),
                  source_sha256=self.payload['source_sha256'],build_manifest_sha256='a'*64,
                  valid_until=self.payload['valid_until'],worker_endpoint=self.profile['worker_endpoint'],storage_id=self.profile['storage_id'])
        self.host=self.signed(host,HOST_DOMAIN)
        self.build=patch('services.controller.live_admission._build',return_value={'manifest_sha256':'a'*64})
        self.build.start();self.addCleanup(self.build.stop)

    def signed(self,*args,**kwargs):return test_live_admission.LiveAdmissionTests.signed(self,*args,**kwargs)
    def provision(self):return self.execution.provision(self.owner,self.project,self.job,self.host,worker_token=self.credential['token'])
    def bill(self,kind,amount,key):
        pod=self.execution.status(self.owner,self.project,self.job)['batch']['provider_resource_id']
        payload=dict(id=key,owner=self.owner,project=self.project,batch=self.job,kind=kind,amount_cents=amount,
                     bill_reference='fictional-reconciler',valid_until=stamp(utcnow()+timedelta(hours=1)),provider_resource_id=pod,currency='USD')
        signature=hmac.new(self.billing_secret,(BILLING_DOMAIN+'\n'+canonical(payload)).encode(),hashlib.sha256).hexdigest()
        return dict(key_id='billing',payload=payload,signature=signature)

    def test_startup_claim_is_idle_inside_post_then_resource_claims(self):
        self.assertIsNone(self.workers.call(self.auth,'claim',{}))
        def startup(request):
            self.assertIsNone(self.workers.call(self.auth,'claim',{}))
            self.assertEqual(json.loads(request.data)['env']['WAN_WORKER_TOKEN'],self.credential['token'])
        self.http.on_create=startup
        result=self.provision()
        self.assertEqual(result['batch']['state'],'rendering')
        self.assertIsNotNone(self.workers.call(self.auth,'claim',{}))
        with self.control.transaction() as db:
            for table in ('live_approvals','live_execution_bindings','pod_batches'):
                self.assertNotIn(self.credential['token'],str(db.execute('SELECT * FROM '+table).fetchall()))

    def test_rejection_preserves_billing_reservation_and_private_diagnostic(self):
        calls=[]
        def rejected(request,timeout):
            calls.append(request.get_method())
            raise HTTPError(request.full_url,402,'ignored',{'x-request-id':'fictional-balance'},
                            io.BytesIO(b'{"detail":"Insufficient balance"}'))
        self.execution._transport=rejected
        before=self.execution.status(self.owner,self.project,self.job)['budget']
        result=self.provision()
        self.assertEqual(result['batch']['state'],'failed')
        self.assertEqual(result['batch']['cleanup_state'],'confirmed')
        self.assertEqual(result['budget'],before)
        self.assertNotIn('Insufficient balance',json.dumps(result['batch']))
        self.execution.provision(self.owner,self.project,self.job)
        self.assertEqual(calls,['POST'])
        with self.control.transaction() as db:
            diagnostic=db.execute('SELECT create_diagnostic FROM pod_batches WHERE id=?',(self.job,)).fetchone()[0]
        self.assertEqual(json.loads(diagnostic)['http_status'],402)
        destination=self.control.asset_root.parent/'rejected-backup'
        backup.create_backup(self.control.db_path,self.control.asset_root,destination)
        restored=backup.restore_backup(destination,self.control.asset_root.parent/'rejected-restore')
        import sqlite3
        with sqlite3.connect(restored['database']) as db:
            self.assertEqual(db.execute('SELECT create_diagnostic FROM pod_batches WHERE id=?',
                                       (self.job,)).fetchone()[0],diagnostic)

    def test_multi_location_grant_is_frozen_and_covered_by_host_signature(self):
        self.live.cancel(self.owner,self.project,self.job)
        self.payload['id']='multiple-locations'
        self.payload['launch_profile']['dataCenterIds'].append('fictional-second-location')
        self.live.approve(self.owner,self.project,self.signed())
        self.job=self.live.submit(self.owner,self.project,dict(self.request,approval_id=self.payload['id'],
                                 idempotency_key='multiple-locations'))['batch']['id']
        self.credential=self.workers.issue(self.owner,self.project,self.job,'worker',ttl_seconds=300)
        with self.assertRaises(ValueError): self.provision()
        self.assertEqual(self.http.posts,0)
        self.host=self.signed(dict(self.host['payload'],config_hash=configuration_hash(
            self.profile,self.payload['launch_profile'])),HOST_DOMAIN)
        captured=[]
        self.http.on_create=lambda request:captured.append(json.loads(request.data)['dataCenterIds'])
        self.assertEqual(self.provision()['batch']['state'],'rendering')
        self.assertEqual(captured,[self.payload['launch_profile']['dataCenterIds']])
        self.execution.cancel(self.owner,self.project,self.job)
        self.assertEqual(self.execution.watchdog(),[])
        backup.create_backup(self.control.db_path,self.control.asset_root,
                             self.control.asset_root.parent/'multiple-location-backup')

    def test_unknown_create_restart_cleanup_after_revoke_source_change_and_settle(self):
        self.http.unknown=True
        self.assertEqual(self.provision()['batch']['state'],'provisioning')
        self.live.revoke(self.owner,self.project,self.payload['id'])
        replacement=LiveExecution(self.live,runpod_token='fictional',transport=self.http,billing_keys={'billing':(self.owner,self.billing_secret)})
        with patch('services.controller.live_admission._sources',return_value={'changed':'source'}):
            result=replacement.provision(self.owner,self.project,self.job)
            self.assertEqual(result['batch']['state'],'rendering')
            replacement.cancel(self.owner,self.project,self.job)
            self.assertEqual(replacement.watchdog(),[])
        self.assertEqual(self.http.posts,1)
        self.assertEqual(replacement.status(self.owner,self.project,self.job)['budget']['reserved_cents'],60)
        receipt=self.bill('settlement',40,'final')
        self.assertEqual(replacement.ingest_bill(self.owner,self.project,receipt)['spent_cents'],40)
        self.assertEqual(replacement.ingest_bill(self.owner,self.project,receipt)['spent_cents'],40)
        late=self.bill('charge',80,'late')
        self.assertEqual(replacement.ingest_bill(self.owner,self.project,late)['spent_cents'],120)

    def test_late_charge_blocks_previously_reserved_launch_and_wrong_billing_key(self):
        self.provision()
        second=dict(self.request,reservation_cents=40,idempotency_key='second')
        queued=self.live.submit(self.owner,self.project,second)['batch']['id']
        token=self.workers.issue(self.owner,self.project,queued,'second-worker',ttl_seconds=300)['token']
        receipt=self.bill('charge',101,'overrun')
        with self.assertRaises(PermissionError):
            self.execution.ingest_bill(self.owner,self.project,self.signed(receipt['payload'],BILLING_DOMAIN))
        self.execution.ingest_bill(self.owner,self.project,receipt)
        with self.assertRaises(ValueError):
            self.execution.provision(self.owner,self.project,queued,self.host,worker_token=token)
        self.assertEqual(self.http.posts,1)

    def test_default_no_transport_and_tampered_host_fail_before_post(self):
        closed=LiveExecution(self.live)
        with self.assertRaises(ValueError):closed.provision(self.owner,self.project,self.job,self.host,worker_token=self.credential['token'])
        altered=deepcopy(self.host);altered['payload']['storage_id']='changed'
        with self.assertRaises(PermissionError):self.execution.provision(self.owner,self.project,self.job,altered,worker_token=self.credential['token'])
        self.assertEqual(self.http.posts,0)
        with self.control.transaction() as db:self.assertEqual(db.execute('SELECT COUNT(*) FROM live_execution_bindings').fetchone()[0],0)

    def test_watchdog_ignores_not_due_and_confirmed_without_credentials(self):
        closed=LiveExecution(self.live)
        self.assertEqual(closed.watchdog(),[])
        self.provision()
        self.execution.cancel(self.owner,self.project,self.job)
        self.assertEqual(self.execution.watchdog(),[])
        self.assertEqual(closed.watchdog(),[])

    def test_last_failed_attempt_closes_batch_and_deletes_without_another_claim(self):
        self.control.max_attempts = 1
        self.provision()
        claim = self.workers.call(self.auth, 'claim', {})
        attempt = claim['attempt']
        self.workers.call(self.auth, f"attempts/{attempt['id']}/fail",
                          {'lease_id':attempt['lease_id'], 'code':'gpu_out_of_memory'})
        self.assertEqual(self.execution.status(self.owner,self.project,self.job)['batch']['state'], 'failed')
        self.assertEqual(self.control.bundle(self.owner,self.project)['attempts'][0]['failure_reason'], 'gpu_out_of_memory')
        self.assertEqual(self.execution.watchdog(), [])
        self.assertEqual(self.execution.status(self.owner,self.project,self.job)['batch']['cleanup_state'], 'confirmed')
        self.assertEqual(self.http.pods, {})
        self.assertEqual(self.http.posts, 1)
