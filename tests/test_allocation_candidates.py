"""Fictional candidate switching through signed admission and durable lifecycle."""
from copy import deepcopy
import json
import sqlite3
from unittest.mock import patch

from tests import test_allocation_retry
from services.controller.allocation_retry import CAPACITY_DETAIL, ALLOCATION_GPUS
from services.controller.live_admission import configuration_hash, HOST_DOMAIN
from services.controller import backup


class AllocationCandidateTests(test_allocation_retry.AllocationRetryTests):
    def setUp(self):
        super().setUp()
        f = self.f
        f.live.cancel(f.owner, f.project, f.job)
        f.payload['id'] = 'fictional-candidates'
        f.payload['launch_profile']['gpu'].update(id=ALLOCATION_GPUS[0], minCudaVersion='12.8', minRamPerGpu=64)
        f.payload['launch_profile'].update(disk=80, mounts={})
        f.payload['profile']['gpu_type'] = ALLOCATION_GPUS[0]
        regions = f.payload['launch_profile']['dataCenterIds']
        f.payload['allocation_plan'] = dict(max_hourly_cents=450, candidates=[
            dict(gpu_type=g, data_center_ids=regions if i == 0 else ['fictional-dc-'+str(i)])
            for i, g in enumerate(ALLOCATION_GPUS[:3])])
        f.live.approve(f.owner, f.project, f.signed())
        f.request.update(approval_id=f.payload['id'], idempotency_key='fictional-candidates',
                         expected_revision=f.studio.get(f.owner)['revision'])
        f.job = f.live.submit(f.owner, f.project, f.request)['batch']['id']
        f.credential = f.workers.issue(f.owner, f.project, f.job, 'worker', ttl_seconds=600)
        f.host = f.signed(dict(f.host['payload'], config_hash=configuration_hash(
            f.payload['profile'], f.payload['launch_profile'], f.payload['allocation_plan'])), HOST_DOMAIN)
        f.execution._candidate_check = lambda candidate, ceiling: True
        self.requests = []

    def transport(self, outcomes):
        super().transport(outcomes)
        original = self.f.execution._transport
        def record(request, timeout):
            if request.get_method() == 'POST': self.requests.append(json.loads(request.data))
            return original(request, timeout)
        self.f.execution._transport = record

    def test_switches_gpu_locations_preserving_identity_and_constraints(self):
        self.transport([(400, CAPACITY_DETAIL), (400, CAPACITY_DETAIL), 'ok'])
        before = self.f.execution.status(self.f.owner, self.f.project, self.f.job)
        after = self.f.provision()
        self.assertEqual([r['gpu']['id'] for r in self.requests], list(ALLOCATION_GPUS[:3]))
        self.assertEqual(len({r['name'] for r in self.requests}), 1)
        self.assertEqual([x['candidate'] for x in self.history()], [0, 1, 2])
        self.assertEqual(before['budget'], after['budget'])
        self.assertEqual(before['batch']['deadline_at'], after['batch']['deadline_at'])
        for r in self.requests:
            self.assertEqual((r['disk'], r['gpu']['minRamPerGpu'], r['gpu']['minCudaVersion']), (80, 64, '12.8'))
            self.assertEqual(r['env']['WAN_WORKER_TOKEN'], self.f.credential['token'])
        self.assertNotIn(self.f.credential['token'], json.dumps(self.history()))

    def test_skips_unavailable_candidate_and_never_repeats_one(self):
        self.f.execution._candidate_check = lambda candidate, ceiling: candidate['gpu_type'] != ALLOCATION_GPUS[0]
        self.transport([(400, CAPACITY_DETAIL)])
        self.assertEqual(self.f.provision()['batch']['cleanup_state'], 'confirmed')
        self.assertEqual(self.posts, 2)
        self.assertEqual([x['candidate'] for x in self.history()], [1, 2])

    def test_stale_quote_after_rejection_stops_before_next_post(self):
        self.transport([(400, CAPACITY_DETAIL)])
        def expire(_):
            def stale(*_): raise AssertionError('fictional stale quote')
            self.f.execution._candidate_check = stale
        self.sleep_mock.side_effect = expire
        self.assertEqual(self.f.provision()['batch']['cleanup_state'], 'confirmed')
        self.assertEqual(self.posts, 1)

    def test_tampered_plan_ceiling_gpu_and_commands_rejected(self):
        for change in ('ceiling', 'gpu', 'duplicate', 'ram', 'first'):
            p = deepcopy(self.f.payload);p['id']='fictional-'+change
            if change == 'ceiling': p['allocation_plan']['max_hourly_cents'] = 451
            if change == 'gpu': p['allocation_plan']['candidates'][1]['gpu_type'] = 'unapproved'
            if change == 'duplicate': p['allocation_plan']['candidates'][1] = p['allocation_plan']['candidates'][0]
            if change == 'ram': p['launch_profile']['gpu']['minRamPerGpu'] = 32
            if change == 'first': p['allocation_plan']['candidates'][0]['data_center_ids'] = ['elsewhere']
            with self.assertRaises(ValueError): self.f.live.approve(self.f.owner, self.f.project, self.f.signed(p))

    def test_old_host_attestation_does_not_authorize_plan(self):
        f=self.f
        f.host=f.signed(dict(f.host['payload'],config_hash=configuration_hash(f.payload['profile'],f.payload['launch_profile'])),HOST_DOMAIN)
        self.transport(['ok'])
        with self.assertRaises(ValueError):f.provision()
        self.assertEqual(self.posts,0)
