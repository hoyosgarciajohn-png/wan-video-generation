"""Private operator for separately approved, isolated one-attempt Wan trials.

The web service receives worker traffic but never receives provider credentials or
signing keys. Only the approved fallback scope permits bounded capacity retries. Preparation is free;
admission starts the deadline; launch requires the separate guard's fresh receipt.
"""
import argparse
import base64
from copy import deepcopy
from datetime import timedelta
from decimal import Decimal, ROUND_CEILING
import hashlib
import hmac
import json
import os
from pathlib import Path
import secrets
import shutil
import subprocess
import time
from urllib.parse import quote
from urllib.request import Request

from deployment.hosted_app import open_control
from deployment import validation_policy
from services.controller.allocation_retry import POLICY as CAPACITY_POLICY, ALLOCATION_GPUS
from services.controller.live_admission import LiveAdmission, APPROVAL_DOMAIN, HOST_DOMAIN, configuration_hash
from services.controller.live_billing import BILLING_DOMAIN
from services.controller.live_execution import LiveExecution, BOOTSTRAP_CMD, BOOTSTRAP_ENTRYPOINT, COMPARISON_CMD
from workers.gpu import comparison
from services.controller.preflight import _build, _sources
from services.controller.runpod import https_transport
from services.controller.service import canonical, stamp
from services.controller.studio import StudioWorkspace
from services.controller.worker_transport import WorkerTransport
from workers.gpu.common import LOCK, atomic_json, digest, scoped, timestamp, utcnow

ROOT = Path(__file__).resolve().parents[1]
STATE = Path('/var/lib/wan')
TRIAL = STATE / 'live-trial-20261116'
AUTH = Path('/etc/wan/first-trial-authority.json')
OWNER = 'john-hoyos'
ORIGIN = 'https://wan-64-225-114-46.sslip.io'
IMAGE = 'ghcr.io/hoyosgarciajohn-png/wan-video-generation-gpu@sha256:c1b181cf4fb83f6451c721dc1035d55966a3757bf6567636bcbeff77f740fbe2'
GPU = 'NVIDIA GeForce RTX 4090'
REGISTRY = 'cmwik8xrr008eoog7l16ldqug'
QUOTE_FILE = Path('/etc/wan/connected-runpod-quote.json')
BUILD_EVIDENCE = '2026-11-15-private-publication'
TITLE = 'First Wan GPU trial · one approved five-second shot'
DURATION_MS = 5000
APPROVAL_ID = 'john-first-trial-20261116'
IDEMPOTENCY_KEY = 'john-first-approved-attempt'
WORKER_ID = 'john-first-wan-worker'
EXPECTED_PRIOR_BATCHES = set()
ALLOW_KNOWN_UNKNOWN = False
CAPACITY_RETRY = False
MULTI_GPU = False
COMPARISON = False
RUNTIME_SECONDS = 1800
HOURLY_CEILING = Decimal('1.00')


