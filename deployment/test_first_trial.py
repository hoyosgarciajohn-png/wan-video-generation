"""Fictional trial gates and real saved build-evidence consistency; no network."""
import json
import importlib
import sqlite3
from pathlib import Path
import tempfile
import time
import unittest
from unittest.mock import patch
from contextlib import contextmanager

from deployment import first_trial
from services.controller.service import canonical
from services.controller.runpod import RunpodProvider
from tests.test_live_execution import LiveExecutionTests
from services.controller.live_execution import BOOTSTRAP_CMD, BOOTSTRAP_ENTRYPOINT
from services.controller.live_admission import HOST_DOMAIN, configuration_hash


class FirstTrialGates(unittest.TestCase):
    def setUp(self):
        importlib.reload(first_trial)
        self.addCleanup(importlib.reload, first_trial)

    def test_consumed_old_image_cannot_match_changed_worker_source(self):
        with tempfile.TemporaryDirectory() as t:
            with self.assertRaises(AssertionError):
                first_trial.materialize_build(Path(t) / 'build')

    def test_consumed_diagnostic_image_is_isolated_and_rejected_after_repair(self):
        old_paths=(first_trial.TRIAL,first_trial.AUTH)
        first_trial.select_trial('diagnostic')
        self.assertNotEqual((first_trial.TRIAL,first_trial.AUTH),old_paths)
        self.assertEqual(first_trial.DURATION_MS,1000)
        self.assertEqual(first_trial.APPROVAL_ID,'john-diagnostic-trial-20261116')
        with tempfile.TemporaryDirectory() as t:
            with self.assertRaises(AssertionError):
                first_trial.materialize_build(Path(t) / 'build')

    def test_repair_uses_verified_image_and_fresh_isolated_scope(self):
        first_trial.select_trial('diagnostic')
        previous=(first_trial.TRIAL,first_trial.AUTH,first_trial.APPROVAL_ID)
        first_trial.select_trial('repair')
        self.assertTrue(all(a!=b for a,b in zip(previous,(first_trial.TRIAL,first_trial.AUTH,first_trial.APPROVAL_ID))))
        self.assertEqual(first_trial.DURATION_MS,1000)
        self.assertEqual(len(first_trial.EXPECTED_PRIOR_BATCHES),2)
        with tempfile.TemporaryDirectory() as t:
            # Historical immutable image is intentionally incompatible with the new worker.
            with self.assertRaises(AssertionError):first_trial.materialize_build(Path(t)/'build')
        proposal=first_trial.read(first_trial.ROOT/'deployment/repair-trial-proposal.json')
        proposal['proposed_additional_terms']['render_attempts']=2
        with patch.object(first_trial,'read',return_value=proposal), self.assertRaises(AssertionError):
            first_trial.select_trial('repair')

    def test_repair_requires_both_prior_cleanups_and_rejects_replay(self):
        first_trial.select_trial('repair')
        with sqlite3.connect(':memory:') as db:
            db.execute('CREATE TABLE live_job_links(batch TEXT)')
            db.execute('CREATE TABLE pod_batches(id TEXT,state TEXT,cleanup TEXT)')
            for previous in first_trial.EXPECTED_PRIOR_BATCHES:
                db.execute('INSERT INTO live_job_links VALUES (?)',(previous,))
                db.execute("INSERT INTO pod_batches VALUES (?,'failed','confirmed')",(previous,))
            first_trial.prior_history_closed(db)
            db.execute("UPDATE pod_batches SET cleanup='pending' WHERE id=?",(previous,))
            with self.assertRaises(AssertionError):first_trial.prior_history_closed(db)
            db.execute("UPDATE pod_batches SET cleanup='confirmed'")
            db.execute("INSERT INTO live_job_links VALUES ('already-repair')")
            with self.assertRaises(AssertionError):first_trial.prior_history_closed(db)

    def test_validation_is_isolated_and_preserves_only_the_authorized_unknown(self):
        first_trial.select_trial('repair')
        previous=(first_trial.TRIAL,first_trial.AUTH,first_trial.APPROVAL_ID)
        first_trial.select_trial('validation')
        self.assertTrue(all(a!=b for a,b in zip(previous,(first_trial.TRIAL,first_trial.AUTH,first_trial.APPROVAL_ID))))
        self.assertEqual(first_trial.DURATION_MS,1000)
        self.assertEqual(len(first_trial.EXPECTED_PRIOR_BATCHES),3)
        with sqlite3.connect(':memory:') as db:
            from deployment.test_validation_policy import fixture
            fixture(db)
            for batch in first_trial.EXPECTED_PRIOR_BATCHES:
                if batch == first_trial.validation_policy.OLD_BATCH: continue
                db.execute("INSERT INTO live_job_links VALUES (?,'fictional','fictional','attempted')",(batch,))
                db.execute("INSERT INTO pod_batches VALUES (?,'fictional','failed','confirmed',NULL,1)",(batch,))
            first_trial.prior_history_closed(db)
            self.assertEqual(db.execute('SELECT cleanup FROM pod_batches WHERE id=?',(first_trial.validation_policy.OLD_BATCH,)).fetchone()[0],'failed')
            # Only a definitive reconciliation may change this in real state.
            db.execute("UPDATE pod_batches SET cleanup='confirmed'")
            first_trial.prior_history_closed(db)
            db.execute("INSERT INTO live_job_links VALUES ('already-validation','fictional','fictional','disabled')")
            with self.assertRaises(AssertionError):first_trial.prior_history_closed(db)

    def test_fallback_scope_and_quote_bind_only_approved_gpus(self):
        first_trial.select_trial('fallback')
        self.assertEqual(len(first_trial.EXPECTED_PRIOR_BATCHES),4)
        self.assertTrue(first_trial.CAPACITY_RETRY)
        self.assertTrue(first_trial.ALLOW_KNOWN_UNKNOWN)
        self.assertEqual(str(first_trial.HOURLY_CEILING),'1.10')
        value={'id':'NVIDIA L40S','secure':True,'price':{'secure':1.09},
               'dataCenters':[{'id':'EUR-IS-2','availability':'LOW'}]}
        with patch.object(first_trial,'catalog_snapshot',return_value=value):
            self.assertEqual(first_trial.checked_quote()['gpu'],'NVIDIA L40S')
            self.assertEqual(first_trial.checked_quote(['EUR-IS-2'])['gpu'],'NVIDIA L40S')
            value['id']='NVIDIA H100'
            with self.assertRaises(AssertionError):first_trial.checked_quote()
            value['id']='NVIDIA L40S';value['price']['secure']=1.11
            with self.assertRaises(AssertionError):first_trial.checked_quote()
        first_trial.select_trial('validation')
        self.assertFalse(first_trial.CAPACITY_RETRY)
        self.assertEqual(first_trial.GPU,'NVIDIA GeForce RTX 4090')
        self.assertEqual(str(first_trial.HOURLY_CEILING),'1.00')

    def test_diagnostic_requires_exact_closed_prior_trial(self):
        first_trial.select_trial('diagnostic')
        with sqlite3.connect(':memory:') as db:
            db.execute('CREATE TABLE live_job_links(batch TEXT)')
            db.execute('CREATE TABLE pod_batches(id TEXT,state TEXT,cleanup TEXT)')
            with self.assertRaises(AssertionError):first_trial.prior_history_closed(db)
            previous=next(iter(first_trial.EXPECTED_PRIOR_BATCHES))
            db.execute('INSERT INTO live_job_links VALUES (?)',(previous,))
            db.execute("INSERT INTO pod_batches VALUES (?,'failed','confirmed')",(previous,))
            first_trial.prior_history_closed(db)
            db.execute("UPDATE pod_batches SET cleanup='pending'")
            with self.assertRaises(AssertionError):first_trial.prior_history_closed(db)
            db.execute("UPDATE pod_batches SET cleanup='confirmed'")
            db.execute("INSERT INTO live_job_links VALUES ('already-diagnostic')")
            with self.assertRaises(AssertionError):first_trial.prior_history_closed(db)

    def test_unapproved_or_unknown_trial_refused(self):
        with self.assertRaises(AssertionError):first_trial.select_trial('third')
        proposal=first_trial.read(first_trial.ROOT/'deployment/diagnostic-trial-proposal.json')
        proposal['status']='PENDING_FRESH_OWNER_APPROVAL'
        with patch.object(first_trial,'read',return_value=proposal):
            with self.assertRaises(AssertionError):first_trial.select_trial('diagnostic')

    def test_quote_requires_available_region_and_ceiling(self):
        value = {'id':first_trial.GPU, 'secure':True, 'price':{'secure':0.89},
                 'dataCenters':[{'id':'US-IL-1','availability':'LOW'}]}
        with patch.object(first_trial,'catalog_snapshot', return_value=value):
            self.assertEqual(first_trial.checked_quote()['region'],'US-IL-1')
            with self.assertRaises(AssertionError): first_trial.checked_quote('unavailable')
            value['dataCenters']=[{'id':'EUR-IS-2','availability':'LOW'}]
            self.assertEqual(first_trial.checked_quote()['region'],'EUR-IS-2')
            value['dataCenters'][0]['availability']='NONE'
            with self.assertRaises(AssertionError): first_trial.checked_quote()
            value['dataCenters'][0]['availability']='LOW'
            value['dataCenters'][0]['id']='EU-CZ-1'
            self.assertEqual(first_trial.checked_quote()['region'],'EU-CZ-1')
            # A prepared grant stays bound to its location; do not migrate it.
            with self.assertRaises(AssertionError): first_trial.checked_quote('EUR-IS-2')
            value['price']['secure']=1.01
            with self.assertRaises(AssertionError): first_trial.checked_quote()

    def test_catalog_record_cannot_be_reused_after_freshness_window(self):
        with tempfile.TemporaryDirectory() as t:
            path=Path(t)/'quote.json'
            with patch.object(first_trial,'QUOTE_FILE',path):
                path.write_text(json.dumps({'observed_at':time.time(),'data':{'id':'fictional'}}))
                self.assertEqual(first_trial.catalog_snapshot()['id'],'fictional')
                for observed in (time.time()-181,time.time()+30):
                    path.write_text(json.dumps({'observed_at':observed,'data':{}}))
                    with self.assertRaises(AssertionError): first_trial.catalog_snapshot()

    def test_unregistered_validation_refreshes_locations_without_expanding_budget(self):
        first_trial.select_trial('validation')
        with tempfile.TemporaryDirectory() as t, sqlite3.connect(':memory:') as db, patch.object(first_trial,'TRIAL',Path(t)):
            db.execute('CREATE TABLE live_approvals(id TEXT)')
            db.execute('CREATE TABLE live_job_links(project TEXT)')
            class Control:
                @contextmanager
                def transaction(self): yield db
            saved=dict(project='fictional-project', pricing=dict(region='US-TX-3',data_center_ids=['US-TX-3']))
            grant=dict(id=first_trial.APPROVAL_ID,owner=first_trial.OWNER,project=saved['project'],approved_cents=400,max_runtime_seconds=1800,
                       profile=dict(region='US-TX-3',image_ref='fictional/image@sha256:'+'a'*64,gpu_count=1,
                                    model_profile=first_trial.LOCK['profile'],gpu_type=first_trial.GPU,
                                    worker_endpoint='https://fictional.example',storage_id='fictional'),
                       launch_profile=dict(image='fictional/image@sha256:'+'a'*64,cloud='SECURE',mounts={},ports=[],env={},
                                           dataCenterIds=['US-TX-3'],gpu=dict(id=first_trial.GPU,count=1,minRamPerGpu=64),disk=80))
            original=dict(payload=grant,signature='fictional-previous-signature')
            (Path(t)/'approval.json').write_text(json.dumps(original))
            (Path(t)/'host.json').write_text(json.dumps(dict(payload=dict(project=saved['project']))))
            quote=dict(region='EU-RO-1',data_center_ids=['EU-RO-1','EUR-IS-1'],usd_per_hour='0.89')
            with patch.object(first_trial,'prior_history_closed'), patch.object(first_trial,'checked_quote',return_value=quote), \
                 patch.object(first_trial,'_sources',return_value={'fictional':'current'}), \
                 patch.object(first_trial,'sign',side_effect=lambda value,*_:dict(payload=value,signature='fictional-refreshed')):
                changed=first_trial.refresh_unregistered_validation(Control(),saved)
                updated=json.loads((Path(t)/'approval.json').read_text())['payload']
                self.assertEqual(updated['launch_profile']['dataCenterIds'],['EU-RO-1','EUR-IS-1','US-TX-3'])
                self.assertEqual(updated['launch_profile']['gpu'],grant['launch_profile']['gpu'])
                self.assertEqual((updated['approved_cents'],updated['max_runtime_seconds']),(400,1800))
                archived=list((Path(t)/'pre-admission-history').glob('*.json'))
                self.assertEqual(len(archived),1)
                self.assertEqual(json.loads(archived[0].read_text())['approval'],original)
                # Registration makes the signature immutable even without a job file.
                db.execute('INSERT INTO live_approvals VALUES (?)',(first_trial.APPROVAL_ID,))
                frozen=(Path(t)/'approval.json').read_bytes()
                first_trial.refresh_unregistered_validation(Control(),changed)
                self.assertEqual((Path(t)/'approval.json').read_bytes(),frozen)
                (Path(t)/'job.json').write_text('{}')
                with self.assertRaises(AssertionError): first_trial.refresh_unregistered_validation(Control(),changed)

    def test_quote_freezes_multiple_locations_and_only_rechecks_that_list(self):
        value = {'id':first_trial.GPU,'secure':True,'price':{'secure':0.89},'dataCenters':[
            {'id':'US-IL-1','availability':'LOW'}, {'id':'EU-RO-1','availability':'LOW'},
            {'id':'EUR-IS-1','availability':'NONE'}]}
        with patch.object(first_trial,'catalog_snapshot',return_value=value):
            selected=first_trial.checked_quote()['data_center_ids']
            self.assertEqual(selected,['EU-RO-1','US-IL-1'])
            value['dataCenters'][1]['availability']='NONE'
            value['dataCenters'][2]['availability']='HIGH'
            self.assertEqual(first_trial.checked_quote(selected)['data_center_ids'],selected)
            value['dataCenters'][0]['availability']='NONE'
            with self.assertRaises(AssertionError):first_trial.checked_quote(selected)

    def test_allocation_scope_keeps_limits_and_five_prior_scopes(self):
        first_trial.select_trial('fallback')
        previous=(first_trial.TRIAL,first_trial.AUTH,first_trial.APPROVAL_ID)
        first_trial.select_trial('allocation')
        self.assertTrue(all(a!=b for a,b in zip(previous,(first_trial.TRIAL,first_trial.AUTH,first_trial.APPROVAL_ID))))
        self.assertEqual(len(first_trial.EXPECTED_PRIOR_BATCHES),5)
        self.assertEqual(str(first_trial.HOURLY_CEILING),'4.50')
        self.assertTrue(first_trial.MULTI_GPU and first_trial.ALLOW_KNOWN_UNKNOWN)
        self.assertEqual(first_trial.DURATION_MS,1000)

    def test_allocation_quotes_rank_capacity_and_preserve_admitted_plan(self):
        first_trial.select_trial('allocation')
        def gpu(identity,price,stock,locations):
            return dict(id=identity,secure=True,availability=stock,price=dict(secure=price),
                        dataCenters=[dict(id=x,availability='LOW') for x in locations])
        values=dict(gpus=[gpu('NVIDIA A100-SXM4-80GB',2.19,'LOW',['fictional-a']),
                          gpu('NVIDIA H100 80GB HBM3',4.39,'MEDIUM',['fictional-b','fictional-c']),
                          gpu('NVIDIA H100 NVL',4.51,'LOW',['fictional-d'])])
        with patch.object(first_trial,'catalog_snapshot',return_value=values):
            selected=first_trial.checked_quote()
            self.assertEqual(selected['gpu'],'NVIDIA H100 80GB HBM3')
            self.assertEqual(len(selected['allocation_plan']['candidates']),2)
            frozen=json.loads(json.dumps(selected['allocation_plan']))
            values['gpus'][1]['availability']='NONE'
            self.assertEqual(first_trial.checked_quote(frozen)['allocation_plan'],frozen)
            self.assertFalse(first_trial.candidate_available(frozen['candidates'][0],450))
            values['gpus'][0]['price']['secure']=4.51
            with self.assertRaises(AssertionError):first_trial.checked_quote(frozen)

    def test_guard_receipt_is_bound_and_fresh(self):
        with tempfile.TemporaryDirectory() as t, patch.object(first_trial,'TRIAL',Path(t)):
            job={'batch':'fictional-batch','scope':canonical(['fictional-owner','fictional-project']), 'deadline':int(time.time())+600}
            name=RunpodProvider('fictional-token',scope=job['scope'])._name(job['batch'],job['batch'])
            ready=dict(job,status='READY',provider_name=name,checked_at=time.time(),run_id='123')
            path=Path(t)/'guard-ready.json'
            path.write_text(json.dumps(ready)); first_trial.guard_ready(job)
            for key,value in [('batch','other'),('scope','[]'),('deadline',job['deadline']+1),('checked_at',time.time()-181),('provider_name','other')]:
                path.write_text(json.dumps(dict(ready,**{key:value})))
                with self.assertRaises(AssertionError): first_trial.guard_ready(job)

    def test_operator_line_keeps_status_visible_without_large_prompt(self):
        summary = dict(checked_at=1, batch=dict(id='fictional',state='provisioning',
            cleanup_state='pending',provider_resource_id=None,deadline_at='2026-11-16T15:33:20Z',
            shot_snapshots=[{'prompt':'private-prompt' * 10000}]), takes=[], attempts=[],
            billing={'status':'NO_POD_ID'},reservation_state='reserved')
        message=json.dumps(first_trial.operator_summary(summary))
        self.assertLess(len(message),1000)
        self.assertIn('provisioning',message)
        self.assertNotIn('private-prompt',message)
        self.assertIn('shot_snapshots',summary['batch'])


