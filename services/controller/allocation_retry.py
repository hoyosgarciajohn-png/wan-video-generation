"""Opt-in allocation retries after one exact, definitive no-capacity response."""
import time

from services.controller.runpod import ProviderCreateError, ProviderCreateRejected

CAPACITY_DETAIL = ('There are no longer any instances available with the requested '
                   'specifications. Please refresh and try again.')
POLICY = {'max_attempts': 3, 'delay_seconds': 15, 'min_remaining_seconds': 120}


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
            except (ValueError, PermissionError, ConnectionError):
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
