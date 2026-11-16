"""Offline real-run planning only. This module has no provider or admission path."""
from datetime import datetime, timedelta, timezone
import hashlib
import ipaddress
import json
import os
from pathlib import Path
import re
import subprocess
from urllib.parse import urlsplit

from deployment import build_verify
from services.controller.service import canonical
from services.controller.studio import require
from workers.gpu.common import digest, sync_dir, timestamp

ROOT = Path(__file__).resolve().parents[2]
FIELDS = {'project_id','owner_id','batch_id','worker_id','provider','region','gpu_type','gpu_count',
          'image_ref','worker_endpoint','runtime_seconds','reservation_cents','worker_ttl_seconds','storage','pod'}
CRITICAL = ('services/controller/live_execution.py','services/controller/live_billing.py','services/controller/live_admission.py','services/controller/http_api.py','services/controller/preflight.py','services/controller/service.py',
            'services/controller/worker_transport.py','services/controller/orchestration.py',
            'services/controller/budget.py','services/controller/real_jobs.py','services/controller/lifecycle.py','services/controller/runpod.py',
            'deployment/build_verify.py','deployment/container_smoke.py',
            'deployment/hosted_app.py','deployment/cleanup_monitor.py','deployment/deadline_guard.py',
            'deployment/publish_image.py','deployment/hosting/requirements.lock',
            'deployment/hosting/wan-controller.service','deployment/hosting/wan-cleanup.service',
            'deployment/hosting/Caddyfile.example','.github/workflows/deadline-guard.yml')


def _hash(value):
    return hashlib.sha256(canonical(value).encode()).hexdigest()


def _gpu_inventory():
    names = subprocess.check_output(['git','ls-files','-z'], cwd=ROOT, timeout=15).decode().split('\0')
    result = {}
    for name in sorted(n for n in names if n and build_verify.allowed_source(n, 'gpu')):
        path = ROOT / name
        require(path.is_file() and not path.is_symlink(), 'Source inventory requires ordinary tracked files')
        result[name] = digest(path)
    return result


def _sources():
    result = _gpu_inventory()
    for name in CRITICAL:
        path = ROOT / name
        require(path.is_file() and not path.is_symlink(), 'Required planning source is unavailable')
        result[name] = digest(path)
    return dict(sorted(result.items()))


def _json(path):
    path = Path(path)
    require(path.is_file() and not path.is_symlink() and path.stat().st_size <= 8 * 1024 * 1024,
            'Evidence must be a bounded ordinary JSON file')
    return json.loads(path.read_text())


def _origin(value):
    require(isinstance(value, str), 'HTTPS endpoint required')
    url = urlsplit(value)
    require(url.scheme == 'https' and url.hostname and not url.username and not url.password and
            url.path in ('','/') and not url.query and not url.fragment, 'Exact HTTPS origin required')
    hostname = url.hostname.lower()
    require(hostname != 'localhost' and not hostname.endswith(('.localhost','.local')), 'A live host origin is required')
    try:
        address = ipaddress.ip_address(hostname)
    except ValueError:
        return value.rstrip('/')
    require(address.is_global, 'Public worker endpoint required')
    return value.rstrip('/')


def _intent(intent, model):
    require(isinstance(intent, dict) and set(intent) == FIELDS, 'Exact non-secret intent fields required')
    for key in ('project_id','owner_id','batch_id','worker_id','provider','region'):
        require(isinstance(intent[key], str) and len(intent[key]) <= 200 and re.fullmatch(r'[A-Za-z0-9][A-Za-z0-9._-]*', intent[key]),
                'Invalid identity or provider selection')
    require(isinstance(intent['gpu_type'], str) and 0 < len(intent['gpu_type']) <= 100, 'GPU type required')
    require(type(intent['gpu_count']) is int and intent['gpu_count'] == 1, 'Plan supports one GPU')
    require(isinstance(intent['image_ref'], str) and re.fullmatch(r'[A-Za-z0-9][A-Za-z0-9._/:-]*@sha256:[a-f0-9]{64}', intent['image_ref']),
            'Built image must be selected by immutable registry digest')
    endpoint = _origin(intent['worker_endpoint'])
    require(type(intent['runtime_seconds']) is int and 0 < intent['runtime_seconds'] < 3600 and
            type(intent['reservation_cents']) is int and 0 < intent['reservation_cents'] <= 2**53 - 1 and
            type(intent['worker_ttl_seconds']) is int and intent['runtime_seconds'] < intent['worker_ttl_seconds'] <= 3600,
            'Explicit runtime, estimate and bounded credential TTL required')
    storage = intent['storage']
    require(isinstance(storage, dict) and set(storage) == {'kind','namespace','durable_artifact_id','retention_days'} and
            storage['kind'] == 'controller_bridge' and storage['namespace'] == 'projects/' + intent['project_id'] and
            isinstance(storage['durable_artifact_id'], str) and re.fullmatch(r'[A-Za-z0-9][A-Za-z0-9._-]{0,199}', storage['durable_artifact_id']) and
            type(storage['retention_days']) is int and storage['retention_days'] >= 1,
            'Exact external-to-Pod durable output policy required')
    pod = intent['pod']
    require(isinstance(pod, dict) and set(pod) == {'disk_gib','model_mount','output_mount','public_ports','privileged'}, 'Exact pod template constraints required')
    require(type(pod['disk_gib']) is int and pod['disk_gib'] > 0 and
            pod['disk_gib'] * 1024**3 >= sum(item['bytes'] for item in model['files']),
            'Disk allocation cannot hold the locked model bytes')
    require(pod['model_mount'] == '/models' and pod['output_mount'] == '/worker' and
            pod['public_ports'] == [] and pod['privileged'] is False, 'Private non-privileged pod mounts required')
    result = json.loads(canonical(intent))
    result['worker_endpoint'] = endpoint
    return result