def select_trial(name):
    """Allowlisted operator scope, never an arbitrary path or mutable retry."""
    global TRIAL, AUTH, IMAGE, BUILD_EVIDENCE, TITLE, DURATION_MS
    global APPROVAL_ID, IDEMPOTENCY_KEY, WORKER_ID, EXPECTED_PRIOR_BATCHES
    global ALLOW_KNOWN_UNKNOWN, CAPACITY_RETRY, HOURLY_CEILING, GPU, MULTI_GPU, COMPARISON, RUNTIME_SECONDS
    COMPARISON = name == 'comparison'
    RUNTIME_SECONDS = 2700 if COMPARISON else 1800
    MULTI_GPU = name == 'allocation'
    CAPACITY_RETRY = name in ('fallback', 'allocation','comparison')
    HOURLY_CEILING = Decimal('4.50') if MULTI_GPU or COMPARISON else Decimal('1.10') if CAPACITY_RETRY else Decimal('1.00')
    GPU = 'NVIDIA GeForce RTX 4090'
    ALLOW_KNOWN_UNKNOWN = name in ('validation','fallback','allocation','comparison')
    if COMPARISON:
        select_repair_trial('validation')
        proposal=read(ROOT/'deployment/duration-comparison-proposal.json')
        assert proposal['status']=='OWNER_APPROVED_RUNTIME_PREPARATION' and proposal['approval']['new_spending_envelope']=='APPROVED'
        terms=proposal['proposed_terms']
        assert (terms['overall_additional_cap_cents'],terms['pod_reservation_cents'],terms['storage_allowance_cents'],
                terms['runtime_seconds_from_admission'],terms['max_allocation_requests'],terms['max_render_attempts'],
                terms['max_hourly_cents'],terms['gpu_type'])==(500,400,100,2700,3,2,450,comparison.GPU)
        TRIAL=STATE/'comparison-trial-20261116'
        AUTH=Path('/etc/wan/comparison-trial-authority-20261116.json')
        TITLE='Wan duration comparison · five and fifteen seconds'
        GPU=comparison.GPU
        DURATION_MS=5000
        IMAGE=proposal['image']
        assert isinstance(IMAGE,str) and '@sha256:' in IMAGE, 'Reviewed comparison image is not yet published'
        BUILD_EVIDENCE='2026-11-16-duration-comparison-build'
        APPROVAL_ID='john-duration-comparison-20261116'
        IDEMPOTENCY_KEY='john-duration-comparison-pair'
        WORKER_ID='john-duration-comparison-worker'
        EXPECTED_PRIOR_BATCHES.update({'bee9e55b1d4a4f458771ad4ac69c3318','4e87af47cce0477b8750b2e4681b722d','0a30c22ff1a8493bbe2714ad36cd0321'})
        return
    if name == 'first':
        return
    if name == 'repair':
        return select_repair_trial()
    if name in ('validation','fallback','allocation'):
        select_repair_trial('validation')
        if CAPACITY_RETRY:
            proposal = read(ROOT / f'deployment/{name}-trial-proposal.json')
            assert proposal['status'] == 'OWNER_APPROVED_RUNTIME_PREPARATION' and proposal['execution_enabled'] is False
            terms = proposal['proposed_additional_terms']
            assert (terms['overall_cap_cents'],terms['pod_reservation_cents'],terms['storage_allowance_cents'],
                    terms['runtime_seconds_from_admission'],terms['pod_create_attempts'],terms['render_attempts'],
                    terms['gpu_quote_ceiling_cents_per_hour']) == (500,400,100,1800,3,1,450 if MULTI_GPU else 110)
            assert terms['gpus'] == (list(ALLOCATION_GPUS) if MULTI_GPU else ['NVIDIA GeForce RTX 4090','NVIDIA L40S'])
            assert proposal['capacity_retry'] == CAPACITY_POLICY and proposal['image'] == IMAGE
            TRIAL = STATE / 'fallback-trial-20261116'
            AUTH = Path('/etc/wan/fallback-trial-authority-20261116.json')
            TITLE = 'Wan approved GPU fallback validation · one second'
            APPROVAL_ID = 'john-capacity-fallback-20261116'
            IDEMPOTENCY_KEY = 'john-capacity-fallback-bounded-attempt'
            WORKER_ID = 'john-capacity-fallback-worker'
            EXPECTED_PRIOR_BATCHES.add('bee9e55b1d4a4f458771ad4ac69c3318')
            if MULTI_GPU:
                TRIAL = STATE / 'allocation-trial-20261116'
                AUTH = Path('/etc/wan/allocation-trial-authority-20261116.json')
                TITLE = 'Wan multi-GPU allocation validation · one second'
                APPROVAL_ID = 'john-multi-gpu-allocation-20261116'
                IDEMPOTENCY_KEY = 'john-multi-gpu-allocation-bounded-attempt'
                WORKER_ID = 'john-multi-gpu-allocation-worker'
                EXPECTED_PRIOR_BATCHES.add('4e87af47cce0477b8750b2e4681b722d')
            if (TRIAL / 'prepared.json').exists():
                GPU = read(TRIAL / 'prepared.json')['pricing']['gpu']
                assert GPU in terms['gpus']
        return
    assert name == 'diagnostic', 'Unknown trial scope'
    proposal = read(ROOT / 'deployment/diagnostic-trial-proposal.json')
    assert proposal['status'] == 'OWNER_APPROVED_RUNTIME_PREPARATION'
    assert proposal['execution_enabled'] is False  # Not a grant by itself.
    terms = proposal['proposed_additional_terms']
    assert (terms['overall_cap_cents'],terms['pod_reservation_cents'],terms['storage_allowance_cents'],
            terms['runtime_seconds_from_admission'],terms['pod_create_attempts'],terms['render_attempts'],
            terms['target_duration_ms'],terms['frames']) == (500,400,100,1800,1,1,1000,25)
    assert proposal['approval_reference']
    TRIAL = STATE / 'diagnostic-trial-20261116'
    AUTH = Path('/etc/wan/diagnostic-trial-authority-20261116.json')
    IMAGE = 'ghcr.io/hoyosgarciajohn-png/wan-video-generation-gpu@sha256:f724b9f32ac4ac780702072fd32e9d08254524ca81afd6aadeb87169904f993b'
    assert proposal['image'] == IMAGE
    BUILD_EVIDENCE = '2026-11-16-private-rebuild'
    TITLE = 'Wan diagnostic trial · one approved one-second shot'
    DURATION_MS = 1000
    APPROVAL_ID = 'john-diagnostic-trial-20261116'
    IDEMPOTENCY_KEY = 'john-diagnostic-approved-attempt'
    WORKER_ID = 'john-diagnostic-wan-worker'
    EXPECTED_PRIOR_BATCHES = {'7c811e6ab21a4392b0e3a80e331fc57a'}


