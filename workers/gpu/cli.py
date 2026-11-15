"""One-attempt executable. A controller starts another worker when policy permits."""
import argparse
import copy
import fcntl
from datetime import timedelta
import json
import math
import os
import signal
import sys
import time
from pathlib import Path

from .client import WorkerClient, WorkerAPIError
from .common import ROOT, atomic_json, require, stamp, utcnow, sync_dir
from .worker import run_once


def fixture_claim():
    bundle = json.loads((ROOT / 'fixtures/project.json').read_text())
    batch, attempt = copy.deepcopy(bundle['batches'][0]), copy.deepcopy(bundle['attempts'][0])
    now = utcnow()
    batch.update(state='rendering', approved_at=now.isoformat(),
                 deadline_at=(now + timedelta(minutes=2)).isoformat())
    attempt.update(state='claimed', started_at=now.isoformat(), completed_at=None,
                   lease_expires_at=(now + timedelta(seconds=30)).isoformat())
    return {'contract_version': '0.1.0', 'project': bundle['project'], 'batch': batch,
            'attempt': attempt, 'shot_snapshot': batch['shot_snapshots'][0], 'input_assets': []}


class FixtureClient:
    """Offline fictional backend. The B02 server is the authority in network mode."""
    def __init__(self, claim, root):
        self.claim_data = claim
        self.root = Path(root)
        self.failures = []
        self.heartbeats = 0

    def heartbeat(self, attempt, progress):
        self.heartbeats += 1
        return {'lease_expires_at': (utcnow() + timedelta(seconds=30)).isoformat()}

    def complete(self, attempt, manifest):
        path = self.root / manifest['asset']['object_key']
        receipt = path.with_name('fixture-take.json')
        if receipt.exists():
            old = json.loads(receipt.read_text())
            require(old['manifest'] == manifest, 'Conflicting fixture completion')
            return old['take']
        take = dict(id='take-' + attempt['id'], project_id=attempt['project_id'],
                    attempt_id=attempt['id'], shot_id=attempt['shot_id'],
                    asset_id=manifest['asset']['id'], committed_at=stamp(), **manifest['media'])
        atomic_json(receipt, {'manifest': manifest, 'take': take})
        return take

    def fail(self, attempt, code):
        self.failures.append(code)


def stop_worker(signum, frame):
    raise SystemExit(128 + signum)


def wait_for_claim(client, wait_seconds, poll_seconds):
    require(math.isfinite(wait_seconds) and 0 <= wait_seconds <= 120,
            'Claim wait must be between zero and 120 seconds')
    require(math.isfinite(poll_seconds) and 0.1 <= poll_seconds <= 10,
            'Claim poll interval must be between 0.1 and ten seconds')
    deadline = time.monotonic() + wait_seconds
    while True:
        # Only an authenticated successful empty claim can trigger another poll.
        # Transport/auth errors are ambiguous and propagate without retry.
        claim = client.claim()
        if claim is not None or wait_seconds == 0:
            return claim
        remaining = deadline - time.monotonic()
        if remaining <= 0:
            return None
        time.sleep(min(poll_seconds, remaining))
        if time.monotonic() >= deadline:
            return None


def remote_run(client, output_root, result_path, *, input_root=None, weights=None,
               claim_wait_seconds=0, claim_poll_seconds=2):
    output_root = Path(output_root)
    output_root.mkdir(parents=True, exist_ok=True, mode=0o700)
    claim_journal = output_root / 'worker-claim.json'
    with (output_root / 'worker-session.lock').open('a') as lock:
        fcntl.flock(lock, fcntl.LOCK_EX)
        if claim_journal.exists():
            saved = json.loads(claim_journal.read_text())
            require(saved.get('binding') == client.binding, 'Worker journal credential/origin mismatch')
            claim = saved['claim']
        else:
            claim = wait_for_claim(client, claim_wait_seconds, claim_poll_seconds)
            if claim is None:
                atomic_json(result_path, {'status': 'idle', 'contract_version': '0.1.0'})
                return
            atomic_json(claim_journal, {'binding': client.binding, 'claim': claim})
        result = run_once(claim, client, output_root, input_root=input_root or output_root / 'inputs', weights=weights)
        atomic_json(result_path, result)
        claim_journal.unlink()
        sync_dir(output_root)



def main():
    signal.signal(signal.SIGTERM, stop_worker)
    parser = argparse.ArgumentParser()
    parser.add_argument('mode', choices=['fixture', 'worker'])
    parser.add_argument('--output-root', required=True, type=Path)
    parser.add_argument('--input-root', type=Path)
    parser.add_argument('--weights', type=Path)
    parser.add_argument('--result', required=True, type=Path)
    parser.add_argument('--claim-wait-seconds', type=float, default=0, help='Poll successful empty claims for at most 120 seconds (default: no wait)')
    parser.add_argument('--claim-poll-seconds', type=float, default=2, help='Empty-claim poll interval, 0.1 to 10 seconds')
    parser.add_argument('--allow-local-http', action='store_true', help='Development only: allow HTTP on 127.0.0.1 or localhost')
    args = parser.parse_args()
    if args.mode == 'fixture':
        claim = fixture_claim()
        client = FixtureClient(claim, args.output_root)
    else:
        client = WorkerClient(os.environ['WAN_WORKER_API_URL'], os.environ['WAN_WORKER_TOKEN'], allow_local_http=args.allow_local_http)
        remote_run(client, args.output_root, args.result, input_root=args.input_root, weights=args.weights,
                   claim_wait_seconds=args.claim_wait_seconds, claim_poll_seconds=args.claim_poll_seconds)
        print('PASS: worker operation completed under contract 0.1.0')
        return
    result = run_once(claim, client, args.output_root, input_root=args.input_root, weights=args.weights)
    atomic_json(args.result, result)
    print('PASS: durable output completed under contract 0.1.0')


if __name__ == '__main__':
    try:
        main()
    except Exception as error:
        print(f'Worker operation failed (API status {error.status})' if isinstance(error, WorkerAPIError) else 'Worker operation failed; retained journals require reconciliation', file=sys.stderr)
        raise SystemExit(1) from None