def _build(directory, image_ref):
    """Validate consistency of existing verifier evidence; never execute its argv."""
    directory = Path(directory).resolve()
    manifest_path = directory / 'manifest.json'
    manifest = _json(manifest_path)
    require(isinstance(manifest, dict) and isinstance(manifest.get('gates'), dict), 'Invalid build evidence shape')
    require(manifest.get('schema_version') == 1 and manifest.get('target') == 'gpu' and
            manifest.get('mode') == 'LOCAL_EXECUTION' and manifest.get('source_dirty') is False,
            'No completed clean GPU image-verification evidence')
    require(manifest.get('source_sha256') == _gpu_inventory(), 'Build source hashes do not match current GPU context')
    build_verify.verify_context(directory, manifest)
    image_id = manifest.get('image_id')
    require(isinstance(image_id, str) and re.fullmatch(r'sha256:[a-f0-9]{64}', image_id) and
            image_id == manifest.get('built_image_id') and
            (directory / 'built-image-id.txt').read_text().strip() == image_id, 'Built image identity mismatch')
    required = ('image_build','image_identity','runtime_smoke','fixture_smoke')
    commands = manifest.get('executed_commands')
    require(isinstance(commands, list), 'Executed command evidence missing')
    logs = {}
    for gate in required:
        items = [item for item in commands if isinstance(item, dict) and item.get('gate') == gate]
        require(len(items) == 1 and manifest.get('gates', {}).get(gate) == 'PASS', 'Image verification gate lacks one executed record')
        item = items[0]
        require(type(item.get('exit_code')) is int and item['exit_code'] == 0 and item.get('log') == gate + '.log', 'Image verification command failed or log path changed')
        log = directory / item['log']
        require(log.is_file() and not log.is_symlink() and log.stat().st_size <= 32 * 1024 * 1024 and digest(log) == item.get('log_sha256'),
                'Image verification log missing or modified')
        argv = item.get('argv')
        require(isinstance(argv, list) and all(isinstance(a, str) for a in argv), 'Invalid executed command')
        if gate == 'image_build':
            require(argv[:2] == ['docker','build'] and '--platform' in argv and
                    argv[argv.index('--platform') + 1] == 'linux/amd64' and
                    '-f' in argv and argv[argv.index('-f') + 1] == str(directory / 'context/workers/gpu/Dockerfile') and
                    argv[-1] == str(directory / 'context'), 'Executed build did not use the captured GPU context')
        elif gate == 'image_identity':
            require(argv == ['docker','image','inspect', image_id], 'Image inspection must bind the built image ID')
        else:
            require(argv[:2] == ['docker','run'] and image_id in argv and '--network' in argv and
                    argv[argv.index('--network') + 1] == 'none' and '--runtime' in argv and
                    argv[argv.index('--runtime') + 1] == 'runc' and '--read-only' in argv and
                    'NVIDIA_VISIBLE_DEVICES=void' in argv and 'CUDA_VISIBLE_DEVICES=' in argv, 'Smoke command provenance is incomplete')
            if gate == 'runtime_smoke':
                require(argv[-2:] == ['/check.py','gpu'] and
                        f'type=bind,src={directory / "container_smoke.py"},dst=/check.py,readonly' in argv,
                        'Runtime smoke helper is not bound to evidence')
            else:
                require(argv[-7:] == ['-m','workers.gpu.cli','fixture','--output-root','/outputs','--result','/outputs/result.json'],
                        'Fixture smoke command mismatch')
        logs[gate] = item['log_sha256']
    identities = _json(directory / 'image_identity.log')
    require(isinstance(identities, list) and len(identities) == 1 and isinstance(identities[0], dict), 'Invalid image identity record')
    identity = identities[0]
    require(identity.get('Id') == image_id and identity.get('Architecture') == 'amd64' and identity.get('Os') == 'linux' and
            image_ref in (identity.get('RepoDigests') or []) and image_ref in manifest.get('repo_digests', []),
            'Selected registry digest is not in inspected image evidence')
    fixture = build_verify.verify_fixture(directory)
    require(fixture == manifest.get('fixture_evidence'), 'Fixture artifact evidence changed')
    runtime = _json(directory / 'runtime_smoke.log')
    require(isinstance(runtime, dict), 'Invalid runtime evidence')
    model = _json(ROOT / 'workers/gpu/model.lock.json')
    require(runtime.get('source_revision') == model['profile']['code_revision'] and runtime.get('runtime_import') == 'PASS',
            'Runtime import evidence does not match pinned Wan source')
    return dict(manifest_sha256=digest(manifest_path), image_id=image_id, image_ref=image_ref,
                log_sha256=logs, fixture_sha256=fixture['asset_sha256'],
                assurance='local_evidence_consistency_only_not_registry_or_gpu_acceptance')