def select_repair_trial(scope='repair'):
    global TRIAL, AUTH, IMAGE, BUILD_EVIDENCE, TITLE, DURATION_MS
    global APPROVAL_ID, IDEMPOTENCY_KEY, WORKER_ID, EXPECTED_PRIOR_BATCHES
    proposal = read(ROOT / f'deployment/{scope}-trial-proposal.json')
    assert proposal['status'] == 'OWNER_APPROVED_RUNTIME_PREPARATION'
    assert proposal['execution_enabled'] is False
    terms = proposal['proposed_additional_terms']
    assert (terms['overall_cap_cents'],terms['pod_reservation_cents'],terms['storage_allowance_cents'],
            terms['runtime_seconds_from_admission'],terms['pod_create_attempts'],terms['render_attempts'],
            terms['target_duration_ms'],terms['frames']) == (500,400,100,1800,1,1,1000,25)
    assert proposal['approval_reference']
    TRIAL = STATE / 'repair-trial-20261116'
    AUTH = Path('/etc/wan/repair-trial-authority-20261116.json')
    IMAGE = 'ghcr.io/hoyosgarciajohn-png/wan-video-generation-gpu@sha256:fce20324d1ae2f65f163f5550c7719d814f775468ce83475d4705f3f3bebed50'
    assert proposal['image'] == IMAGE
    BUILD_EVIDENCE = '2026-11-16-memory-repair-build'
    TITLE = 'Wan repaired worker validation · one one-second shot'
    DURATION_MS = 1000
    APPROVAL_ID = 'john-repair-validation-20261116'
    IDEMPOTENCY_KEY = 'john-repair-validation-single-attempt'
    WORKER_ID = 'john-repair-validation-worker'
    EXPECTED_PRIOR_BATCHES = {'7c811e6ab21a4392b0e3a80e331fc57a','def5478dc85949139ca1c0ae404f9d1f'}
    if scope == 'validation':
        TRIAL = STATE / 'validation-trial-20261116'
        AUTH = Path('/etc/wan/validation-trial-authority-20261116.json')
        TITLE = 'Wan isolated progressive validation · one second'
        APPROVAL_ID = 'john-progressive-validation-20261116'
        IDEMPOTENCY_KEY = 'john-progressive-validation-single-attempt'
        WORKER_ID = 'john-progressive-validation-worker'
        EXPECTED_PRIOR_BATCHES.add('249c50635ec84ac38cef0eb66232efed')


def prior_history_closed(db):
    rows = db.execute('SELECT l.batch,p.state,p.cleanup FROM live_job_links AS l '
                      'LEFT JOIN pod_batches AS p ON p.id=l.batch').fetchall()
    assert {row[0] for row in rows} == EXPECTED_PRIOR_BATCHES
    assert all(row[1] in ('succeeded','failed','canceled') and
               (row[2] == 'confirmed' or (ALLOW_KNOWN_UNKNOWN and row[0] == validation_policy.OLD_BATCH)) for row in rows)
    validation_policy.quiescent(db, allow_unknown=ALLOW_KNOWN_UNKNOWN)


def read(path):
    return json.loads(Path(path).read_text())


def control():
    return open_control({'WAN_STATE': str(STATE)})


def sign(payload, key, domain):
    return dict(key_id=key, payload=deepcopy(payload), signature=hmac.new(
        bytes.fromhex(read(AUTH)[key]), (domain + '\n' + canonical(payload)).encode(), hashlib.sha256).hexdigest())


def services():
    keys = read(AUTH)
    c = control()
    a = LiveAdmission(StudioWorkspace(c), approval_keys={'owner': (OWNER, bytes.fromhex(keys['owner']))},
        host_keys={'host': (OWNER, bytes.fromhex(keys['host']))}, build_evidence=TRIAL / 'build')
    e = LiveExecution(a, runpod_token=Path('/etc/wan/runpod-token').read_text().strip(),
        transport=https_transport(), billing_keys={'billing': (OWNER, bytes.fromhex(keys['billing']))},
        candidate_check=candidate_available if MULTI_GPU else comparison_available if COMPARISON else None)
    return c, a, e


def provider_get(path):
    token = Path('/etc/wan/runpod-token').read_text().strip()
    req = Request('https://api.runpod.io/v2' + path, headers={'Authorization': 'Bearer ' + token})
    with https_transport()(req, timeout=20) as response:
        if response.status != 200:
            raise ValueError('Provider read failed')
        data = response.read(8 * 1024 * 1024 + 1)
        if len(data) > 8 * 1024 * 1024:
            raise ValueError('Provider response too large')
        return json.loads(data)


def catalog_snapshot():
    envelope = read(QUOTE_FILE)
    assert set(envelope) == {'observed_at', 'data'}
    assert type(envelope['observed_at']) in (int, float) and 0 <= time.time() - envelope['observed_at'] < 180
    return envelope['data']


