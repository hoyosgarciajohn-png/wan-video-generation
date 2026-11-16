"""Fictional capacity responses, clocks and signed grants; never provider traffic."""
import io
import json
from datetime import timedelta
import sqlite3
import unittest
from unittest.mock import patch
from urllib.error import HTTPError

from tests import test_live_execution
from services.controller.allocation_retry import CAPACITY_DETAIL, POLICY
from services.controller import backup


class AllocationRetryTests(unittest.TestCase):
    def setUp(self):
        self.f = f = test_live_execution.LiveExecutionTests()
        f.setUp()
        self.addCleanup(f.doCleanups)
        f.live.cancel(f.owner,f.project,f.job)
        f.payload.update(id='fictional-capacity', max_runtime_seconds=300, capacity_retry=dict(POLICY))
        f.live.approve(f.owner,f.project,f.signed())
        f.request.update(approval_id=f.payload['id'], idempotency_key='fictional-capacity', runtime_seconds=300,
                         expected_revision=f.studio.get(f.owner)['revision'])
        f.job=f.live.submit(f.owner,f.project,f.request)['batch']['id']
        f.credential=f.workers.issue(f.owner,f.project,f.job,'worker',ttl_seconds=600)
        self.posts=0
        self.sleep=patch('services.controller.allocation_retry.time.sleep')
        self.sleep_mock=self.sleep.start();self.addCleanup(self.sleep.stop)

    def transport(self, outcomes):
        f=self.f
        def call(request, timeout):
            if request.get_method()=='POST':
                outcome=outcomes[min(self.posts,len(outcomes)-1)];self.posts+=1
                if isinstance(outcome,tuple):
                    status,detail=outcome
                    raise HTTPError(request.full_url,status,'fictional',{'x-request-id':'fictional-'+str(self.posts)},
                                    io.BytesIO(json.dumps({'detail':detail}).encode()))
                if outcome=='lost':f.http.unknown=True
                if outcome=='crash':raise SystemExit('fictional crash before response')
            return f.http(request,timeout)
        f.execution._transport=call

    def history(self):
        with self.f.control.transaction() as db:
            return json.loads(db.execute('SELECT allocation_attempts FROM live_execution_bindings WHERE batch=?',
                                         (self.f.job,)).fetchone()[0])

    def test_rejected_twice_then_one_allocation_and_no_replay(self):
        self.transport([(400,CAPACITY_DETAIL),(400,CAPACITY_DETAIL),'ok'])
        result=self.f.provision()
        self.assertEqual(result['batch']['state'],'rendering')
        self.assertEqual(self.posts,3);self.assertEqual(len(self.f.http.pods),1)
        self.assertEqual([x['result']['outcome'] for x in self.history()],['rejected','rejected','allocated'])
        self.f.execution.provision(self.f.owner,self.f.project,self.f.job)
        self.assertEqual(self.posts,3)
        self.f.execution.cancel(self.f.owner,self.f.project,self.f.job)
        self.assertEqual(self.f.execution.watchdog(),[])
        path=self.f.control.asset_root.parent/'retry-backup'
        backup.create_backup(self.f.control.db_path,self.f.control.asset_root,path)
        restored=backup.restore_backup(path,self.f.control.asset_root.parent/'retry-restored')
        with sqlite3.connect(restored['database']) as db:
            self.assertEqual(json.loads(db.execute('SELECT allocation_attempts FROM live_execution_bindings WHERE batch=?',
                                                  (self.f.job,)).fetchone()[0]),self.history())

    def test_three_rejections_exhaust_cap_without_new_reservation_or_deadline(self):
        before=self.f.execution.status(self.f.owner,self.f.project,self.f.job)
        self.transport([(400,CAPACITY_DETAIL)])
        after=self.f.provision()
        self.assertEqual(self.posts,3)
        self.assertEqual(after['batch']['cleanup_state'],'confirmed')
        self.assertEqual(after['budget'],before['budget'])
        self.assertEqual(after['batch']['deadline_at'],before['batch']['deadline_at'])
        self.assertEqual(after['reservation_state'],'reserved')

    def test_unknown_response_stops_and_restart_only_reconciles(self):
        self.transport([(400,CAPACITY_DETAIL),'lost'])
        self.assertEqual(self.f.provision()['batch']['state'],'provisioning')
        self.assertEqual(self.posts,2)
        self.assertEqual(self.history()[-1]['result']['outcome'],'unknown')
        self.assertEqual(self.f.execution.provision(self.f.owner,self.f.project,self.f.job)['batch']['state'],'rendering')
        self.assertEqual(self.posts,2)

    def test_other_400_and_server_failure_do_not_retry(self):
        self.transport([(400,'Invalid image')])
        self.assertEqual(self.f.provision()['batch']['cleanup_state'],'confirmed')
        self.assertEqual(self.posts,1)

    def test_500_with_capacity_text_is_uncertain_not_retryable(self):
        self.transport([(500,CAPACITY_DETAIL)])
        self.assertEqual(self.f.provision()['batch']['state'],'provisioning')
        self.assertEqual(self.posts,1)

    def test_deadline_during_backoff_prevents_next_post(self):
        self.transport([(400,CAPACITY_DETAIL)])
        original=self.f.control.clock
        self.sleep_mock.side_effect=lambda _:setattr(self.f.control,'clock',lambda:original()+timedelta(seconds=299))
        self.assertEqual(self.f.provision()['batch']['cleanup_state'],'confirmed')
        self.assertEqual(self.posts,1)

    def test_cancellation_during_backoff_prevents_next_post(self):
        self.transport([(400,CAPACITY_DETAIL)])
        self.sleep_mock.side_effect=lambda _:self.f.execution.cancel(self.f.owner,self.f.project,self.f.job)
        result=self.f.provision()
        self.assertEqual(result['batch']['state'],'canceled')
        self.assertEqual(result['batch']['cleanup_state'],'confirmed')
        self.assertEqual(self.posts,1)

    def test_revocation_during_backoff_prevents_next_post(self):
        self.transport([(400,CAPACITY_DETAIL)])
        self.sleep_mock.side_effect=lambda _:self.f.live.revoke(self.f.owner,self.f.project,self.f.payload['id'])
        self.assertEqual(self.f.provision()['batch']['cleanup_state'],'confirmed')
        self.assertEqual(self.posts,1)

    def test_crash_after_start_is_never_reposted(self):
        self.transport(['crash'])
        with self.assertRaises(SystemExit):self.f.provision()
        self.assertNotIn('result',self.history()[0])
        self.f.execution.provision(self.f.owner,self.f.project,self.f.job)
        self.assertEqual(self.posts,1)

    def test_signed_policy_cannot_expand_attempts_or_use_boolean(self):
        for value in (4,True):
            payload=dict(self.f.payload,id='fictional-invalid',capacity_retry=dict(POLICY,max_attempts=value))
            with self.assertRaises(ValueError):self.f.live.approve(self.f.owner,self.f.project,self.f.signed(payload))