def evaluate_plan(intent, *, build_evidence=None, approval=None, now=None):
    now = now or datetime.now(timezone.utc)
    require(now.tzinfo is not None, 'Timezone-aware planning time required')
    sources = _sources()
    model = _json(ROOT / 'workers/gpu/model.lock.json')
    gates, evidence = [], {}

    def gate(name, status, action):
        gates.append(dict(id=name, status=status, action=action))

    valid_intent = None
    try:
        valid_intent = _intent(intent, model)
        gate('intent_constraints', 'CONSISTENT', 'Re-review the exact source-bound intent before any execution change.')
    except (ValueError, TypeError, KeyError, IndexError):
        gate('intent_constraints', 'MISSING_OR_INVALID', 'Supply exact project/owner/batch/worker IDs, provider/region/GPU, immutable image, HTTPS endpoint, runtime/estimate/TTL and durable storage/pod constraints; no secrets.')
    binding = dict(intent=valid_intent, source_sha256=sources, model_lock_sha256=sources['workers/gpu/model.lock.json'])
    intent_hash = _hash(binding)
    if build_evidence is not None and valid_intent:
        try:
            evidence['image'] = _build(build_evidence, valid_intent['image_ref'])
            gate('built_image_evidence', 'CONSISTENT', 'Registry pull and real GPU behavior remain unverified; this only checks supplied local build evidence.')
        except (OSError, ValueError, TypeError, KeyError, IndexError):
            gate('built_image_evidence', 'MISSING_OR_INVALID', 'Provide current deployment.build_verify GPU LOCAL_EXECUTION evidence with source/context, command logs, image inspect registry digest and actual fixture output; PASS text alone is insufficient.')
    else:
        gate('built_image_evidence', 'MISSING_OR_INVALID', 'Build and verify the reviewed GPU image on an explicitly selected compatible host; then supply its evidence directory and immutable registry digest.')
    if approval is not None and valid_intent:
        try:
            value = _json(approval)
            require(set(value) == {'schema_version','owner_id','project_id','intent_sha256','currency','approved_cents',
                    'max_runtime_seconds','issued_at','expires_at','reference'}, 'Exact owner attestation required')
            require(type(value['schema_version']) is int and value['schema_version'] == 1 and value['owner_id'] == valid_intent['owner_id'] and
                    value['project_id'] == valid_intent['project_id'] and value['intent_sha256'] == intent_hash and value['currency'] == 'USD',
                    'Attestation scope or intent mismatch')
            require(type(value['approved_cents']) is int and valid_intent['reservation_cents'] <= value['approved_cents'] <= 2**53 - 1 and
                    type(value['max_runtime_seconds']) is int and valid_intent['runtime_seconds'] <= value['max_runtime_seconds'] <= 86400 and
                    timestamp(value['issued_at']) <= now and timestamp(value['expires_at']) >= now + timedelta(seconds=valid_intent['runtime_seconds']) and
                    isinstance(value['reference'], str) and 0 < len(value['reference']) <= 500, 'Attestation is expired or terms insufficient')
            evidence['owner_attestation'] = dict(sha256=digest(approval), approved_cents=value['approved_cents'],
                max_runtime_seconds=value['max_runtime_seconds'], expires_at=value['expires_at'], assurance='content_consistency_not_authenticated_authority')
            gate('owner_attestation', 'CONSISTENT', 'This file is not authenticated spending authority; the live approval verifier is not implemented.')
        except (OSError, ValueError, TypeError, KeyError):
            gate('owner_attestation', 'MISSING_OR_INVALID', 'Provide an unexpired owner/project attestation bound to this intent_sha256 with exact USD cap, runtime and approval reference; simulated budget records are not accepted.')
    else:
        gate('owner_attestation', 'MISSING_OR_INVALID', 'John must choose the specific project, maximum dollar budget and runtime window after reviewing the exact intent; no live approval has been inferred.')
    for name, action in (
        ('live_admission_not_implemented', 'Source now verifies installed signed owner authority and atomically queues live jobs with separate reservations; provision actual operator trust and owner cap/runtime, then install and independently validate the gated live worker/provider coordinator, watchdog and signed billing reconciler. No live transport is installed.'),
        ('real_worker_bridge_not_implemented', 'Canonical real-profile lifecycle/worker/storage wiring exists only behind an explicit synthetic test authority. Implement authenticated live activation with verified build/config evidence; default WorkerTransport still rejects non-fixture batches.'),
        ('host_storage_acceptance_unverified', 'Select and verify a durable controller/storage host, real TLS endpoint, owner-scoped output retention and disaster recovery; an HTTPS string is not deployment evidence.'),
        ('registry_weights_gpu_unverified', 'Verify registry access to the exact digest, every locked model file on the selected volume, CUDA inference and measured cold/warm behavior on the selected GPU.'),
        ('billing_cleanup_acceptance_unverified', 'Implement authoritative provider usage/final-invoice ingestion, stable receipts and independently observed cleanup; budget estimates are not guaranteed dollar hard stops.'),
        ('specific_execution_authorization_missing', 'After code and evidence review, obtain explicit approval for the specific benchmark release and capped resource action; this plan cannot launch it.'),
    ):
        gate(name, 'BLOCKED', action)
    plan = dict(schema_version=1, mode='PLAN_ONLY', execution_authorized=False, ready_for_live_run=False,
                evaluated_at=now.isoformat(), intent_sha256=intent_hash, source_sha256=sources,
                model_profile=model['profile'], model_lock_sha256=sources['workers/gpu/model.lock.json'],
                locked_weight_bytes=sum(item['bytes'] for item in model['files']), intent=valid_intent,
                worker_scope=None if valid_intent is None else dict(project_id=valid_intent['project_id'], batch_id=valid_intent['batch_id'],
                    worker_id=valid_intent['worker_id'], ttl_seconds=valid_intent['worker_ttl_seconds'], credential_issued=False),
                evidence=evidence, gates=gates)
    plan['plan_sha256'] = _hash(plan)
    return plan