def candidate_available(candidate, ceiling):
    snapshot = catalog_snapshot()
    assert isinstance(snapshot, dict) and isinstance(snapshot.get('gpus'), list)
    value = next((x for x in snapshot['gpus'] if x['id'] == candidate['gpu_type']), None)
    if value is None or not value.get('secure') or value.get('availability') not in ('HIGH', 'MEDIUM', 'LOW'):
        return False
    price = Decimal(str(value['price']['secure']))
    if not price.is_finite() or not 0 < price * 100 <= ceiling:
        return False
    available = {x['id'] for x in value.get('dataCenters', []) if x.get('availability') in ('HIGH','MEDIUM','LOW')}
    return bool(available.intersection(candidate['data_center_ids']))


def comparison_available(candidate, ceiling):
    assert COMPARISON and ceiling==450 and candidate['gpu_type']==GPU
    checked_quote(candidate['data_center_ids'])
    return True


def allocation_quote(plan=None):
    global GPU
    snapshot = catalog_snapshot()
    assert isinstance(snapshot, dict) and isinstance(snapshot.get('gpus'), list)
    ranked = []
    for value in snapshot['gpus']:
        if value['id'] not in ALLOCATION_GPUS:
            continue
        locations = [x['id'] for x in value.get('dataCenters', []) if x.get('availability') in ('HIGH','MEDIUM','LOW')][:8]
        candidate = dict(gpu_type=value['id'], data_center_ids=locations)
        if not locations or not candidate_available(candidate, 450):
            continue
        price = Decimal(str(value['price']['secure']))
        ranked.append(({'HIGH':0,'MEDIUM':1,'LOW':2}[value['availability']], -len(locations), price, candidate))
    ranked.sort(key=lambda x: x[:3])
    if plan is None:
        candidates = [x[3] for x in ranked]
        assert candidates, 'No eligible approved GPU candidate'
        plan = dict(max_hourly_cents=450, candidates=candidates)
    else:
        assert any(candidate_available(x, plan['max_hourly_cents']) for x in plan['candidates']), 'No admitted candidate currently available'
    first = plan['candidates'][0]
    GPU = first['gpu_type']
    return dict(checked_at=time.time(), gpu=GPU, region=first['data_center_ids'][0],
                data_center_ids=first['data_center_ids'], max_hourly_cents=450,
                allocation_plan=deepcopy(plan), min_cuda='12.8')


def checked_quote(region=None):
    # Supplied by the authorized connected Runpod read, via pinned operator SSH.
    # The existing cleanup credential deliberately has no catalog/billing access.
    global GPU
    if MULTI_GPU:
        return allocation_quote(region)
    value = catalog_snapshot()
    if CAPACITY_RETRY and not COMPARISON and region is None:
        assert value['id'] in ('NVIDIA GeForce RTX 4090','NVIDIA L40S')
        GPU = value['id']
    price = Decimal(str(value['price']['secure']))
    assert value['id'] == GPU and value['secure'] and 0 < price <= HOURLY_CEILING
    available = [x['id'] for x in value.get('dataCenters', []) if x.get('availability') in ('HIGH', 'MEDIUM', 'LOW')]
    if region is None:
        # The approval bounds GPU, cloud, price and runtime, not geography.
        # Prefer previous locations, then bind any currently quoted location.
        preferred = ('EU-RO-1', 'US-IL-1', 'EUR-IS-1', 'EUR-IS-2')
        regions = list(dict.fromkeys([x for x in preferred if x in available] + available))[:8]
    else:
        # Recheck the signed list without expanding, reordering or migrating it.
        regions = [region] if isinstance(region, str) else list(region)
    assert 1 <= len(regions) <= 8 and len(set(regions)) == len(regions)
    assert all(isinstance(x, str) and x for x in regions)
    assert any(x in available for x in regions), 'Approved GPU regions have no current capacity'
    return {'checked_at': time.time(), 'gpu': GPU, 'region': regions[0], 'data_center_ids': regions,
            'usd_per_hour': str(price), 'min_cuda': '12.8'}


def materialize_build(destination):
    source = ROOT / 'deployment/evidence' / BUILD_EVIDENCE
    destination.mkdir(mode=0o700)
    for file in source.iterdir():
        if file.is_file():
            shutil.copy2(file, destination / file.name)
    manifest = read(destination / 'manifest.json')
    for name, checksum in manifest['source_sha256'].items():
        original = scoped(ROOT, name)
        assert digest(original) == checksum
        target = scoped(destination / 'context', name)
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(original, target)
    shutil.copy2(ROOT / 'deployment/container_smoke.py', destination / 'container_smoke.py')
    result = read(destination / 'fixture-result.json')
    fixture = destination / 'fixture'
    target = scoped(fixture, result['asset']['object_key'])
    target.parent.mkdir(parents=True)
    target.write_bytes(base64.b64decode((source / 'fixture.mp4.base64').read_text(), validate=False))
    shutil.copy2(source / 'fixture-result.json', fixture / 'result.json')
    return _build(destination, IMAGE)


