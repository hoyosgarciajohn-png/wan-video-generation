"""Separate-host deadline fallback for one explicitly bound Pod request.

Has no controller/database dependency and cannot create resources. Start after
admission but before provisioning, verify READY, and keep primary cleanup running.
"""
import json
import os
import re
import time
from pathlib import Path
from deployment.cleanup_monitor import CleanupOnlyProvider
from services.controller.runpod import https_transport
from deployment.validation_policy import OLD_BATCH, OLD_SCOPE


def validate(scope, batch, deadline, now):
    binding = json.loads(scope)
    if (not isinstance(binding, list) or len(binding) != 2 or
            any(not isinstance(v, str) or not 1 <= len(v) <= 200 for v in binding) or
            not re.fullmatch(r'[A-Za-z0-9_-]{1,200}', batch)):
        raise ValueError('Exact owner/project and batch binding required')
    if type(deadline) is not int or not now < deadline <= now + 1800:
        raise ValueError('Deadline must be within the approved 30-minute envelope')
    return json.dumps(binding, sort_keys=True, separators=(',', ':'))


def terminate_matches(provider, batch, observed):
    # A late allocation must still be found even if its POST response was lost.
    for pod in provider.find(batch, batch):
        observed.add(pod.id)
    for pod_id in sorted(observed):
        if provider.get(pod_id) is not None:
            provider.delete(pod_id)
        if provider.get(pod_id) is not None:
            raise ConnectionError('Pod termination is not confirmed')
    if provider.find(batch, batch):
        raise ConnectionError('A matching Pod remains')
    return bool(observed)


def readiness(provider, scope, batch, deadline, observed):
    # Remember allocations before the deadline, including ones primary cleanup
    # removes early. A refreshed receipt requires a successful provider read.
    for pod in provider.find(batch, batch):
        observed.add(pod.id)
    return {'status': 'READY', 'batch': batch, 'deadline': deadline,
            'scope': scope, 'provider_name': provider._name(batch, batch),
            'checked_at': time.time(), 'run_id': os.environ.get('GITHUB_RUN_ID')}


def watch_previous(provider, observed):
    # This request's deadline has already expired. Only exact-name GET/DELETE;
    # absence without ever observing an ID still does not close its liability.
    confirmed = terminate_matches(provider, OLD_BATCH, observed)
    return 'ABSENCE_CONFIRMED' if confirmed else 'NO_ALLOCATION_OBSERVED'


def save_ready(ready):
    if os.environ.get('WAN_GUARD_READY_FILE'):
        path = Path(os.environ['WAN_GUARD_READY_FILE'])
        temporary = path.with_suffix('.tmp')
        temporary.write_text(json.dumps(ready))
        temporary.replace(path)


def main():
    start = time.time()
    batch = os.environ['WAN_GUARD_BATCH']
    deadline = int(os.environ['WAN_GUARD_DEADLINE'])
    scope = validate(os.environ['WAN_GUARD_SCOPE'], batch, deadline, start)
    provider = CleanupOnlyProvider(os.environ['RUNPOD_CLEANUP_TOKEN'], scope=scope, transport=https_transport())
    observed = set()
    previous = (CleanupOnlyProvider(os.environ['RUNPOD_CLEANUP_TOKEN'], scope=OLD_SCOPE, transport=https_transport())
                if os.environ.get('WAN_TRIAL') in ('validation','fallback','allocation') else None)
    previous_observed = set()
    def current_ready():
        value = readiness(provider, scope, batch, deadline, observed)
        if previous is not None:
            watch_previous(previous, previous_observed)
            value['additional_cleanup_batch'] = OLD_BATCH
        return value
    # Verify credentials/inventory before announcing readiness. No POST occurs.
    ready = current_ready()
    save_ready(ready)
    print(json.dumps(ready), flush=True)
    confirmed = False
    # Keep reconciling for five minutes after the deadline to catch late creates.
    while time.time() < deadline + 300:
        if previous is not None:
            try:
                old_status = watch_previous(previous, previous_observed)
            except Exception:
                old_status = 'CLEANUP_UNRESOLVED'
            print(json.dumps({'checked_at': time.time(), 'status': old_status, 'batch': OLD_BATCH}), flush=True)
        if time.time() >= deadline:
            try:
                confirmed = terminate_matches(provider, batch, observed)
                status = 'ABSENCE_CONFIRMED' if confirmed else 'NO_ALLOCATION_OBSERVED'
            except Exception:
                confirmed, status = False, 'CLEANUP_UNRESOLVED'
            print(json.dumps({'checked_at': time.time(), 'status': status, 'batch': batch}), flush=True)
        else:
            try:
                save_ready(current_ready())
            except Exception:
                # Keep the deadline fallback alive, but do not refresh a receipt
                # when provider access is unavailable.
                print(json.dumps({'status': 'READINESS_UNAVAILABLE', 'batch': batch}), flush=True)
        time.sleep(10)
    if not confirmed:
        raise SystemExit('Cleanup was not proved; reconcile this exact request before any new launch')


if __name__ == '__main__': main()