def write_plan(plan, path):
    require(isinstance(plan, dict), 'Invalid plan shape')
    require(plan.get('plan_sha256') == _hash({k:v for k,v in plan.items() if k != 'plan_sha256'}), 'Plan integrity mismatch')
    require(plan.get('mode') == 'PLAN_ONLY' and plan.get('execution_authorized') is False and plan.get('ready_for_live_run') is False,
            'Only non-executable plans can be saved')
    path = Path(path)
    fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    with os.fdopen(fd, 'w') as output:
        output.write(canonical(plan) + '\n')
        output.flush()
        os.fsync(output.fileno())
    sync_dir(path.parent)
    return path


def verify_plan(path):
    plan = _json(path)
    require(isinstance(plan, dict), 'Invalid plan shape')
    require(plan.get('plan_sha256') == _hash({k:v for k,v in plan.items() if k != 'plan_sha256'}), 'Plan integrity mismatch')
    require(plan.get('source_sha256') == _sources(), 'Planning source bytes changed; regenerate and review the plan')
    require(plan.get('mode') == 'PLAN_ONLY' and plan.get('execution_authorized') is False and plan.get('ready_for_live_run') is False,
            'Plan cannot authorize execution')
    return plan


def main():
    import argparse
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--intent', type=Path, help='Non-secret intent JSON; omitted means report missing inputs')
    parser.add_argument('--build-evidence', type=Path)
    parser.add_argument('--approval', type=Path, help='Owner attestation JSON; consistency only, never live authority')
    parser.add_argument('--output', required=True, type=Path)
    args = parser.parse_args()
    plan = evaluate_plan(_json(args.intent) if args.intent else {}, build_evidence=args.build_evidence, approval=args.approval)
    write_plan(plan, args.output)
    print('PLAN_ONLY: execution remains disabled; review the saved missing gates.')


if __name__ == '__main__':
    main()
