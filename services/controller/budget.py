"""Persistent simulated budget authority; never authorizes real provider spending.

The trusted host supplies owner identity. All money is integer USD cents. A new
immutable approval changes future admission terms; historical liability is never
erased. Reservations are estimates, not a provider billing hard stop.
"""
import json
from uuid import uuid4

from services.controller.service import canonical, stamp
from services.controller.studio import StudioConflict, require
from workers.gpu.common import timestamp

MAX_CENTS = 2**53 - 1


def cents(value, *, positive=False):
    require(type(value) is int and (1 if positive else 0) <= value <= MAX_CENTS, 'Invalid integer USD cents')


class BudgetLedger:
    def __init__(self, control):
        self.control = control
        with control.transaction() as db:
            db.execute('''CREATE TABLE IF NOT EXISTS budget_approvals (
                id TEXT PRIMARY KEY, owner TEXT NOT NULL, project TEXT NOT NULL,
                idem TEXT NOT NULL, terms TEXT NOT NULL, created TEXT NOT NULL,
                revoked INTEGER NOT NULL DEFAULT 0, mode TEXT NOT NULL DEFAULT 'simulation',
                UNIQUE(owner,project,idem))''')
            db.execute('''CREATE TABLE IF NOT EXISTS budget_reservations (
                batch TEXT PRIMARY KEY, owner TEXT NOT NULL, project TEXT NOT NULL,
                approval TEXT NOT NULL, idem TEXT NOT NULL, request TEXT NOT NULL,
                reserved_cents INTEGER NOT NULL, state TEXT NOT NULL DEFAULT 'reserved',
                created TEXT NOT NULL, UNIQUE(owner,project,idem))''')
            db.execute('''CREATE TABLE IF NOT EXISTS budget_events (
                id TEXT PRIMARY KEY, owner TEXT NOT NULL, project TEXT NOT NULL,
                batch TEXT NOT NULL, idem TEXT NOT NULL, request TEXT NOT NULL,
                kind TEXT NOT NULL, amount_cents INTEGER NOT NULL, created TEXT NOT NULL,
                UNIQUE(owner,project,idem))''')

    def _project(self, db, owner, project):
        return self.control._load(db, owner, project)

    @staticmethod
    def _approval(db, owner, project, approval_id=None):
        fields = 'id,terms,created,revoked,mode'
        row = (db.execute(f'SELECT {fields} FROM budget_approvals WHERE owner=? AND project=? AND id=?',
                          (owner, project, approval_id)).fetchone() if approval_id else
               db.execute(f'SELECT {fields} FROM budget_approvals WHERE owner=? AND project=? ORDER BY rowid DESC LIMIT 1',
                          (owner, project)).fetchone())
        if row is None:
            raise KeyError('Budget approval unavailable')
        value = dict(zip(('id','terms','created_at','revoked','mode'), row))
        value['terms'] = json.loads(value['terms'])
        value['revoked'] = bool(value['revoked'])
        return value

    def approve(self, owner, project, terms, idempotency_key):
        require(isinstance(terms, dict) and set(terms) == {'currency','approved_cents','max_runtime_seconds','valid_until','profile'},
                'Exact approval terms required')
        require(terms['currency'] == 'USD', 'Only USD is supported')
        cents(terms['approved_cents'], positive=True)
        require(type(terms['max_runtime_seconds']) is int and 0 < terms['max_runtime_seconds'] <= 86400,
                'Runtime envelope must be 1 to 86400 seconds')
        require(isinstance(terms['valid_until'], str), 'Approval expiry required')
        end = timestamp(terms['valid_until'])
        require(isinstance(terms['profile'], dict) and bool(terms['profile']) and len(canonical(terms['profile'])) <= 16000,
                'Exact simulated launch profile required')
        self._key(idempotency_key)
        with self.control.transaction() as db:
            self._project(db, owner, project)
            prior = db.execute('SELECT id,terms FROM budget_approvals WHERE owner=? AND project=? AND idem=?',
                               (owner, project, idempotency_key)).fetchone()
            if prior:
                if prior[1] != canonical(terms):
                    raise StudioConflict('Approval idempotency conflict')
                return self._approval(db, owner, project, prior[0])
            require(end > self.control.clock(), 'Approval must expire in the future')
            approval_id = uuid4().hex
            db.execute('INSERT INTO budget_approvals (id,owner,project,idem,terms,created) VALUES (?,?,?,?,?,?)',
                       (approval_id, owner, project, idempotency_key, canonical(terms), stamp(self.control.clock())))
            return self._approval(db, owner, project, approval_id)

    @staticmethod
    def _key(key):
        require(isinstance(key, str) and 0 < len(key.strip()) <= 200, 'Idempotency key required')

    @staticmethod
    def _reservation(db, owner, project, batch):
        row = db.execute('SELECT batch,approval,reserved_cents,state,request FROM budget_reservations WHERE batch=? AND owner=? AND project=?',
                         (batch, owner, project)).fetchone()
        if row is None:
            raise KeyError('Budget reservation unavailable')
        return dict(zip(('batch_id','approval_id','reserved_cents','state','request'), row))

    def _status(self, db, owner, project):
        self._project(db, owner, project)
        try:
            approval = self._approval(db, owner, project)
        except KeyError:
            approval = None
        rows = db.execute('''SELECT r.batch,r.reserved_cents,r.state,COALESCE(SUM(e.amount_cents),0)
                FROM budget_reservations r LEFT JOIN budget_events e ON e.batch=r.batch
                WHERE r.owner=? AND r.project=? GROUP BY r.batch,r.reserved_cents,r.state''', (owner, project)).fetchall()
        spent = sum(row[3] for row in rows)
        reserved = sum(max(0, row[1] - row[3]) for row in rows if row[2] == 'reserved')
        cap = approval['terms']['approved_cents'] if approval else 0
        active = bool(approval and not approval['revoked'] and approval['mode'] == 'simulation' and
                      timestamp(approval['terms']['valid_until']) > self.control.clock())
        return dict(mode='simulation', approval=approval, approved_cents=cap, spent_cents=spent,
                    reserved_cents=reserved, unsettled_count=sum(row[2] == 'reserved' for row in rows),
                    available_cents=max(0, cap - spent - reserved), overrun_cents=max(0, spent - cap),
                    overcommitted=spent + reserved > cap, admission_blocked=not active or spent + reserved >= cap)

    def status(self, owner, project):
        with self.control.transaction() as db:
            return self._status(db, owner, project)

    def revoke(self, owner, project, approval_id):
        with self.control.transaction() as db:
            self._project(db, owner, project)
            self._approval(db, owner, project, approval_id)
            db.execute('UPDATE budget_approvals SET revoked=1 WHERE id=?', (approval_id,))
            return self._status(db, owner, project)

    def _reserve(self, db, owner, project, batch_id, request):
        """Coordinator calls inside the SAME transaction as lifecycle insertion."""
        approval = self._approval(db, owner, project, request['approval_id'])
        status = self._status(db, owner, project)
        require(approval['mode'] == 'simulation' and not approval['revoked'] and
                status['approval']['id'] == approval['id'], 'Approval is not current')
        require(not status['admission_blocked'] and request['reservation_cents'] <= status['available_cents'],
                'Budget has insufficient uncommitted approval')
        require(request['runtime_seconds'] <= approval['terms']['max_runtime_seconds'], 'Runtime exceeds approval')
        now = self.control.clock()
        require(now.timestamp() + request['runtime_seconds'] <= timestamp(approval['terms']['valid_until']).timestamp(),
                'Runtime exceeds approval expiry')
        db.execute('INSERT INTO budget_reservations (batch,owner,project,approval,idem,request,reserved_cents,created) VALUES (?,?,?,?,?,?,?,?)',
                   (batch_id, owner, project, approval['id'], request['idempotency_key'], canonical(request),
                    request['reservation_cents'], stamp(now)))
        return approval

    def _event(self, owner, project, batch, amount, bill_reference, key, kind):
        cents(amount)
        self._key(key)
        require(isinstance(bill_reference, str) and 0 < len(bill_reference.strip()) <= 500, 'Explicit simulated billing reference required')
        request = dict(batch_id=batch, amount_cents=amount, bill_reference=bill_reference, kind=kind)
        with self.control.transaction() as db:
            self._project(db, owner, project)
            reservation = self._reservation(db, owner, project, batch)
            prior = db.execute('SELECT request,id,amount_cents FROM budget_events WHERE owner=? AND project=? AND idem=?',
                               (owner, project, key)).fetchone()
            if prior:
                if prior[0] != canonical(request):
                    raise StudioConflict('Billing idempotency conflict')
                return dict(event_id=prior[1], recorded_cents=prior[2], budget=self._status(db, owner, project))
            delta = amount
            if kind == 'settlement':
                row = db.execute('SELECT state,cleanup FROM pod_batches WHERE id=? AND project=?', (batch, project)).fetchone()
                require(row is not None and row[0] in ('succeeded','failed','canceled') and row[1] == 'confirmed',
                        'Settlement requires confirmed cleanup or confirmed never-dispatched cancellation')
                require(reservation['state'] == 'reserved', 'Reservation already settled; record a late charge separately')
                total = db.execute('SELECT COALESCE(SUM(amount_cents),0) FROM budget_events WHERE batch=?', (batch,)).fetchone()[0]
                require(amount >= total, 'Settlement cannot erase recorded charges')
                delta = amount - total
                db.execute("UPDATE budget_reservations SET state='settled' WHERE batch=?", (batch,))
            event_id = uuid4().hex
            db.execute('INSERT INTO budget_events VALUES (?,?,?,?,?,?,?,?,?)',
                       (event_id, owner, project, batch, key, canonical(request), kind, delta, stamp(self.control.clock())))
            return dict(event_id=event_id, recorded_cents=delta, budget=self._status(db, owner, project))

    def record_charge(self, owner, project, batch_id, amount_cents, bill_reference, idempotency_key):
        """Append an incremental observed charge, including late/over-cap charges."""
        return self._event(owner, project, batch_id, amount_cents, bill_reference, idempotency_key, 'charge')

    def settle(self, owner, project, batch_id, total_cents, bill_reference, idempotency_key):
        """Explicit final cumulative bill; cleanup confirmation alone never settles."""
        return self._event(owner, project, batch_id, total_cents, bill_reference, idempotency_key, 'settlement')