def primary_ready():
    status = read(STATE / 'cleanup-status.json')
    c = control()
    with c.transaction() as db:
        validation_policy.monitor_ready(db, status, allow_unknown=ALLOW_KNOWN_UNKNOWN)
    if ALLOW_KNOWN_UNKNOWN:
        validation_policy.verify_absent(Path('/etc/wan/runpod-token').read_text().strip(), transport=https_transport())
    for unit in ('wan-controller', 'wan-cleanup', 'wan-proxy'):
        subprocess.run(['systemctl','is-active','--quiet',unit], check=True)


def prepare():
    primary_ready()
    previous = read(STATE / 'acceptance-20261116/result.json')
    assert previous['http_workflow'] == previous['restart_persistence'] == previous['cleanup_during_controller_stop'] == 'PASS'
    assert previous['same_host_restore']['media_decoded']
    off_host = read(ROOT / 'deployment/evidence/2026-11-16-access-recovery/off-host-result.json')
    assert off_host == previous['same_host_restore']
    # No new live project or keys can silently replace an earlier trial.
    assert not TRIAL.exists() and not AUTH.exists()
    c = control()
    with c.transaction() as db:
        prior_history_closed(db)
    pricing = checked_quote()
    TRIAL.mkdir(mode=0o700)
    build = materialize_build(TRIAL / 'build')
    atomic_json(AUTH, {key: secrets.token_hex(32) for key in ('owner','host','billing')})
    studio = StudioWorkspace(c)
    workspace = studio.get(OWNER)
    title = TITLE
    assert not any(x['bundle']['project']['title'] == title for x in workspace['projects'])
    workspace = studio.create(OWNER, title, 'music_video', workspace['revision'])
    p = next(x for x in workspace['projects'] if x['bundle']['project']['title'] == title)
    project = p['bundle']['project']['id']
    shot = deepcopy(read(ROOT / 'fixtures/project.json')['shots'][0])
    shot.update(project_id=project, scene_id=p['scenes'][0]['id'], target_duration_ms=DURATION_MS,
                prompt='A small blue sailboat moves slowly across a calm lake at sunrise, steady wide camera, no text.')
    shot['settings'].update(width=1280, height=704, steps=50, seed=42)
    p['bundle']['shots'] = [shot]
    if COMPARISON:
        shot.update(id='duration-05',prompt=comparison.PROMPT,target_duration_ms=5000)
        second=deepcopy(shot)
        second.update(id='duration-15',target_duration_ms=15000)
        p['bundle']['shots'].append(second)
    workspace = studio.save(OWNER, workspace, workspace['revision'])
    profile = dict(model_profile=deepcopy(LOCK['profile']), image_ref=IMAGE, gpu_type=GPU, gpu_count=1,
        region=pricing['region'], worker_endpoint=ORIGIN, storage_id='wan-controller-01-artifacts')
    launch = dict(image=IMAGE, gpu={'id': GPU, 'count': 1, 'minCudaVersion': '12.8', 'minRamPerGpu': 64}, cloud='SECURE',
        disk=80, dataCenterIds=pricing['data_center_ids'], mounts={}, ports=[], env={}, registry=REGISTRY,
        entrypoint=BOOTSTRAP_ENTRYPOINT, cmd=COMPARISON_CMD if COMPARISON else BOOTSTRAP_CMD)
    expires = stamp(utcnow() + timedelta(hours=6))
    grant = dict(id=APPROVAL_ID, owner=OWNER, project=project, currency='USD', approved_cents=400,
        max_runtime_seconds=RUNTIME_SECONDS, valid_until=expires, profile=profile, launch_profile=launch, source_sha256=_sources())
    if CAPACITY_RETRY:
        grant['capacity_retry'] = dict(CAPACITY_POLICY)
    if MULTI_GPU:
        grant['allocation_plan'] = pricing['allocation_plan']
    if COMPARISON:
        grant['duration_comparison']=comparison.policy(['duration-05','duration-15'],IMAGE)
    host = dict(owner=OWNER, project=project, config_hash=configuration_hash(profile, launch, grant.get('allocation_plan'), grant.get('duration_comparison')), source_sha256=grant['source_sha256'],
        build_manifest_sha256=build['manifest_sha256'], valid_until=expires, worker_endpoint=ORIGIN, storage_id=profile['storage_id'])
    atomic_json(TRIAL / 'approval.json', sign(grant, 'owner', APPROVAL_DOMAIN))
    atomic_json(TRIAL / 'host.json', sign(host, 'host', HOST_DOMAIN))
    atomic_json(TRIAL / 'prepared.json', dict(owner=OWNER, project=project, shot=shot['id'], pricing=pricing,
        source_commit=subprocess.check_output(['git','rev-parse','HEAD'], text=True).strip(), build=build,
        overall_cap_cents=500, pod_cap_cents=400, storage_allowance_cents=100, runtime_seconds=RUNTIME_SECONDS, max_attempts=2 if COMPARISON else 1, max_create_requests=3 if CAPACITY_RETRY else 1))
    # Only install a receiver in the web process; provider access stays private.
    env = Path('/etc/wan/controller.env')
    current = env.read_text()
    if 'WAN_WORKER_EXECUTION' not in current:
        with env.open('a') as out:
            out.write('\nWAN_WORKER_EXECUTION=1\n')
        subprocess.run(['systemctl','restart','wan-controller'], check=True)
    else:
        assert [line for line in current.splitlines() if line.startswith('WAN_WORKER_EXECUTION=')] == ['WAN_WORKER_EXECUTION=1']
    print(json.dumps({'status':'PREPARED_NO_ADMISSION_NO_GPU', 'project':project, 'quote':pricing, 'build':build['manifest_sha256']}))


