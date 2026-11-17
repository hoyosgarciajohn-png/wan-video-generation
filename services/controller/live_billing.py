"""Delegated signed billing receipts; provider invoice reconciliation is external."""
import json
from uuid import uuid4

from services.controller.budget import cents
from services.controller.service import canonical, stamp
from services.controller.studio import require, StudioConflict
from workers.gpu.common import timestamp

BILLING_DOMAIN = 'wan-live-billing-receipt-v1'


def initialize(db):
    db.execute('''CREATE TABLE IF NOT EXISTS live_billing_events (
        id TEXT PRIMARY KEY, owner TEXT NOT NULL, project TEXT NOT NULL,
        batch TEXT NOT NULL, kind TEXT NOT NULL, amount_cents INTEGER NOT NULL,
        envelope TEXT NOT NULL, created TEXT NOT NULL)''')
    db.execute('''CREATE TABLE IF NOT EXISTS live_recovery_caps (
        batch TEXT PRIMARY KEY, approval TEXT NOT NULL UNIQUE,
        retained_cents INTEGER NOT NULL, created TEXT NOT NULL)''')


def totals(db, owner, project):
    rows = db.execute('''SELECT r.batch,COALESCE(c.retained_cents,r.reserved_cents),r.state,COALESCE(SUM(e.amount_cents),0)
        FROM live_reservations r LEFT JOIN live_billing_events e ON e.batch=r.batch
        LEFT JOIN live_recovery_caps c ON c.batch=r.batch
        WHERE r.owner=? AND r.project=? GROUP BY r.batch,r.reserved_cents,r.state''', (owner, project)).fetchall()
    return dict(spent_cents=sum(r[3] for r in rows),
                reserved_cents=sum(max(0,r[1]-r[3]) for r in rows if r[2]=='reserved'),
                unsettled_count=sum(r[2]=='reserved' for r in rows))


def ingest(control, keys, owner, project, envelope):
    from services.controller.live_admission import _verify
    receipt = _verify(envelope, keys, BILLING_DOMAIN, owner)
    require(set(receipt)=={'id','owner','project','batch','kind','amount_cents','bill_reference','valid_until','provider_resource_id','currency'}, 'Exact billing receipt required')
    require(receipt['owner']==owner and receipt['project']==project, 'Billing owner/project mismatch')
    for key in ('id','batch','bill_reference'):
        require(isinstance(receipt[key],str) and 0<len(receipt[key])<=500, 'Billing identifier required')
    require(receipt['currency']=='USD', 'Only USD billing supported')
    require(receipt['kind'] in ('charge','settlement'), 'Invalid billing kind')
    cents(receipt['amount_cents'])
    with control.transaction() as db:
        control._load(db,owner,project)
        row=db.execute('SELECT state FROM live_reservations WHERE batch=? AND owner=? AND project=?',
                       (receipt['batch'],owner,project)).fetchone()
        if row is None: raise KeyError('Live reservation unavailable')
        pod=db.execute('SELECT pod_id FROM pod_batches WHERE id=? AND project=?',(receipt['batch'],project)).fetchone()
        require(pod is not None and pod[0]==receipt['provider_resource_id'], 'Billing resource identity mismatch')
        prior=db.execute('SELECT envelope FROM live_billing_events WHERE id=?',(receipt['id'],)).fetchone()
        if prior:
            if prior[0]!=canonical(envelope): raise StudioConflict('Billing receipt ID conflict')
            return totals(db,owner,project)
        require(timestamp(receipt['valid_until'])>control.clock(), 'Billing receipt expired')
        require(row[0] in ('reserved','settled'), 'Released never-dispatched reservation cannot receive billing')
        if receipt['kind']=='charge':
            require(isinstance(pod[0],str) and bool(pod[0]), 'Charge requires an observed provider resource')
        amount=receipt['amount_cents']
        if receipt['kind']=='settlement':
            lifecycle=db.execute('SELECT state,cleanup FROM pod_batches WHERE id=?',(receipt['batch'],)).fetchone()
            require(lifecycle and lifecycle[0] in ('succeeded','failed','canceled') and lifecycle[1]=='confirmed',
                    'Final settlement requires confirmed cleanup')
            require(row[0]=='reserved','Reservation already closed')
            observed=db.execute('SELECT COALESCE(SUM(amount_cents),0) FROM live_billing_events WHERE batch=?',(receipt['batch'],)).fetchone()[0]
            require(amount>=observed,'Final cumulative bill cannot erase charges')
            amount-=observed
            db.execute("UPDATE live_reservations SET state='settled' WHERE batch=?",(receipt['batch'],))
        db.execute('INSERT INTO live_billing_events VALUES (?,?,?,?,?,?,?,?)',
                   (receipt['id'],owner,project,receipt['batch'],receipt['kind'],amount,canonical(envelope),stamp(control.clock())))
        return totals(db,owner,project)
