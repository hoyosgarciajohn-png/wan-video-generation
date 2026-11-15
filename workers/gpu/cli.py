"""One-attempt executable. A controller starts another worker when policy permits."""
import argparse
import copy
from datetime import timedelta
import json
import os
import signal
from pathlib import Path

from .client import WorkerClient
from .common import ROOT, atomic_json, require, stamp, utcnow
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


def main():
    signal.signal(signal.SIGTERM, stop_worker)
    parser = argparse.ArgumentParser()
    parser.add_argument('mode', choices=['fixture', 'worker'])
    parser.add_argument('--output-root', required=True, type=Path)
    parser.add_argument('--input-root', type=Path)
    parser.add_argument('--weights', type=Path)
    parser.add_argument('--result', required=True, type=Path)
    args = parser.parse_args()
    if args.mode == 'fixture':
        claim = fixture_claim()
        client = FixtureClient(claim, args.output_root)
    else:
        client = WorkerClient(os.environ['WAN_WORKER_API_URL'], os.environ['WAN_WORKER_TOKEN'])
        claim = client.claim()
        if claim is None:
            atomic_json(args.result, {'status': 'idle', 'contract_version': '0.1.0'})
            return
    result = run_once(claim, client, args.output_root, input_root=args.input_root, weights=args.weights)
    atomic_json(args.result, result)
    print('PASS: durable output completed under contract 0.1.0')


if __name__ == '__main__':
    main()

