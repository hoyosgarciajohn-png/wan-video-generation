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
    # Verify credentials/inventory before announcing readiness. No POST occurs.
    ready = readiness(provider, scope, batch, deadline, observed)
    save_ready(ready)
    print(json.dumps(ready), flush=True)
    confirmed = False
    # Keep reconciling for five minutes after the deadline to catch late creates.
    while time.time() < deadline + 300:
        if time.time() >= deadline:
            try:
                confirmed = terminate_matches(provider, batch, observed)
                status = 'ABSENCE_CONFIRMED' if confirmed else 'NO_ALLOCATION_OBSERVED'
            except Exception:
                confirmed, status = False, 'CLEANUP_UNRESOLVED'
            print(json.dumps({'checked_at': time.time(), 'status': status, 'batch': batch}), flush=True)
        else:
            try:
                save_ready(readiness(provider, scope, batch, deadline, observed))
            except Exception:
                # Keep the deadline fallback alive, but do not refresh a receipt
                # when provider access is unavailable.
                print(json.dumps({'status': 'READINESS_UNAVAILABLE', 'batch': batch}), flush=True)
        time.sleep(10)
    if not confirmed:
        raise SystemExit('Cleanup was not proved; reconcile this exact request before any new launch')


if __name__ == '__main__': main()
