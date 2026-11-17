"""Production policy comes from the admitted signed grant, never request JSON."""
import json
import hashlib
import math

from workers.gpu.production import validate_policy, validate_snapshots
from workers.gpu.common import require, timestamp


def policy(db, batch):
    tables = {r[0] for r in db.execute("SELECT name FROM sqlite_master WHERE type='table'")}
    if not {'live_job_links','live_approvals'} <= tables:
        return None
    row = db.execute('''SELECT a.envelope FROM live_job_links l JOIN live_approvals a ON a.id=l.approval
        WHERE l.batch=? AND l.project=? AND a.owner=l.owner AND a.project=l.project''',
        (batch['id'], batch['project_id'])).fetchone()
    value = json.loads(row[0])['payload'].get('continuous_queue') if row else None
    if value is not None:
        validate_policy(value)
        validate_snapshots(value, batch['shot_snapshots'])
    return value


def save_metrics(db, batch, attempt, value):
    require(policy(db,batch) is not None, 'Production telemetry needs signed scope')
    fields = {'protocol','attempt_id','batch_id','asset_sha256','asset_bytes','metrics'}
    require(isinstance(value,dict) and set(value) == fields and
            value['protocol'] == 'wan-song-queue-v1' and value['attempt_id'] == attempt['id'] and
            value['batch_id'] == batch['id'], 'Telemetry identity mismatch')
    m = value['metrics']
    require(isinstance(m,dict) and len(json.dumps(m)) <= 8192 and m['model_profile'] == attempt['model_profile'],
            'Telemetry profile mismatch')
    for field in ('model_load_seconds','generation_seconds','decode_encode_seconds','upload_seconds',
                  'render_and_verify_seconds','gpu_peak_allocated_bytes','gpu_peak_reserved_bytes'):
        require(type(m.get(field)) in (float,int) and math.isfinite(m[field]) and 0 <= m[field] <= 1e12,
                'Invalid production metric')
    require(m['process_start'] in ('cold','warm'), 'Invalid model session metric')
    payload = json.dumps(value,sort_keys=True,separators=(',',':'),allow_nan=False)
    receipt = hashlib.sha256(payload.encode()).hexdigest()
    row = db.execute('SELECT payload FROM worker_telemetry WHERE attempt=?',(attempt['id'],)).fetchone()
    require(row is None or row[0] == payload, 'Conflicting production telemetry')
    if row is None:
        db.execute('INSERT INTO worker_telemetry VALUES (?,?,?,?,?)',
                   (attempt['id'],batch['id'],batch['project_id'],payload,receipt))
    return {'sha256':receipt}


def require_metrics(db, batch, attempt, asset):
    if policy(db,batch) is None:
        return
    row = db.execute('SELECT payload FROM worker_telemetry WHERE attempt=?',(attempt['id'],)).fetchone()
    require(row is not None, 'Production metrics must be durable before completion')
    value = json.loads(row[0])
    require(value['asset_sha256'] == asset['sha256'] and value['asset_bytes'] == asset['bytes'], 'Telemetry asset mismatch')


def claim_gate(db, bundle, batch, now):
    if policy(db,batch) is None:
        return True
    active = [a for a in bundle['attempts'] if a['batch_id'] == batch['id'] and a['state'] in ('claimed','running')]
    if active:
        return False
    row = db.execute('SELECT payload FROM worker_telemetry WHERE batch=? ORDER BY rowid DESC LIMIT 1',(batch['id'],)).fetchone()
    seconds = json.loads(row[0])['metrics']['render_and_verify_seconds'] if row else 0
    if (timestamp(batch['deadline_at'])-now).total_seconds() < max(120, seconds*1.15+60):
        # Closing immediately enables the independent watchdog to delete the Pod.
        batch['state'] = 'failed'
        return False
    return True
