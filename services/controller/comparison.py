"""Controller-only lookup of source-bound comparison authority and durable metrics."""
import json
from workers.gpu.comparison import validate_policy, validate_snapshots, validate_metrics, receipt, continuation_gate
from workers.gpu.common import timestamp


def initialize(db):
    db.execute('CREATE TABLE IF NOT EXISTS worker_telemetry (attempt TEXT PRIMARY KEY, batch TEXT NOT NULL, project TEXT NOT NULL, payload TEXT NOT NULL, receipt TEXT NOT NULL)')
    db.execute('CREATE TABLE IF NOT EXISTS comparison_gates (batch TEXT PRIMARY KEY, decision TEXT NOT NULL)')


def experiment(db,batch):
    if batch['execution_mode']!='runpod': return None
    if not db.execute("SELECT 1 FROM sqlite_master WHERE name='live_job_links'").fetchone(): return None
    row=db.execute('SELECT a.envelope FROM live_approvals a JOIN live_job_links l ON l.approval=a.id WHERE l.batch=? AND l.project=?',
                   (batch['id'],batch['project_id'])).fetchone()
    value=json.loads(row[0])['payload'].get('duration_comparison') if row else None
    if value is not None: validate_snapshots(value,batch['shot_snapshots'])
    return value


def claim_gate(db,bundle,batch,snapshot,now):
    value=experiment(db,batch)
    if value is None:return True
    attempts=[a for a in bundle['attempts'] if a['batch_id']==batch['id']]
    if any(a['state'] in ('claimed','running','failed','canceled') for a in attempts):return False
    if any(a['shot_id']==snapshot['shot_id'] for a in attempts):return False
    index=value['shot_ids'].index(snapshot['shot_id'])
    if index==0:return not attempts
    if len(attempts)!=1 or attempts[0]['shot_id']!=value['shot_ids'][0] or attempts[0]['state']!='succeeded':return False
    first=attempts[0]
    row=db.execute('SELECT payload FROM worker_telemetry WHERE attempt=? AND batch=? AND project=?',
                   (first['id'],batch['id'],batch['project_id'])).fetchone()
    if row is None or not any(t['attempt_id']==first['id'] for t in bundle['takes']):return False
    metrics=json.loads(row[0])
    gate=continuation_gate(metrics,(timestamp(batch['deadline_at'])-now).total_seconds())
    db.execute('INSERT OR REPLACE INTO comparison_gates VALUES (?,?)',(batch['id'],json.dumps(gate,sort_keys=True)))
    if not gate['allowed']:batch['state']='failed'
    return gate['allowed']


def save_metrics(db,batch,attempt,payload):
    value=experiment(db,batch)
    if value is None:raise ValueError('Telemetry is only enabled for the comparison scope')
    snapshot=next(s for s in batch['shot_snapshots'] if s['shot_id']==attempt['shot_id'])
    validate_metrics(payload,value,attempt,snapshot)
    checksum=receipt(payload)
    prior=db.execute('SELECT receipt FROM worker_telemetry WHERE attempt=?',(attempt['id'],)).fetchone()
    if prior and prior[0]!=checksum:raise ValueError('Telemetry replay conflict')
    if not prior:db.execute('INSERT INTO worker_telemetry VALUES (?,?,?,?,?)',
                           (attempt['id'],batch['id'],batch['project_id'],json.dumps(payload,sort_keys=True),checksum))
    return {'sha256':checksum}


def require_metrics(db,batch,attempt,asset):
    if experiment(db,batch) is None:return
    row=db.execute('SELECT payload FROM worker_telemetry WHERE attempt=? AND batch=? AND project=?',
                   (attempt['id'],batch['id'],batch['project_id'])).fetchone()
    if row is None:raise ValueError('Durable telemetry acknowledgement required')
    value=json.loads(row[0])
    if value['asset_sha256']!=asset['sha256'] or value['asset_bytes']!=asset['bytes']:
        raise ValueError('Telemetry output checksum mismatch')