def refresh_unregistered_validation(c, saved):
    """Select current locations before registering authority, never after admission."""
    assert ALLOW_KNOWN_UNKNOWN and not (TRIAL / 'job.json').exists()
    with c.transaction() as db:
        prior_history_closed(db)
        # A registered approval is already immutable, even if submit failed.
        if db.execute('SELECT 1 FROM live_approvals WHERE id=?', (APPROVAL_ID,)).fetchone():
            return saved
        assert db.execute('SELECT count(*) FROM live_job_links WHERE project=?', (saved['project'],)).fetchone()[0] == 0
    current = checked_quote()
    regions = current['data_center_ids'] if MULTI_GPU else list(dict.fromkeys(current['data_center_ids'] + saved['pricing']['data_center_ids']))[:8]
    current.update(region=regions[0], data_center_ids=regions)
    approval = read(TRIAL / 'approval.json')
    host = read(TRIAL / 'host.json')
    grant = deepcopy(approval['payload'])
    assert grant['id'] == APPROVAL_ID and grant['owner'] == OWNER and grant['project'] == saved['project']
    assert (grant['approved_cents'], grant['max_runtime_seconds']) == (400, RUNTIME_SECONDS)
    # Retain the prior signed preparation as evidence. It never reached the DB.
    history = TRIAL / 'pre-admission-history'
    history.mkdir(mode=0o700, exist_ok=True)
    identity = hashlib.sha256(canonical(approval).encode()).hexdigest()
    archive = history / (identity + '.json')
    if not archive.exists():
        atomic_json(archive, dict(approval=approval, host=host, prepared=saved))
    grant['profile']['region'] = regions[0]
    if CAPACITY_RETRY:
        grant['profile']['gpu_type'] = current['gpu']
        grant['launch_profile']['gpu']['id'] = current['gpu']
    grant['launch_profile']['dataCenterIds'] = regions
    if MULTI_GPU:
        grant['allocation_plan'] = current['allocation_plan']
    grant['source_sha256'] = _sources()
    grant['valid_until'] = stamp(utcnow() + timedelta(hours=6))
    attestation = deepcopy(host['payload'])
    attestation.update(config_hash=configuration_hash(grant['profile'], grant['launch_profile'], grant.get('allocation_plan'), grant.get('duration_comparison')),
                       source_sha256=grant['source_sha256'], valid_until=grant['valid_until'])
    saved = dict(saved, pricing=current, source_commit=subprocess.check_output(['git','rev-parse','HEAD'], text=True).strip())
    atomic_json(TRIAL / 'approval.json', sign(grant, 'owner', APPROVAL_DOMAIN))
    atomic_json(TRIAL / 'host.json', sign(attestation, 'host', HOST_DOMAIN))
    atomic_json(TRIAL / 'prepared.json', saved)
    print(json.dumps({'status':'UNREGISTERED_PREPARATION_REFRESHED', 'project':saved['project'], 'data_center_ids':regions}), flush=True)
    return saved


def admit():
    primary_ready()
    assert not (TRIAL / 'job.json').exists()
    saved = read(TRIAL / 'prepared.json')
    c, a, e = services()
    with c.transaction() as db:
        prior_history_closed(db)
    if ALLOW_KNOWN_UNKNOWN:
        saved = refresh_unregistered_validation(c, saved)
    pricing = checked_quote(saved['pricing']['allocation_plan'] if MULTI_GPU else saved['pricing'].get('data_center_ids', [saved['pricing']['region']]))
    a.approve(OWNER, saved['project'], read(TRIAL / 'approval.json'))
    with c.transaction() as db:
        a.verify_execution_evidence(db, OWNER, saved['project'], read(TRIAL / 'approval.json')['payload']['id'], read(TRIAL / 'host.json'))
    request = dict(approval_id=APPROVAL_ID, shot_ids=['duration-05','duration-15'] if COMPARISON else [saved['shot']], expected_revision=a.studio.get(OWNER)['revision'],
        reservation_cents=400, runtime_seconds=RUNTIME_SECONDS, idempotency_key=IDEMPOTENCY_KEY)
    result = a.submit(OWNER, saved['project'], request)
    batch = result['batch']['id']
    atomic_json(TRIAL / 'job.json', dict(project=saved['project'], batch=batch,
        deadline=int(timestamp(result['batch']['deadline_at']).timestamp()), scope=canonical([OWNER,saved['project']]), pricing=pricing))
    worker = WorkerTransport(c, real_jobs=e).issue(OWNER, saved['project'], batch, WORKER_ID, ttl_seconds=RUNTIME_SECONDS+300)
    atomic_json(TRIAL / 'worker.json', worker)
    print(json.dumps({'status':'ADMITTED_NOT_LAUNCHED', **read(TRIAL / 'job.json')}))


