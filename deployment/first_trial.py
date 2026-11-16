"""Private operator for separately approved, isolated one-attempt Wan trials.

The web service receives worker traffic but never receives provider credentials or
signing keys. No scheduler and no create retry exist here. Preparation is free;
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
from services.controller.live_admission import LiveAdmission, APPROVAL_DOMAIN, HOST_DOMAIN, configuration_hash
from services.controller.live_billing import BILLING_DOMAIN
from services.controller.live_execution import LiveExecution, BOOTSTRAP_CMD, BOOTSTRAP_ENTRYPOINT
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


def select_trial(name):
    """Allowlisted operator scope, never an arbitrary path or mutable retry."""
    global TRIAL, AUTH, IMAGE, BUILD_EVIDENCE, TITLE, DURATION_MS
    global APPROVAL_ID, IDEMPOTENCY_KEY, WORKER_ID, EXPECTED_PRIOR_BATCHES
    if name == 'first':
        return
    if name == 'repair':
        return select_repair_trial()
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


def select_repair_trial():
    global TRIAL, AUTH, IMAGE, BUILD_EVIDENCE, TITLE, DURATION_MS
    global APPROVAL_ID, IDEMPOTENCY_KEY, WORKER_ID, EXPECTED_PRIOR_BATCHES
    proposal = read(ROOT / 'deployment/repair-trial-proposal.json')
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


def prior_history_closed(db):
    rows = db.execute('SELECT l.batch,p.state,p.cleanup FROM live_job_links AS l '
                      'LEFT JOIN pod_batches AS p ON p.id=l.batch').fetchall()
    assert {row[0] for row in rows} == EXPECTED_PRIOR_BATCHES
    assert all(row[1] in ('succeeded','failed','canceled') and row[2] == 'confirmed' for row in rows)
    assert db.execute("SELECT count(*) FROM pod_batches WHERE cleanup!='confirmed' OR state NOT IN ('succeeded','failed','canceled')").fetchone()[0] == 0


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
        transport=https_transport(), billing_keys={'billing': (OWNER, bytes.fromhex(keys['billing']))})
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


def checked_quote(region=None):
    # Supplied by the authorized connected Runpod read, via pinned operator SSH.
    # The existing cleanup credential deliberately has no catalog/billing access.
    value = catalog_snapshot()
    price = Decimal(str(value['price']['secure']))
    assert value['id'] == GPU and value['secure'] and 0 < price <= Decimal('1.00')
    available = [x['id'] for x in value.get('dataCenters', []) if x.get('availability') in ('HIGH', 'MEDIUM', 'LOW')]
    if region is None:
        region = next((x for x in ('EU-RO-1', 'US-IL-1', 'EUR-IS-1', 'EUR-IS-2') if x in available), None)
    assert region in available, 'Approved GPU region has no current capacity'
    return {'checked_at': time.time(), 'gpu': GPU, 'region': region, 'usd_per_hour': str(price), 'min_cuda': '12.8'}


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
    assert status['ready'] and 0 <= time.time() - status['checked_at'] < 45
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
    workspace = studio.save(OWNER, workspace, workspace['revision'])
    profile = dict(model_profile=deepcopy(LOCK['profile']), image_ref=IMAGE, gpu_type=GPU, gpu_count=1,
        region=pricing['region'], worker_endpoint=ORIGIN, storage_id='wan-controller-01-artifacts')
    launch = dict(image=IMAGE, gpu={'id': GPU, 'count': 1, 'minCudaVersion': '12.8', 'minRamPerGpu': 64}, cloud='SECURE',
        disk=80, dataCenterIds=[pricing['region']], mounts={}, ports=[], env={}, registry=REGISTRY,
        entrypoint=BOOTSTRAP_ENTRYPOINT, cmd=BOOTSTRAP_CMD)
    expires = stamp(utcnow() + timedelta(hours=6))
    grant = dict(id=APPROVAL_ID, owner=OWNER, project=project, currency='USD', approved_cents=400,
        max_runtime_seconds=1800, valid_until=expires, profile=profile, launch_profile=launch, source_sha256=_sources())
    host = dict(owner=OWNER, project=project, config_hash=configuration_hash(profile, launch), source_sha256=grant['source_sha256'],
        build_manifest_sha256=build['manifest_sha256'], valid_until=expires, worker_endpoint=ORIGIN, storage_id=profile['storage_id'])
    atomic_json(TRIAL / 'approval.json', sign(grant, 'owner', APPROVAL_DOMAIN))
    atomic_json(TRIAL / 'host.json', sign(host, 'host', HOST_DOMAIN))
    atomic_json(TRIAL / 'prepared.json', dict(owner=OWNER, project=project, shot=shot['id'], pricing=pricing,
        source_commit=subprocess.check_output(['git','rev-parse','HEAD'], text=True).strip(), build=build,
        overall_cap_cents=500, pod_cap_cents=400, storage_allowance_cents=100, runtime_seconds=1800, max_attempts=1))
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


def admit():
    primary_ready()
    assert not (TRIAL / 'job.json').exists()
    saved = read(TRIAL / 'prepared.json')
    c, a, e = services()
    with c.transaction() as db:
        prior_history_closed(db)
    a.approve(OWNER, saved['project'], read(TRIAL / 'approval.json'))
    with c.transaction() as db:
        a.verify_execution_evidence(db, OWNER, saved['project'], read(TRIAL / 'approval.json')['payload']['id'], read(TRIAL / 'host.json'))
    pricing = checked_quote(saved['pricing']['region'])
    request = dict(approval_id=APPROVAL_ID, shot_ids=[saved['shot']], expected_revision=a.studio.get(OWNER)['revision'],
        reservation_cents=400, runtime_seconds=1800, idempotency_key=IDEMPOTENCY_KEY)
    result = a.submit(OWNER, saved['project'], request)
    batch = result['batch']['id']
    atomic_json(TRIAL / 'job.json', dict(project=saved['project'], batch=batch,
        deadline=int(timestamp(result['batch']['deadline_at']).timestamp()), scope=canonical([OWNER,saved['project']]), pricing=pricing))
    worker = WorkerTransport(c, real_jobs=e).issue(OWNER, saved['project'], batch, WORKER_ID, ttl_seconds=2100)
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
            if not hourly.is_finite() or hourly > Decimal('1.00'):
                e.cancel(OWNER, job['project'], job['batch'])
                provider['canceled_above_price_ceiling'] = True
        except Exception:
            provider = {'status':'OBSERVATION_UNAVAILABLE'}
    billing = bill_snapshot(c, e, job, pod) if pod else {'status':'NO_POD_ID'}
    unresolved = e.watchdog()
    result = e.status(OWNER, job['project'], job['batch'])
    bundle = c.bundle(OWNER, job['project'])
    summary = dict(checked_at=time.time(), batch=result['batch'], budget=result['budget'], reservation_state=result['reservation_state'],
        provider=provider, billing=billing, unresolved=unresolved, takes=bundle['takes'], attempts=bundle['attempts'])
    atomic_json(TRIAL / 'status.json', summary)
    print(json.dumps(summary), flush=True)
    return summary


def launch():
    primary_ready()
    job = read(TRIAL / 'job.json')
    ready = guard_ready(job)
    # The CI caller supplies a live GitHub API observation before this SSH call.
    assert os.environ.get('WAN_VERIFIED_GUARD_RUN') == ready['run_id']
    checked_quote(job['pricing']['region'])
    c, a, e = services()
    with c.transaction() as db:
        assert db.execute("SELECT dispatch_state FROM live_job_links WHERE batch=?",(job['batch'],)).fetchone()[0] == 'disabled'
    print(json.dumps({'status':'ONE_CREATE_ATTEMPT_STARTING','batch':job['batch'],'deadline':job['deadline']}), flush=True)
    e.provision(OWNER, job['project'], job['batch'], read(TRIAL / 'host.json'), worker_token=read(TRIAL / 'worker.json')['token'])
    while time.time() < job['deadline'] + 60:
        status = observe()
        if status['batch']['cleanup_state'] == 'confirmed':
            break
        time.sleep(15)
    final = observe()
    if final['batch']['cleanup_state'] != 'confirmed':
        raise SystemExit('Cleanup remains unresolved; separate guard remains responsible')


def main():
    os.umask(0o077)
    assert os.geteuid() == 0 and subprocess.check_output(['hostname'],text=True).strip() == 'wan-controller-01'
    os.chdir(ROOT)
    subprocess.run(['git','diff','--quiet'], check=True)
    subprocess.run(['git','diff','--cached','--quiet'], check=True)
    parser = argparse.ArgumentParser()
    parser.add_argument('operation', choices=['prepare','admit','launch','observe'])
    parser.add_argument('--trial', choices=['first','diagnostic','repair'], default='first')
    args = parser.parse_args()
    select_trial(args.trial)
    {'prepare':prepare,'admit':admit,'launch':launch,'observe':observe}[args.operation]()


if __name__ == '__main__':
    main()
