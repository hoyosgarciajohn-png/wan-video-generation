"""Serial queue with durable completion and failure acknowledgement boundaries."""
import json
from pathlib import Path

from .common import atomic_json, require, sync_dir, timestamp, utcnow
from .production import validate_policy
from .resident import ResidentRenderer
from .worker import run_once


def finish_queue(progress_path, result_path, client_binding):
    progress = json.loads(Path(progress_path).read_text())
    require(progress['binding'][0] == client_binding, 'Queue journal credential mismatch')
    policy = validate_policy(progress['binding'][1][4])
    atomic_json(result_path, {'queue_drained': True, 'protocol': policy['protocol'],
        'completed_attempts': progress['completed'], 'attempts': progress['attempts'],
        'status': 'succeeded' if len(progress['completed']) == len(policy['shot_ids']) else 'incomplete'})


def run_queue(claim, client, output_root, result_path, claim_journal, *, input_root, weights,
              renderer_factory=ResidentRenderer, execute=run_once):
    root = Path(output_root)
    policy = validate_policy(claim.get('continuous_queue'))
    binding = (claim['project']['id'], claim['batch']['id'], claim['batch']['deadline_at'],
               claim['batch']['model_profile'], policy)
    progress_path = root / 'queue-progress.json'
    key = [client.binding, binding]
    key = json.loads(json.dumps(key))
    progress = {'binding': key, 'attempts': [], 'completed': []}
    if progress_path.exists():
        progress = json.loads(progress_path.read_text())
        require(progress['binding'] == key, 'Queue journal scope changed')
    with renderer_factory() as resident:
        while claim is not None:
            require((claim['project']['id'], claim['batch']['id'], claim['batch']['deadline_at'],
                claim['batch']['model_profile'], claim.get('continuous_queue')) == binding, 'Queue claim scope changed')
            require(utcnow() < timestamp(binding[2]), 'Queue deadline reached')
            identity = claim['attempt']['id']
            if identity not in progress['attempts']:
                require(len(progress['attempts']) < len(policy['shot_ids'])*policy['max_attempts_per_shot'],
                        'Queue attempt limit reached')
                progress['attempts'].append(identity)
                atomic_json(progress_path, progress)
            try:
                result = execute(claim, client, root, input_root=input_root, weights=weights, resident=resident)
            except Exception:
                failure = root / 'projects' / binding[0] / 'attempts' / identity / 'failure.json'
                # Only an acknowledged terminal render failure can release this
                # assignment. Ambiguous upload/completion must replay identically.
                if not failure.exists() or not json.loads(failure.read_text()).get('acknowledged'):
                    raise
                reason = json.loads(failure.read_text())['code']
                resident.close()
                if reason in ('gpu_out_of_memory','model_load_failed'):
                    # Identical OOM/dependency retries cannot repair the cause.
                    raise
            else:
                atomic_json(root / ('result-' + identity + '.json'), result)
                if identity not in progress['completed']:
                    progress['completed'].append(identity)
                    atomic_json(progress_path, progress)
            claim_journal.unlink(missing_ok=True)
            sync_dir(root)
            claim = client.claim()
            if claim is not None:
                atomic_json(claim_journal, {'binding': client.binding, 'claim': claim})
    finish_queue(progress_path, result_path, client.binding)