def guard_ready(job):
    ready = read(TRIAL / 'guard-ready.json')
    assert ready['status'] == 'READY' and ready['batch'] == job['batch'] and ready['deadline'] == job['deadline']
    assert ready['scope'] == job['scope'] and 0 <= time.time() - ready['checked_at'] < 180
    assert isinstance(ready['run_id'], str) and ready['run_id'].isdigit()
    assert job['deadline'] - time.time() > 120
    expected = 'wan-' + hashlib.sha256(json.dumps([job['scope'],job['batch'],job['batch']]).encode()).hexdigest()
    assert ready['provider_name'] == expected
    if ALLOW_KNOWN_UNKNOWN:
        assert ready.get('additional_cleanup_batch') == validation_policy.OLD_BATCH
    return ready


def bill_snapshot(c, e, job, pod):
    try:
        envelope = read(TRIAL / 'connected-billing.json')
        assert set(envelope) == {'observed_at', 'data'}
        assert type(envelope['observed_at']) in (int, float) and 0 <= time.time() - envelope['observed_at'] < 3600
        raw = envelope['data']
        assert raw['metadata']['query']['podId'] == pod
        assert raw['metadata']['recordCount'] == len(raw['records'])
        assert all(x['podId'] == pod for x in raw['records'])
        total = Decimal(str(raw['metadata']['totals']['totalAmount']))
        assert total.is_finite() and total >= 0
        amount = int((total * 100).to_integral_value(rounding=ROUND_CEILING))
        with c.transaction() as db:
            prior = db.execute('SELECT COALESCE(SUM(amount_cents),0) FROM live_billing_events WHERE batch=?', (job['batch'],)).fetchone()[0]
        if amount > prior:
            payload = dict(id=f"runpod-{job['batch']}-{amount}", owner=OWNER, project=job['project'], batch=job['batch'], kind='charge',
                amount_cents=amount-prior, bill_reference=f"Runpod v2 billing/pods cumulative {amount} cents", valid_until=stamp(utcnow()+timedelta(hours=1)), provider_resource_id=pod, currency='USD')
            e.ingest_bill(OWNER, job['project'], sign(payload, 'billing', BILLING_DOMAIN))
        atomic_json(TRIAL / 'provider-billing.json', {'observed_at':time.time(), 'cumulative_cents':amount, 'raw':raw, 'final':False})
        return {'status':'RETRIEVED_NOT_FINAL', 'observed_cents':amount}
    except Exception:
        return {'status':'AWAITING_CONNECTED_BILLING_RECORD', 'reservation_retained':True}


def observe():
    c, a, e = services()
    job = read(TRIAL / 'job.json')
    result = e.status(OWNER, job['project'], job['batch'])
    if result['batch']['state'] == 'provisioning':
        # Already attempted: Lifecycle performs GET reconciliation only here.
        result = e.provision(OWNER, job['project'], job['batch'])
    batch = result['batch']
    pod = batch['provider_resource_id']
    provider = {}
    if pod and batch['cleanup_state'] != 'confirmed':
        try:
            detail = provider_get('/pods/' + quote(pod, safe=''))
            assert detail['name'] == 'wan-' + hashlib.sha256(json.dumps([job['scope'],job['batch'],job['batch']]).encode()).hexdigest()
            hourly = Decimal(str(detail['cost']))
            provider = {k:detail.get(k) for k in ('id','status','cost','cudaVersion','dataCenterId','startedAt')}
            if not hourly.is_finite() or hourly > HOURLY_CEILING:
                e.cancel(OWNER, job['project'], job['batch'])
                provider['canceled_above_price_ceiling'] = True
        except Exception:
            provider = {'status':'OBSERVATION_UNAVAILABLE'}
    billing = bill_snapshot(c, e, job, pod) if pod else {'status':'NO_POD_ID'}
    unresolved = e.watchdog()
    result = e.status(OWNER, job['project'], job['batch'])
    bundle = c.bundle(OWNER, job['project'])
    with c.transaction() as db:
        raw_diagnostic = db.execute('SELECT create_diagnostic FROM pod_batches WHERE id=?', (job['batch'],)).fetchone()[0]
        allocation_row = db.execute('SELECT allocation_attempts FROM live_execution_bindings WHERE batch=?',(job['batch'],)).fetchone()
        allocation_history = json.loads(allocation_row[0]) if allocation_row else []
        metrics=[json.loads(x[0]) for x in db.execute('SELECT payload FROM worker_telemetry WHERE batch=?',(job['batch'],))]
        gate=db.execute('SELECT decision FROM comparison_gates WHERE batch=?',(job['batch'],)).fetchone()
    summary = dict(checked_at=time.time(), pricing=job['pricing'], batch=result['batch'], budget=result['budget'], reservation_state=result['reservation_state'],
        provider=provider, billing=billing, unresolved=unresolved, takes=bundle['takes'], attempts=bundle['attempts'],
        provider_create=json.loads(raw_diagnostic) if raw_diagnostic else None, allocation_attempts=allocation_history, telemetry=metrics, comparison_gate=json.loads(gate[0]) if gate else None)
    if summary['batch']['cleanup_state'] == 'confirmed':
        previous = read(TRIAL / 'status.json') if (TRIAL / 'status.json').exists() else {}
        summary['cleanup_confirmed_observed_at'] = previous.get('cleanup_confirmed_observed_at', summary['checked_at'])
    atomic_json(TRIAL / 'status.json', summary)
    # Keep complete evidence on disk, but put lifecycle fields first in a short
    # live log line so the Actions viewer does not truncate the useful status.
    print(json.dumps(operator_summary(summary)), flush=True)
    return summary