class BootstrapExecutionTests(LiveExecutionTests):
    def setUp(self):
        super().setUp()

    def test_only_exact_pinned_downloader_bootstrap_can_dispatch(self):
        # Bind a fresh fictional grant to the exact bootstrap and valid host floor.
        self.payload['id']='bootstrap-grant'
        self.payload['launch_profile'].update(cmd=BOOTSTRAP_CMD,entrypoint=BOOTSTRAP_ENTRYPOINT)
        self.payload['launch_profile']['gpu']['minCudaVersion']='12.8'
        self.payload['launch_profile']['gpu']['minRamPerGpu']=64
        self.live.approve(self.owner,self.project,self.signed())
        self.live.cancel(self.owner,self.project,self.job)
        request=dict(self.request,approval_id='bootstrap-grant',idempotency_key='bootstrap-job')
        self.job=self.live.submit(self.owner,self.project,request)['batch']['id']
        self.credential=self.workers.issue(self.owner,self.project,self.job,'worker',ttl_seconds=300)
        host=dict(self.host['payload'],config_hash=configuration_hash(self.profile,self.payload['launch_profile']))
        self.host=self.signed(host,HOST_DOMAIN)
        self.assertEqual(self.provision()['batch']['state'],'rendering')
        self.assertEqual(self.http.posts,1)

    def test_arbitrary_bootstrap_shell_is_rejected_before_create(self):
        self.payload['id']='tampered-command'
        self.payload['launch_profile'].update(cmd=[BOOTSTRAP_CMD[0]+'; echo unsafe'],entrypoint=BOOTSTRAP_ENTRYPOINT)
        self.live.approve(self.owner,self.project,self.signed())
        self.live.cancel(self.owner,self.project,self.job)
        self.job=self.live.submit(self.owner,self.project,dict(self.request,approval_id=self.payload['id'],idempotency_key='altered-job'))['batch']['id']
        self.credential=self.workers.issue(self.owner,self.project,self.job,'worker',ttl_seconds=300)
        self.host=self.signed(dict(self.host['payload'],config_hash=configuration_hash(self.profile,self.payload['launch_profile'])),HOST_DOMAIN)
        with self.assertRaises(ValueError): self.provision()
        self.assertEqual(self.http.posts,0)

class ComparisonScopeGates(unittest.TestCase):
    def test_pair_scope_is_fresh_and_all_six_historical_grants_remain_closed(self):
        importlib.reload(first_trial)
        self.addCleanup(importlib.reload,first_trial)
        original=first_trial.read
        def approved(path):
            value=original(path)
            if str(path).endswith('duration-comparison-proposal.json'):
                value['image']='ghcr.io/fictional/worker@sha256:'+'a'*64
            return value
        with patch.object(first_trial,'read',side_effect=approved):first_trial.select_trial('comparison')
        self.assertEqual(first_trial.RUNTIME_SECONDS,2700)
        self.assertEqual(len(first_trial.EXPECTED_PRIOR_BATCHES),6)
        self.assertEqual(first_trial.GPU,'NVIDIA H100 80GB HBM3')
        self.assertEqual(str(first_trial.HOURLY_CEILING),'4.50')
        self.assertTrue(first_trial.ALLOW_KNOWN_UNKNOWN)
        self.assertNotIn('allocation-trial',str(first_trial.TRIAL))
