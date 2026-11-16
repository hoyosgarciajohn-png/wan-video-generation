"""Opt-in allocation retries after one exact, definitive no-capacity response."""
import time
from copy import deepcopy

from services.controller.runpod import ProviderCreateError, ProviderCreateRejected, validate_launch_profile

CAPACITY_DETAIL = ('There are no longer any instances available with the requested '
                   'specifications. Please refresh and try again.')
POLICY = {'max_attempts': 3, 'delay_seconds': 15, 'min_remaining_seconds': 120}
ALLOCATION_GPUS = ('NVIDIA GeForce RTX 4090', 'NVIDIA L40S',
                   'NVIDIA A100-SXM4-80GB', 'NVIDIA H100 NVL', 'NVIDIA H100 80GB HBM3')


def candidate_profile(launch, candidate):
    result = deepcopy(launch)
    result['gpu']['id'] = candidate['gpu_type']
    result['dataCenterIds'] = list(candidate['data_center_ids'])
    return validate_launch_profile(result)


def validate_plan(plan, launch):
    if (not isinstance(plan, dict) or set(plan) != {'max_hourly_cents', 'candidates'} or
            type(plan['max_hourly_cents']) is not int or plan['max_hourly_cents'] != 450 or
            not isinstance(plan['candidates'], list) or not 1 <= len(plan['candidates']) <= 5):
        raise ValueError('Exact approved allocation plan required')
    seen = set()
    for candidate in plan['candidates']:
        if (not isinstance(candidate, dict) or set(candidate) != {'gpu_type', 'data_center_ids'} or
                candidate['gpu_type'] not in ALLOCATION_GPUS or candidate['gpu_type'] in seen):
            raise ValueError('Distinct approved GPU candidates required')
        seen.add(candidate['gpu_type'])
        proposed = candidate_profile(launch, candidate)
        if (proposed['gpu'].get('minCudaVersion') != '12.8' or proposed['gpu'].get('minRamPerGpu') != 64 or
                proposed['disk'] != 80 or proposed['mounts'] != {} or proposed['env'] != {}):
            raise ValueError('Candidate hardware and credential constraints changed')
    first = candidate_profile(launch, plan['candidates'][0])
    if first != launch:
        raise ValueError('Primary profile must match first allocation candidate')
    return deepcopy(plan)


def validate_policy(value):
    if (not isinstance(value, dict) or set(value) != set(POLICY) or
            any(type(value[k]) is not int or value[k] != v for k, v in POLICY.items())):
        raise ValueError('Exact bounded capacity retry policy required')
    return dict(value)


def capacity_rejected(diagnostic):
    return (diagnostic.get('kind') == 'http_error' and
            diagnostic.get('http_status') == 400 and
            diagnostic.get('outcome') == 'rejected' and
            diagnostic.get('detail') == CAPACITY_DETAIL)


class CapacityRetryProvider:
    def __init__(self, provider, policy, before, record):
        self.provider, self.policy = provider, validate_policy(policy)
        self.before, self.record = before, record

    def __getattr__(self, name):
        return getattr(self.provider, name)

    def create(self, batch_id, request_key):
        last = None
        for index in range(self.policy['max_attempts']):
            if index:
                time.sleep(self.policy['delay_seconds'])
            try:
                attempt = self.before()
            except (ValueError, PermissionError, ConnectionError, AssertionError):
                if last is not None:
                    raise last
                raise ConnectionError('Allocation authorization unavailable') from None
            try:
                pod = self.provider.create(batch_id, request_key)
            except ProviderCreateError as error:
                self.record(attempt, error.diagnostic)
                if not isinstance(error, ProviderCreateRejected) or not capacity_rejected(error.diagnostic):
                    raise
                last = error
            except (TimeoutError, ConnectionError):
                self.record(attempt, {'outcome': 'unknown', 'kind': 'unclassified_transport'})
                raise
            else:
                self.record(attempt, {'outcome': 'allocated', 'pod_id': pod.id})
                return pod
        raise last
