"""Trusted live execution wiring. No installed credentials/transport means no dispatch."""
from copy import deepcopy
import hashlib
import json

from services.controller.lifecycle import Lifecycle
from services.controller.allocation_retry import CapacityRetryProvider, capacity_rejected, candidate_profile
from services.controller.live_admission import LiveAdmission, _keys, configuration_hash
from services.controller.live_billing import ingest, totals
from services.controller.runpod import RunpodProvider
from services.controller.service import canonical, stamp
from services.controller.studio import require
from workers.gpu.common import LOCK, timestamp

WORKER_CMD = ['worker','--output-root','/worker','--weights','/models',
              '--result','/worker/result.json','--claim-wait-seconds','60']
BOOTSTRAP_ENTRYPOINT = ['bash', '-c']
COMPARISON_CMD = ['python -m workers.gpu.weights download /models && exec python -m workers.gpu.cli ' + ' '.join(WORKER_CMD) + ' --comparison-pair']
BOOTSTRAP_CMD = ['python -m workers.gpu.weights download /models && exec python -m workers.gpu.cli ' + ' '.join(WORKER_CMD)]


class LiveExecution:
    def __init__(self, admission, *, runpod_token=None, transport=None, billing_keys=None, candidate_check=None):
        require(type(admission) is LiveAdmission, 'Trusted live admission required')
        self.admission, self.control = admission, admission.control
        self._token, self._transport = runpod_token, transport
        self._candidate_check = candidate_check
        self._billing_keys = _keys(billing_keys or {})
        # Billing authority must not reuse an owner approval secret.
        require(not any(a[1] == b[1] for a in self._billing_keys.values() for b in admission._approval_keys.values()),
                'Billing keys must be distinct from owner approval keys')
        with self.control.transaction() as db:
            db.execute('''CREATE TABLE IF NOT EXISTS live_execution_bindings (
                batch TEXT PRIMARY KEY, credential TEXT NOT NULL,
                host_envelope TEXT NOT NULL, created TEXT NOT NULL)''')
            if 'allocation_attempts' not in {r[1] for r in db.execute('PRAGMA table_info(live_execution_bindings)')}:
                db.execute("ALTER TABLE live_execution_bindings ADD COLUMN allocation_attempts TEXT NOT NULL DEFAULT '[]'")

    def _context(self, db, owner, project, batch_id):
        bundle = self.control._load(db, owner, project)
        link = db.execute('SELECT approval,config_hash,dispatch_state FROM live_job_links WHERE batch=? AND owner=? AND project=?',
                          (batch_id,owner,project)).fetchone()
        if link is None: raise KeyError('Live execution unavailable')
        record = db.execute('SELECT envelope FROM live_approvals WHERE id=? AND owner=? AND project=?', (link[0],owner,project)).fetchone()
        require(record is not None,'Live approval binding missing')
        grant = json.loads(record[0])['payload']
        frozen=db.execute('SELECT snapshot FROM pod_batches WHERE id=?',(batch_id,)).fetchone()
        require(frozen is not None and json.loads(frozen[0]).get('config_hash')==link[1], 'Frozen execution binding changed')
        batch = self.control._batch(bundle,batch_id)
        row = db.execute('SELECT state,cleanup,pod_id,deadline FROM pod_batches WHERE id=? AND project=?',(batch_id,project)).fetchone()
        require(row is not None and batch['execution_mode']=='runpod' and batch['model_profile']==grant['profile']['model_profile'], 'Live lifecycle mismatch')
        return bundle,batch,link,grant,row

    def _provider(self, owner, project, batch_id, worker_token=None):
        require(self._transport is not None and isinstance(self._token,str) and bool(self._token), 'Live transport credentials are not installed')
        with self.control.transaction() as db:
            _,_,_,grant,_ = self._context(db,owner,project,batch_id)
        profile=deepcopy(grant['launch_profile'])
        if worker_token is not None:
            profile['env']={'WAN_WORKER_TOKEN':worker_token, 'WAN_WORKER_API_URL':grant['profile']['worker_endpoint']}
        scope=canonical([owner,project])
        provider=RunpodProvider(self._token,launch_profile=profile,scope=scope,transport=self._transport)
        def expected(pod_id):
            with self.control.transaction() as db:
                found=db.execute('''SELECT p.id FROM pod_batches p JOIN live_job_links l ON l.batch=p.id
                     WHERE p.id=? AND p.pod_id=? AND l.owner=? AND l.project=?''',(batch_id,pod_id,owner,project)).fetchone()
                return provider._name(batch_id,batch_id) if found else None
        provider._expected_names=expected
        if 'capacity_retry' in grant and worker_token is not None:
            policy = grant['capacity_retry']
            def before():
                with self.control.transaction() as db:
                    _,_,link,current,row = self._context(db,owner,project,batch_id)
                    self.admission._approval(db,owner,project,link[0])
                    require(current == grant and link[2] == 'attempted' and row[0] == 'provisioning' and
                            row[2] is None and row[3] - self.control.clock().timestamp() > policy['min_remaining_seconds'],
                            'Capacity retry is no longer authorized')
                    history = json.loads(db.execute('SELECT allocation_attempts FROM live_execution_bindings WHERE batch=?',
                                                   (batch_id,)).fetchone()[0])
                    require(len(history) < policy['max_attempts'] and
                            all(capacity_rejected(x.get('result', {})) for x in history),
                            'Allocation history cannot be retried')
                    event = {'attempt': len(history)+1, 'started_at': stamp(self.control.clock())}
                    if 'allocation_plan' in grant:
                        require(callable(self._candidate_check), 'Fresh candidate check required')
                        candidates = grant['allocation_plan']['candidates']
                        used = {x['candidate'] for x in history}
                        eligible = [i for i, candidate in enumerate(candidates) if i not in used and
                                    self._candidate_check(candidate, grant['allocation_plan']['max_hourly_cents'])]
                        require(bool(eligible), 'No untried eligible allocation candidate')
                        selected = eligible[0]
                        provider._profile = candidate_profile(profile, candidates[selected])
                        event['candidate'] = selected
                    if 'duration_comparison' in grant:
                        require(callable(self._candidate_check) and self._candidate_check(
                            dict(gpu_type=profile['gpu']['id'],data_center_ids=profile['dataCenterIds']),450),
                            'Fresh comparison quote required')
                    history.append(event)
                    db.execute('UPDATE live_execution_bindings SET allocation_attempts=? WHERE batch=?',
                               (canonical(history),batch_id))
                    return len(history)
            def record(attempt, result):
                try:
                    with self.control.transaction() as db:
                        history = json.loads(db.execute('SELECT allocation_attempts FROM live_execution_bindings WHERE batch=?',
                                                       (batch_id,)).fetchone()[0])
                        require(len(history) == attempt and 'result' not in history[-1], 'Allocation receipt conflict')
                        history[-1].update(result=result, finished_at=stamp(self.control.clock()))
                        db.execute('UPDATE live_execution_bindings SET allocation_attempts=? WHERE batch=?',
                                   (canonical(history),batch_id))
                except Exception:
                    raise ConnectionError('Allocation result could not be retained; no retry') from None
            return CapacityRetryProvider(provider,policy,before,record)
        return provider

    def _authorize_dispatch(self, db, owner, project, batch_id, host_envelope, worker_token):
        _,batch,link,_,row=self._context(db,owner,project,batch_id)
        require(link[2]=='disabled' and row[0]=='queued','New dispatch already attempted')
        grant,_=self.admission.verify_execution_evidence(db,owner,project,link[0],host_envelope)
        latest=db.execute('SELECT id FROM live_approvals WHERE owner=? AND project=? ORDER BY rowid DESC LIMIT 1',(owner,project)).fetchone()[0]
        require(latest==link[0], 'Live approval is not current')
        balance=totals(db,owner,project)
        require(balance['spent_cents']<grant['approved_cents'] and balance['spent_cents']+balance['reserved_cents']<=grant['approved_cents'], 'Live budget exhausted or overcommitted')
        require(timestamp(grant['valid_until']).timestamp()>=row[3] and row[3]>self.control.clock().timestamp(), 'Live runtime expired')
        launch=grant['launch_profile']
        direct = launch.get('cmd') == WORKER_CMD and launch.get('entrypoint', ['python','-m','workers.gpu.cli']) == ['python','-m','workers.gpu.cli']
        bootstrap = launch.get('cmd') == BOOTSTRAP_CMD and launch.get('entrypoint') == BOOTSTRAP_ENTRYPOINT and launch['mounts'] == {}
        comparison = (grant.get('duration_comparison') is not None and launch.get('cmd')==COMPARISON_CMD
                      and launch.get('entrypoint')==BOOTSTRAP_ENTRYPOINT and launch['mounts']=={})
        require(comparison if grant.get('duration_comparison') else direct or bootstrap, 'Exact scoped worker command required')
        require(row[3]-timestamp(batch['approved_at']).timestamp()>60, 'Runtime must include bounded startup wait')
        require(isinstance(worker_token,str), 'Trusted worker bootstrap credential required')
        credential=db.execute('SELECT id,expires,revoked FROM worker_credentials WHERE token_hash=? AND owner=? AND project=? AND batch=?',
                              (hashlib.sha256(worker_token.encode()).hexdigest(),owner,project,batch_id)).fetchone()
        require(credential is not None and not credential[2] and timestamp(credential[1]).timestamp()>row[3], 'Bootstrap credential does not cover runtime')
        db.execute('INSERT INTO live_execution_bindings (batch,credential,host_envelope,created) VALUES (?,?,?,?)',(batch_id,credential[0],canonical(host_envelope),stamp(self.control.clock())))
        db.execute("UPDATE live_job_links SET dispatch_state='attempted' WHERE batch=?",(batch_id,))

    def provision(self, owner, project, batch_id, host_envelope=None, *, worker_token=None):
        provider=self._provider(owner,project,batch_id,worker_token)
        lifecycle=Lifecycle(self.control.db_path,provider)
        lifecycle.provision(project,batch_id,self.control.clock().timestamp(),
                            authorize=lambda db:self._authorize_dispatch(db,owner,project,batch_id,host_envelope,worker_token))
        return self.status(owner,project,batch_id)

    def _refresh(self, db, owner, project, batch_id):
        bundle,batch,link,grant,row=self._context(db,owner,project,batch_id)
        batch.update(state=row[0],cleanup_state=row[1],provider_resource_id=row[2])
        reservation=db.execute('SELECT state,reserved_cents FROM live_reservations WHERE batch=?',(batch_id,)).fetchone()
        spent=db.execute('SELECT COALESCE(SUM(amount_cents),0) FROM live_billing_events WHERE batch=?',(batch_id,)).fetchone()[0]
        batch['budget'].update(spent_cents=spent,reserved_cents=max(0,reservation[1]-spent) if reservation[0]=='reserved' else 0)
        self.control._reconcile(bundle,batch,self.control.clock())
        self.synchronize(db,bundle,batch)
        self.control._save(db,bundle)
        return dict(batch=deepcopy(batch),budget=totals(db,owner,project),dispatch_state=link[2],reservation_state=reservation[0])

    def status(self, owner, project, batch_id):
        with self.control.transaction() as db:return self._refresh(db,owner,project,batch_id)

    def cancel(self, owner, project, batch_id):
        with self.control.transaction() as db:
            _,_,link,_,_=self._context(db,owner,project,batch_id)
        if link[2]=='disabled':
            return self.admission.cancel(owner,project,batch_id)
        # Never creates a provider or releases a dispatched reservation.
        Lifecycle(self.control.db_path,None).cancel(project,batch_id)
        return self.status(owner,project,batch_id)

    def watchdog(self):
        with self.control.transaction() as db:
            rows=db.execute("""SELECT l.owner,l.project,l.batch,l.dispatch_state,p.state FROM live_job_links l
                JOIN pod_batches p ON p.id=l.batch WHERE p.cleanup!='confirmed'
                AND (p.deadline<=? OR p.state IN ('succeeded','failed','canceled'))""",
                (self.control.clock().timestamp(),)).fetchall()
        unresolved=[]
        for owner,project,batch,dispatch_state,state in rows:
            try:
                if dispatch_state=='disabled' and state=='queued':
                    self.admission.cancel(owner,project,batch)
                    continue
                provider=self._provider(owner,project,batch)
                unresolved.extend(Lifecycle(self.control.db_path,provider).watchdog(self.control.clock().timestamp(),batch_ids={batch}))
                self.status(owner,project,batch)
            except (ValueError,ConnectionError,KeyError):
                unresolved.append(batch)
        return unresolved

    def authorize_scope(self, db, owner, project, batch_id):
        _,batch,link,_,row=self._context(db,owner,project,batch_id)
        if link[2]=='disabled':
            self.admission._approval(db,owner,project,link[0])
            require(row[0]=='queued','Undispatched job closed')
        else:
            require(link[2]=='attempted' and db.execute('SELECT batch FROM live_execution_bindings WHERE batch=?',(batch_id,)).fetchone(), 'Worker bootstrap binding missing')
        require(batch['state']==row[0] or (batch['state']=='queued' and row[0] in ('provisioning','rendering')),
                'Live worker state is not reconciled')
        if row[0]=='rendering': require(row[2] is not None,'Worker cannot run before resource reconciliation')

    def synchronize(self, db, bundle, batch):
        if batch['execution_mode']!='runpod':return
        owner,project=bundle['project']['owner_id'],bundle['project']['id']
        self._context(db,owner,project,batch['id'])
        if batch['state'] in ('succeeded','failed','canceled'):
            db.execute("""UPDATE pod_batches SET state=?,cleanup=CASE WHEN state='queued' THEN 'confirmed' ELSE cleanup END
                          WHERE id=? AND state IN ('queued','provisioning','rendering')""",(batch['state'],batch['id']))

    def ingest_bill(self, owner, project, envelope):
        result=ingest(self.control,self._billing_keys,owner,project,envelope)
        self.status(owner,project,envelope['payload']['batch'])
        return result