def operator_summary(summary):
    batch = summary['batch']
    return dict(checked_at=summary['checked_at'], batch=batch['id'], state=batch['state'],
        cleanup=batch['cleanup_state'], pod=batch['provider_resource_id'], deadline=batch['deadline_at'],
        takes=len(summary['takes']), attempts=len(summary['attempts']),
        failure_codes=[a['failure_reason'] for a in summary['attempts'] if a.get('failure_reason')],
        billing=summary['billing'], reservation_state=summary['reservation_state'],
        provider_create=summary.get('provider_create'), allocation_requests=len(summary.get('allocation_attempts',[])), telemetry=summary.get('telemetry',[]), comparison_gate=summary.get('comparison_gate'))


def launch():
    primary_ready()
    job = read(TRIAL / 'job.json')
    ready = guard_ready(job)
    # The CI caller supplies a live GitHub API observation before this SSH call.
    assert os.environ.get('WAN_VERIFIED_GUARD_RUN') == ready['run_id']
    checked_quote(job['pricing']['allocation_plan'] if MULTI_GPU else job['pricing'].get('data_center_ids', [job['pricing']['region']]))
    c, a, e = services()
    with c.transaction() as db:
        assert db.execute("SELECT dispatch_state FROM live_job_links WHERE batch=?",(job['batch'],)).fetchone()[0] == 'disabled'
    print(json.dumps({'status':'BOUNDED_CAPACITY_LAUNCH_STARTING' if CAPACITY_RETRY else 'ONE_CREATE_ATTEMPT_STARTING','batch':job['batch'],'deadline':job['deadline']}), flush=True)
    e.provision(OWNER, job['project'], job['batch'], read(TRIAL / 'host.json'), worker_token=read(TRIAL / 'worker.json')['token'])
    while time.time() < job['deadline'] + 60:
        status = observe()
        if status['batch']['cleanup_state'] == 'confirmed':
            break
        time.sleep(15)
    final = observe()
    if final['batch']['cleanup_state'] != 'confirmed':
        raise SystemExit('Cleanup remains unresolved; separate guard remains responsible')


def export():
    assert COMPARISON
    summary=observe()
    assert summary['batch']['cleanup_state']=='confirmed' and summary['batch']['state'] in ('succeeded','failed','canceled')
    destination=TRIAL/'comparison-output'
    destination.mkdir(mode=0o700,exist_ok=True)
    bundle=control().bundle(OWNER,summary['batch']['project_id'])
    for take in summary['takes']:
        metrics=next(m for m in summary['telemetry'] if m['attempt_id']==take['attempt_id'])
        asset=next(a for a in bundle['assets'] if a['id']==take['asset_id'])
        source=scoped(control().asset_root,asset['object_key'])
        assert digest(source)==asset['sha256']==metrics['asset_sha256'] and source.stat().st_size==asset['bytes']==metrics['asset_bytes']
        target=destination/f"wan-{metrics['target_duration_ms']//1000:02d}s-original.mp4"
        if target.exists():assert digest(target)==asset['sha256']
        else:shutil.copyfile(source,target)
    atomic_json(destination/'status.json',summary)
    print(json.dumps(dict(status='RETAINED_OUTPUTS_COLLECTED',takes=len(summary['takes']))))


def main():
    os.umask(0o077)
    assert os.geteuid() == 0 and subprocess.check_output(['hostname'],text=True).strip() == 'wan-controller-01'
    os.chdir(ROOT)
    subprocess.run(['git','diff','--quiet'], check=True)
    subprocess.run(['git','diff','--cached','--quiet'], check=True)
    parser = argparse.ArgumentParser()
    parser.add_argument('operation', choices=['prepare','admit','launch','observe','export'])
    parser.add_argument('--trial', choices=['first','diagnostic','repair','validation','fallback','allocation','comparison'], default='first')
    args = parser.parse_args()
    select_trial(args.trial)
    {'prepare':prepare,'admit':admit,'launch':launch,'observe':observe,'export':export}[args.operation]()


if __name__ == '__main__':
    main()
