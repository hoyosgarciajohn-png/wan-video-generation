"""Fictional trial gates and real saved build-evidence consistency; no network."""
import json
import importlib
import sqlite3
from pathlib import Path
import tempfile
import time
import unittest
from unittest.mock import patch

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

    def test_materialize_approved_diagnostic_image_and_isolate_authority(self):
        old_paths=(first_trial.TRIAL,first_trial.AUTH)
        first_trial.select_trial('diagnostic')
        self.assertNotEqual((first_trial.TRIAL,first_trial.AUTH),old_paths)
        self.assertEqual(first_trial.DURATION_MS,1000)
        self.assertEqual(first_trial.APPROVAL_ID,'john-diagnostic-trial-20261116')
        with tempfile.TemporaryDirectory() as t:
            result = first_trial.materialize_build(Path(t) / 'build')
            self.assertEqual(result['image_ref'], first_trial.IMAGE)
            self.assertEqual(result['assurance'], 'local_evidence_consistency_only_not_registry_or_gpu_acceptance')

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
