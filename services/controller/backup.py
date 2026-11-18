"""Checksummed local SQLite/media backups and restore into an empty destination.

Current application assets are immutable and published before their DB commit.
SQLite backup pins a read transaction; referenced assets can then be copied while
new work proceeds. External mutation or deletion causes verification failure.
"""
import argparse
from contextlib import contextmanager
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path, PurePosixPath
import sqlite3
import stat
from urllib.parse import quote

from scripts.validate_contract import validate_bundle
from services.controller.service import canonical
from workers.gpu.common import digest, sync_dir, timestamp

TABLES = {'worker_telemetry','comparison_gates','projects','admissions','completions','studio_owners','studio_projects',
          'command_receipts','upload_sessions','upload_chunks','export_jobs','pod_batches',
          'budget_approvals','budget_reservations','budget_events','worker_credentials','real_job_links',
          'live_approvals','live_reservations','live_job_links','live_billing_events','live_execution_bindings','live_recovery_caps'}
TABLES.update({'longcat_budgets','longcat_scopes','longcat_shots','longcat_cleanup'})
DB_NAME = 'database.sqlite'


def require(value, message):
    if not value:
        raise ValueError(message)


def _plain_path(path):
    path = Path(path).absolute()
    for part in (path, *path.parents):
        require(not part.is_symlink(), 'Symlinks are not accepted')
    return path.resolve()


def _file(path, *, hardlinks=False):
    path = _plain_path(path)
    info = path.stat()
    require(stat.S_ISREG(info.st_mode) and (hardlinks or info.st_nlink == 1), 'Expected a regular unlinked backup file')
    return path


def _key(key):
    require(isinstance(key, str) and key and '\\' not in key and '\x00' not in key,
            'Invalid relative path')
    value = PurePosixPath(key)
    require(not value.is_absolute() and '..' not in value.parts and str(value) == key and key != '.',
            'Unsafe relative path')
    return key


def _destination(path):
    path = _plain_path(path)
    if path.exists():
        require(path.is_dir() and not any(path.iterdir()), 'Destination must be empty; existing data is never overwritten')
    else:
        require(path.parent.is_dir(), 'Destination parent must already exist')
        path.mkdir(mode=0o700)
        sync_dir(path.parent)
    return path


@contextmanager
def _connect(path, readonly=False):
    path = _plain_path(path)
    connection = sqlite3.connect(f"file:{quote(str(path), safe='/')}?mode={'ro' if readonly else 'rw'}", uri=True)
    connection.execute('PRAGMA trusted_schema=OFF')
    connection.enable_load_extension(False)
    try:
        with connection:
            yield connection
    finally:
        connection.close()


def _tables(db):
    objects = db.execute("SELECT type,name FROM sqlite_master WHERE name NOT LIKE 'sqlite_%'").fetchall()
    require(all(kind in ('table','index') and (kind == 'index' or name in TABLES) for kind, name in objects),
            'Unsupported database objects; backup only the application database')
    names = {name for kind, name in objects if kind == 'table'}
    require('projects' in names, 'Missing project database')
    return names


def _inspect_budget(db, names, projects):
    """Preserve settled simulation history; never restore uncertain liabilities."""
    ledger_tables = {'budget_approvals', 'budget_reservations', 'budget_events'}
    if not names & ledger_tables:
        return
    require(ledger_tables <= names, 'Incomplete budget ledger schema')

    def owner_matches(owner, project):
        return project in projects and projects[project]['project']['owner_id'] == owner

    def money(amount, positive=False):
        return type(amount) is int and (1 if positive else 0) <= amount <= 2**53 - 1

    approvals = {}
    for identity, owner, project, raw, revoked, mode in db.execute(
            'SELECT id,owner,project,terms,revoked,mode FROM budget_approvals'):
        terms = json.loads(raw)
        require(owner_matches(owner, project) and mode == 'simulation' and revoked in (0, 1),
                'Invalid budget approval ownership or mode')
        require(isinstance(terms, dict) and terms.get('currency') == 'USD' and
                money(terms.get('approved_cents'), True) and
                type(terms.get('max_runtime_seconds')) is int and 0 < terms['max_runtime_seconds'] <= 86400 and
                isinstance(terms.get('profile'), dict) and bool(terms['profile']), 'Invalid budget approval terms')
        timestamp(terms['valid_until'])
        approvals[identity] = (owner, project)
    reservations = {}
    for batch, owner, project, approval, reserved, state, raw in db.execute(
            'SELECT batch,owner,project,approval,reserved_cents,state,request FROM budget_reservations'):
        require(owner_matches(owner, project) and approvals.get(approval) == (owner, project) and money(reserved, True),
                'Invalid reservation ownership or approval')
        require(state == 'settled', 'Outstanding budget liability must be explicitly settled before backup')
        require('pod_batches' in names, 'Budget lifecycle unavailable')
        pod = db.execute('SELECT project,state,cleanup FROM pod_batches WHERE id=?', (batch,)).fetchone()
        require(pod and pod[0] == project and pod[1] in ('succeeded','failed','canceled') and pod[2] == 'confirmed',
                'Settled budget lifecycle is not closed')
        request = json.loads(raw)
        require(request.get('approval_id') == approval and request.get('reservation_cents') == reserved,
                'Reservation receipt mismatch')
        reservations[batch] = (owner, project)
    totals, settlements = {}, set()
    for owner, project, batch, raw, kind, delta in db.execute(
            'SELECT owner,project,batch,request,kind,amount_cents FROM budget_events ORDER BY rowid'):
        request = json.loads(raw)
        require(reservations.get(batch) == (owner, project) and kind in ('charge','settlement') and money(delta),
                'Invalid billing event ownership or amount')
        require(request.get('batch_id') == batch and request.get('kind') == kind and
                money(request.get('amount_cents')) and isinstance(request.get('bill_reference'), str) and
                bool(request['bill_reference'].strip()), 'Billing event receipt mismatch')
        previous = totals.get(batch, 0)
        if kind == 'settlement':
            require(batch not in settlements and request['amount_cents'] >= previous and
                    delta == request['amount_cents'] - previous, 'Invalid cumulative settlement')
            settlements.add(batch)
        else:
            require(delta == request['amount_cents'], 'Incremental charge mismatch')
        totals[batch] = previous + delta
    require(settlements == set(reservations), 'Settled reservation lacks final billing evidence')


def _inspect_real_jobs(db, names, projects):
    if 'real_job_links' not in names:
        return set()
    from services.controller.real_jobs import RealJobBridge
    from workers.gpu.common import LOCK
    rows = db.execute('SELECT batch,owner,project,approval,mode,config_hash FROM real_job_links').fetchall()
    if not rows:
        return set()
    require({'budget_approvals','budget_reservations','budget_events','pod_batches'} <= names,
            'Linked job accounting or lifecycle unavailable')
    linked = set()
    for batch_id, owner, project, approval_id, mode, config_hash in rows:
        require(project in projects and projects[project]['project']['owner_id'] == owner and mode == 'test',
                'Live/unknown linked authority is not restorable')
        batch = next((b for b in projects[project]['batches'] if b['id'] == batch_id), None)
        require(batch and batch['execution_mode'] == 'runpod' and batch['model_profile'] == LOCK['profile'],
                'Linked canonical model profile mismatch')
        approval = db.execute('SELECT owner,project,mode,terms FROM budget_approvals WHERE id=?', (approval_id,)).fetchone()
        require(approval and tuple(approval[:3]) == (owner, project, 'simulation'), 'Linked approval ownership mismatch')
        terms = json.loads(approval[3])
        require(RealJobBridge.configuration_hash(terms['profile']) == config_hash and
                batch['budget']['approved_cents'] == terms['approved_cents'], 'Linked approval configuration changed')
        reservation = db.execute('SELECT owner,project,approval,state FROM budget_reservations WHERE batch=?', (batch_id,)).fetchone()
        require(reservation and tuple(reservation[:3]) == (owner, project, approval_id) and reservation[3] == 'settled',
                'Linked job retains unsettled monetary liability')
        spent = db.execute('SELECT COALESCE(SUM(amount_cents),0) FROM budget_events WHERE batch=?', (batch_id,)).fetchone()[0]
        require(batch['budget']['spent_cents'] == spent and batch['budget']['reserved_cents'] == 0,
                'Canonical budget is not reconciled with settled accounting')
        pod = db.execute('SELECT project,state,cleanup,pod_id,snapshot FROM pod_batches WHERE id=?', (batch_id,)).fetchone()
        require(pod and tuple(pod[:4]) == (project, batch['state'], batch['cleanup_state'], batch['provider_resource_id']),
                'Canonical lifecycle state is not reconciled')
        frozen = json.loads(pod[4])
        require(frozen.get('mode') == 'test' and frozen.get('config_hash') == config_hash and
                all(frozen['canonical_batch'][key] == batch[key] for key in
                    ('id','project_id','idempotency_key','execution_mode','model_profile','shot_snapshots','approved_at','deadline_at')),
                'Immutable linked snapshot mismatch')
        linked.add(batch_id)
    return linked


def _inspect_live_admission(db, names, projects):
    """Preserve closed live history, including unpaid liabilities; keys stay external."""
    tables = {'live_approvals','live_reservations','live_job_links'}
    if not names & tables:
        require(not names & {'live_billing_events','live_execution_bindings','live_recovery_caps'}, 'Orphan live execution schema')
        return set()
    require(tables <= names, 'Incomplete live admission schema')
    from services.controller.live_admission import GRANT_FIELDS, configuration_hash
    from services.controller.real_jobs import RealJobBridge
    from services.controller.runpod import validate_launch_profile
    from workers.gpu.common import LOCK
    approvals = {}
    def hex_hash(value):
        return isinstance(value, str) and len(value) == 64 and all(c in '0123456789abcdef' for c in value)
    for identity, owner, project, raw, revoked in db.execute('SELECT id,owner,project,envelope,revoked FROM live_approvals'):
        require(project in projects and projects[project]['project']['owner_id'] == owner and revoked in (0,1),
                'Live approval ownership mismatch')
        envelope = json.loads(raw)
        require(isinstance(envelope, dict) and set(envelope) == {'key_id','payload','signature'} and
                isinstance(envelope['key_id'], str) and bool(envelope['key_id']) and hex_hash(envelope['signature']),
                'Malformed signed approval history')
        grant = envelope['payload']
        from services.controller.live_admission import GRANT_SHAPES
        require(isinstance(grant, dict) and set(grant) in GRANT_SHAPES and
                (grant['id'],grant['owner'],grant['project']) == (identity,owner,project) and grant['currency'] == 'USD' and
                type(grant['approved_cents']) is int and 0 < grant['approved_cents'] <= 2**53-1 and
                type(grant['max_runtime_seconds']) is int and 1 <= grant['max_runtime_seconds'] <= (14400 if 'continuous_queue' in grant else 3600),
                'Invalid live approval terms')
        if 'capacity_retry' in grant:
            from services.controller.allocation_retry import validate_policy
            validate_policy(grant['capacity_retry'])
        timestamp(grant['valid_until'])
        require(isinstance(grant['source_sha256'], dict) and bool(grant['source_sha256']) and
                all(isinstance(k,str) and hex_hash(v) for k,v in grant['source_sha256'].items()), 'Invalid signed source inventory')
        config_hash = configuration_hash(grant['profile'], grant['launch_profile'], grant.get('allocation_plan'), grant.get('duration_comparison'), grant.get('continuous_queue'))
        launch = validate_launch_profile(grant['launch_profile'])
        require(launch['env'] == {} and launch['image'] == grant['profile']['image_ref'] and
                launch['gpu']['id'] == grant['profile']['gpu_type'] and launch['gpu']['count'] == 1 and
                launch['dataCenterIds'][0] == grant['profile']['region'], 'Live launch configuration mismatch')
        approvals[identity] = (owner, project, grant, config_hash)
    seen = set()
    for batch_id, owner, project, approval, raw, reserved, state in db.execute(
            'SELECT batch,owner,project,approval,request,reserved_cents,state FROM live_reservations'):
        require(approval in approvals and approvals[approval][:2] == (owner,project) and state in ('reserved','released','settled') and
                type(reserved) is int and 0 < reserved <= approvals[approval][2]['approved_cents'],
                'Live reservation is unresolved or has invalid ownership')
        request = json.loads(raw)
        require(isinstance(request, dict) and request.get('approval_id') == approval and request.get('reservation_cents') == reserved,
                'Live reservation receipt mismatch')
        require('pod_batches' in names, 'Live lifecycle missing')
        pod = db.execute('SELECT project,state,cleanup,pod_id,snapshot FROM pod_batches WHERE id=?',(batch_id,)).fetchone()
        require(pod and pod[0] == project and pod[1] in ('succeeded','failed','canceled') and pod[2] == 'confirmed',
                'Live resource cleanup is unresolved')
        link = db.execute('SELECT owner,project,approval,config_hash,dispatch_state FROM live_job_links WHERE batch=?',(batch_id,)).fetchone()
        require(link and tuple(link[:4]) == (owner,project,approval,approvals[approval][3]) and link[4] in ('disabled','attempted'),
                'Live authority link mismatch')
        events = (db.execute('SELECT id,owner,project,kind,amount_cents,envelope FROM live_billing_events WHERE batch=? ORDER BY rowid',
                            (batch_id,)).fetchall() if 'live_billing_events' in names else [])
        spent, settlements = 0, 0
        for event_id, event_owner, event_project, kind, delta, raw_event in events:
            envelope = json.loads(raw_event)
            require(isinstance(envelope, dict) and set(envelope) == {'key_id','payload','signature'} and
                    isinstance(envelope['key_id'], str) and hex_hash(envelope['signature']), 'Invalid billing envelope')
            receipt = envelope['payload']
            require(isinstance(receipt, dict) and set(receipt) == {'id','owner','project','batch','kind','amount_cents','bill_reference','valid_until','provider_resource_id','currency'} and
                    (event_owner,event_project) == (owner,project) and
                    (receipt['id'],receipt['owner'],receipt['project'],receipt['batch'],receipt['kind'],receipt['provider_resource_id'],receipt['currency']) ==
                    (event_id,owner,project,batch_id,kind,pod[3],'USD') and kind in ('charge','settlement') and
                    type(delta) is int and delta >= 0 and type(receipt['amount_cents']) is int and
                    0 <= receipt['amount_cents'] <= 2**53-1 and isinstance(receipt['bill_reference'], str) and bool(receipt['bill_reference']),
                    'Billing receipt scope or amount mismatch')
            timestamp(receipt['valid_until'])
            if kind == 'settlement':
                require(settlements == 0 and receipt['amount_cents'] >= spent and delta == receipt['amount_cents']-spent,
                        'Invalid cumulative live settlement')
                settlements += 1
            else:
                require(pod[3] is not None and delta == receipt['amount_cents'], 'Invalid live charge')
            spent += delta
        require((state == 'released' and not events) or (state == 'settled' and settlements == 1) or
                (state == 'reserved' and settlements == 0 and link[4] == 'attempted'),
                'Live released/settled history lacks matching final evidence')
        batch = next((b for b in projects[project]['batches'] if b['id'] == batch_id),None)
        require(batch and batch['execution_mode'] == 'runpod' and batch['model_profile'] == approvals[approval][2]['profile']['model_profile'] and
                (batch['state'],batch['cleanup_state'],batch['provider_resource_id']) == tuple(pod[1:4]) and
                batch['budget'] == dict(currency='USD',approved_cents=approvals[approval][2]['approved_cents'],
                                       reserved_cents=max(0,reserved-spent) if state == 'reserved' else 0,spent_cents=spent),
                'Closed live canonical record mismatch')
        binding = (db.execute('SELECT credential,host_envelope FROM live_execution_bindings WHERE batch=?',(batch_id,)).fetchone()
                   if 'live_execution_bindings' in names else None)
        if link[4] == 'disabled':
            require(pod[3] is None and pod[1] == 'canceled' and spent == 0 and binding is None and
                    not any(a['batch_id'] == batch_id for a in projects[project]['attempts']), 'Undispatched history contains execution evidence')
        else:
            require(state in ('reserved','settled') and binding and 'worker_credentials' in names,
                    'Dispatched live history has no retained liability or execution binding')
            credential = db.execute('SELECT owner,project,batch FROM worker_credentials WHERE id=?',(binding[0],)).fetchone()
            require(credential and tuple(credential) == (owner,project,batch_id), 'Execution credential scope mismatch')
            host = json.loads(binding[1])
            require(isinstance(host,dict) and set(host) == {'key_id','payload','signature'} and hex_hash(host['signature']) and
                    isinstance(host['key_id'],str) and bool(host['key_id']) and isinstance(host['payload'],dict) and
                    set(host['payload']) == {'owner','project','config_hash','source_sha256','build_manifest_sha256','valid_until','worker_endpoint','storage_id'} and
                    host['payload']['source_sha256'] == approvals[approval][2]['source_sha256'] and
                    hex_hash(host['payload']['build_manifest_sha256']) and
                    host['payload']['worker_endpoint'] == approvals[approval][2]['profile']['worker_endpoint'] and
                    host['payload']['storage_id'] == approvals[approval][2]['profile']['storage_id'] and
                    host['payload'].get('owner') == owner and
                    host['payload'].get('project') == project and host['payload'].get('config_hash') == approvals[approval][3],
                    'Execution host binding mismatch')
            timestamp(host['payload']['valid_until'])
        if binding and 'allocation_attempts' in {r[1] for r in db.execute('PRAGMA table_info(live_execution_bindings)')}:
            from services.controller.allocation_retry import capacity_rejected
            history = json.loads(db.execute('SELECT allocation_attempts FROM live_execution_bindings WHERE batch=?',(batch_id,)).fetchone()[0])
            policy = approvals[approval][2].get('capacity_retry')
            require(isinstance(history,list) and len(history) <= (policy['max_attempts'] if policy else 0),
                    'Allocation history exceeds signed policy')
            for index,event in enumerate(history):
                plan = approvals[approval][2].get('allocation_plan')
                fields = {'attempt','started_at'} | ({'candidate'} if plan else set())
                require(isinstance(event,dict) and type(event.get('attempt')) is int and event['attempt'] == index+1 and
                        set(event) in (fields, fields | {'result','finished_at'}),
                        'Invalid allocation audit event')
                if plan:
                    require(type(event['candidate']) is int and 0 <= event['candidate'] < len(plan['candidates']) and
                            event['candidate'] not in {h['candidate'] for h in history[:index]},
                            'Invalid or repeated allocation candidate')
                timestamp(event['started_at'])
                if 'result' in event:
                    require(isinstance(event['result'],dict), 'Invalid allocation result')
                    timestamp(event['finished_at'])
                require(index == len(history)-1 or capacity_rejected(event.get('result',{})),
                        'Allocation retry followed an uncertain or allocated outcome')
        frozen = json.loads(pod[4])
        require(frozen.get('mode') == 'live_pending' and frozen.get('config_hash') == approvals[approval][3] and
                all(frozen['canonical_batch'][k] == batch[k] for k in
                    ('id','project_id','idempotency_key','execution_mode','model_profile','shot_snapshots','approved_at','deadline_at')),
                'Live immutable snapshot mismatch')
        seen.add(batch_id)
    require(seen == {row[0] for row in db.execute('SELECT batch FROM live_job_links')}, 'Unmatched live authority link')
    for table in ('live_billing_events','live_execution_bindings','live_recovery_caps'):
        if table in names:
            require({row[0] for row in db.execute('SELECT batch FROM '+table)} <= seen, 'Orphan live execution history')
    if 'live_recovery_caps' in names:
        for parent,approval,retained,created in db.execute('SELECT * FROM live_recovery_caps'):
            require(approval in approvals, 'Recovery approval missing')
            terms=approvals[approval][2].get('production_recovery')
            parent_scope=db.execute('SELECT owner,project FROM live_job_links WHERE batch=?',(parent,)).fetchone()
            require(isinstance(terms,dict) and terms.get('parent_batch')==parent and
                    parent_scope and tuple(parent_scope)==approvals[approval][:2] and
                    type(retained) is int and 0<retained<1800 and terms.get('retained_cents')==retained,
                    'Recovery liability does not match signed history')
            timestamp(created)
    return seen


def _inspect_longcat(db,names,projects,assets,asset_root):
    tables={'longcat_budgets','longcat_scopes','longcat_shots','longcat_cleanup'}
    if not names & tables:return
    require(tables<=names,'Incomplete LongCat recovery schema')
    from services.controller.longcat import pod_name
    from workers.gpu.longcat_batch import fingerprint
    budgets={};reserved={};scopes={}
    for identity,owner,raw in db.execute('SELECT id,owner,terms FROM longcat_budgets'):
        terms=json.loads(raw)
        require(set(terms)=={'budget_total_cents','prior_committed_cents','storage_reserve_cents'} and
                all(type(v) is int and v>=0 for v in terms.values()) and
                0<terms['budget_total_cents']<=2000 and terms['storage_reserve_cents']>0,'Invalid retained LongCat budget')
        budgets[identity]=(owner,terms);reserved[identity]=0
    for scope,owner,project,batch,budget,held,raw,host_raw,manifest_raw,token,revoked in db.execute('SELECT * FROM longcat_scopes'):
        require(project in projects and projects[project]['project']['owner_id']==owner and
                budget in budgets and budgets[budget][0]==owner,'Orphan LongCat ownership/budget')
        grant=json.loads(raw)['payload'];host=json.loads(host_raw)['payload'];manifest=json.loads(manifest_raw)
        execution=grant['execution'];binding=fingerprint(manifest)
        require(grant['owner']==owner and grant['project']==project and grant['budget_id']==budget and
                execution['scope_id']==scope and execution['manifest_sha256']==binding and
                manifest['project_id']==project and manifest['batch_id']==batch and
                all(grant[k]==v for k,v in budgets[budget][1].items()) and
                type(held) is int and held==execution['compute_cap_cents'] and 0<held<=1171 and
                isinstance(token,str) and len(token)==64 and all(c in '0123456789abcdef' for c in token),
                'LongCat scope binding changed')
        require(host['grant_sha256']==fingerprint(grant) and host['pod_name']==pod_name(scope),
                'LongCat host binding changed')
        cleanup=db.execute('SELECT envelope FROM longcat_cleanup WHERE scope=?',(scope,)).fetchone()
        require(cleanup is not None and revoked==1,'Provider absence must be attested before LongCat backup')
        proof=json.loads(cleanup[0])['payload']
        require(proof==dict(owner=owner,scope_id=scope,grant_sha256=fingerprint(grant),
                guard_run_id=execution['guard_run_id'],pod_name=pod_name(scope),absence_confirmed=True,
                confirmed_at=proof.get('confirmed_at')) and type(proof['confirmed_at']) is int and
                proof['confirmed_at']>=execution['admitted_at'],'Invalid LongCat cleanup history')
        reserved[budget]+=held;scopes[scope]=(manifest,binding,project,batch)
        require(asset_root is not None,'LongCat backup requires its immutable media root')
        for shot in manifest['shots']:
            for kind in ('image','audio'):
                value=shot[kind];key=_key(f"longcat/{project}/{batch}/inputs/{_key(value['path'])}")
                path=_file(Path(asset_root)/key,hardlinks=True)
                record=dict(bytes=path.stat().st_size,sha256=value['sha256'])
                require(key not in assets or assets[key]==record,'Conflicting LongCat input')
                assets[key]=record
    for scope,shot_id,state,raw in db.execute('SELECT scope,shot,state,receipt FROM longcat_shots'):
        require(scope in scopes,'Orphan LongCat shot');manifest,binding,project,batch=scopes[scope]
        require(any(s['id']==shot_id for s in manifest['shots']) and state in ('rendering','published'),
                'Invalid LongCat shot state')
        if state=='rendering':require(raw is None,'Uncommitted LongCat receipt');continue
        receipt=json.loads(raw);key=_key(receipt['object_key'])
        require(receipt['shot_id']==shot_id and receipt['scope_id']==scope and receipt['binding']==binding and
                key==f"longcat/{project}/{batch}/takes/{shot_id}-{receipt['sha256']}.mp4" and
                type(receipt['bytes']) is int and receipt['bytes']>0,'LongCat receipt binding changed')
        record=dict(bytes=receipt['bytes'],sha256=receipt['sha256'])
        require(key not in assets or assets[key]==record,'Conflicting LongCat take');assets[key]=record
    require({r[0] for r in db.execute('SELECT scope FROM longcat_cleanup')}==set(scopes),
            'Orphan LongCat cleanup history')
    for identity,(_,terms) in budgets.items():
        require(reserved[identity]+terms['prior_committed_cents']+terms['storage_reserve_cents']<=terms['budget_total_cents'],
                'Retained LongCat budget exceeded')


def _inspect(db,asset_root=None):
    require(db.execute('PRAGMA integrity_check').fetchall() == [('ok',)], 'Database integrity check failed')
    require(not db.execute('PRAGMA foreign_key_check').fetchall(), 'Database foreign key check failed')
    names = _tables(db)
    assets = {}
    projects = {}

    def collect(bundle):
        validate_bundle(bundle)
        for batch in bundle['batches']:
            require(batch['execution_mode'] == 'fixture' or (batch['state'] in ('succeeded','failed','canceled') and
                    batch['cleanup_state'] == 'confirmed'), 'Outstanding or uncertain paid resources cannot be restored safely')
        for asset in bundle['assets']:
            key = _key(asset['object_key'])
            prior = assets.get(key)
            require(prior is None or (prior['bytes'], prior['sha256']) == (asset['bytes'],asset['sha256']),
                    'Conflicting immutable asset references')
            assets[key] = asset

    for project_id, owner, raw in db.execute('SELECT id,owner,bundle FROM projects'):
        bundle = json.loads(raw)
        require(bundle['project']['id'] == project_id and bundle['project']['owner_id'] == owner, 'Project row identity mismatch')
        collect(bundle)
        projects[project_id] = bundle
    if 'pod_batches' in names:
        require(db.execute("SELECT count(*) FROM pod_batches WHERE cleanup!='confirmed'").fetchone()[0] == 0,
                'Provider cleanup must be confirmed before backup')
    if 'export_jobs' in names:
        for job_id, project_id, owner, raw, state in db.execute('SELECT id,project,owner,snapshot,state FROM export_jobs'):
            require(project_id in projects and projects[project_id]['project']['owner_id'] == owner, 'Export job owner mismatch')
            frozen = json.loads(raw)
            require(frozen['project']['id'] == project_id and frozen['project']['owner_id'] == owner, 'Export snapshot identity mismatch')
            collect(frozen)  # Include snapshot-only assets, independent of canonical refs.
            source = next((j for j in frozen['exports'] if j['id'] == job_id), None)
            current = next((j for j in projects[project_id]['exports'] if j['id'] == job_id), None)
            require(source is not None and current is not None and state == current['state'] and
                    all(source[k] == current[k] for k in ('id','project_id','timeline_id','timeline_revision','profile')),
                    'Export job state or frozen identity mismatch')
    if 'studio_projects' in names:
        for project_id, raw in db.execute('SELECT project,metadata FROM studio_projects'):
            require(project_id in projects, 'Studio project unavailable')
            value = json.loads(raw)
            require(isinstance(value.get('script'), str) and isinstance(value.get('scenes'), list) and
                    isinstance(value.get('shotHistory'), list) and isinstance(value.get('assetNames'), dict) and
                    isinstance(value.get('selectedTakes'), dict), 'Invalid Studio metadata')
    if 'upload_sessions' in names:
        for owner, project_id, state, asset_id in db.execute('SELECT owner,project,state,asset FROM upload_sessions'):
            require(project_id in projects and projects[project_id]['project']['owner_id'] == owner and
                    state in ('uploading','completed','expired','aborted'), 'Invalid upload session')
            if state == 'completed':
                require(any(a['id'] == asset_id for a in projects[project_id]['assets']), 'Completed upload asset unavailable')
    linked_test_jobs = _inspect_real_jobs(db, names, projects)
    linked_live_jobs = _inspect_live_admission(db, names, projects)
    if 'worker_credentials' in names:
        for token_hash, owner, project_id, batch_id, worker, expires, revoked in db.execute(
                'SELECT token_hash,owner,project,batch,worker,expires,revoked FROM worker_credentials'):
            require(project_id in projects and projects[project_id]['project']['owner_id'] == owner,
                    'Worker credential owner mismatch')
            batch = next((b for b in projects[project_id]['batches'] if b['id'] == batch_id), None)
            require(batch and ((batch['execution_mode'] == 'fixture' and
                    all(batch['budget'][key] == 0 for key in ('approved_cents','reserved_cents','spent_cents'))) or
                    batch_id in linked_test_jobs or batch_id in linked_live_jobs), 'Worker credential batch has no valid authority binding')
            require(isinstance(token_hash, str) and len(token_hash) == 64 and
                    all(c in '0123456789abcdef' for c in token_hash) and
                    isinstance(worker, str) and bool(worker) and revoked in (0, 1),
                    'Invalid worker credential')
            timestamp(expires)
    from services.controller import comparison
    from workers.gpu.comparison import validate_metrics, receipt
    if 'worker_telemetry' in names:
        for attempt_id,batch_id,project_id,raw,checksum in db.execute('SELECT attempt,batch,project,payload,receipt FROM worker_telemetry'):
            require(project_id in projects, 'Orphan telemetry project')
            bundle=projects[project_id]
            batch=next((b for b in bundle['batches'] if b['id']==batch_id),None)
            attempt=next((a for a in bundle['attempts'] if a['id']==attempt_id and a['batch_id']==batch_id),None)
            require(batch is not None and attempt is not None, 'Orphan telemetry attempt')
            experiment=comparison.experiment(db,batch)
            require(experiment is not None, 'Telemetry lacks approved experiment')
            snapshot=next(s for s in batch['shot_snapshots'] if s['shot_id']==attempt['shot_id'])
            metrics=json.loads(raw)
            validate_metrics(metrics,experiment,attempt,snapshot)
            require(receipt(metrics)==checksum, 'Telemetry checksum changed')
            take=next((t for t in bundle['takes'] if t['attempt_id']==attempt_id),None)
            if take:
                asset=next(a for a in bundle['assets'] if a['id']==take['asset_id'])
                comparison.require_metrics(db,batch,attempt,asset)
    if 'comparison_gates' in names:
        known={b['id'] for p in projects.values() for b in p['batches']}
        require({r[0] for r in db.execute('SELECT batch FROM comparison_gates')}<=known, 'Orphan comparison gate')
    _inspect_budget(db, names, projects)
    _inspect_longcat(db,names,projects,assets,asset_root)
    return assets


def _normalize(db, now):
    counts = dict(uploads_aborted=0, attempts_fenced=0, worker_credentials_revoked=0, live_approvals_revoked=0)
    names = _tables(db)
    if 'live_approvals' in names:
        counts['live_approvals_revoked'] = db.execute('UPDATE live_approvals SET revoked=1 WHERE revoked=0').rowcount
    if 'upload_sessions' in names:
        counts['uploads_aborted'] = db.execute("UPDATE upload_sessions SET state='aborted' WHERE state='uploading'").rowcount
    if 'worker_credentials' in names:
        counts['worker_credentials_revoked'] = db.execute('UPDATE worker_credentials SET revoked=1 WHERE revoked=0').rowcount
    for project_id, raw in db.execute('SELECT id,bundle FROM projects').fetchall():
        bundle = json.loads(raw)
        changed = False
        for attempt in bundle['attempts']:
            if attempt['state'] in ('claimed','running'):
                completed = max(timestamp(now), timestamp(attempt['started_at'])).isoformat().replace('+00:00', 'Z')
                attempt.update(state='failed', failure_reason='backup_interrupted', completed_at=completed)
                counts['attempts_fenced'] += 1
                changed = True
        if changed:
            validate_bundle(bundle)
            db.execute('UPDATE projects SET bundle=? WHERE id=?', (canonical(bundle), project_id))
    return counts


def _copy(source, destination, size, checksum, *, hardlinks=False):
    source = _file(source, hardlinks=hardlinks)
    require(type(size) is int and size >= 0 and source.stat().st_size == size, 'Backup file size mismatch')
    destination.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
    hasher = hashlib.sha256()
    written = 0
    with source.open('rb') as incoming, destination.open('xb') as output:
        while chunk := incoming.read(65536):
            written += len(chunk)
            require(written <= size, 'Source file changed while copying')
            hasher.update(chunk)
            output.write(chunk)
        output.flush()
        os.fsync(output.fileno())
    require(written == size and hasher.hexdigest() == checksum, 'Backup checksum mismatch')
    sync_dir(destination.parent)


def _write(path, data):
    with path.open('xb') as output:
        output.write(data)
        output.flush()
        os.fsync(output.fileno())
    sync_dir(path.parent)


def _sync_directories(directory):
    directories = [Path(parent) for parent, _, _ in os.walk(directory)]
    for path in reversed(directories):
        sync_dir(path)


def _finish_marker(directory, manifest_bytes):
    _sync_directories(directory)
    temporary = directory / 'COMPLETE.tmp'
    _write(temporary, (hashlib.sha256(manifest_bytes).hexdigest() + '\n').encode())
    os.replace(temporary, directory / 'COMPLETE')
    sync_dir(directory)


def create_backup(database, asset_root, destination):
    """Copy a consistent DB snapshot and its immutable committed media refs.

    Only the backup copy is normalized: active uploads abort, active attempts are
    fenced. Queued/rendering export jobs retain their captured inputs for restart.
    """
    database = _file(database, hardlinks=True)
    asset_root = _plain_path(asset_root)
    require(asset_root.is_dir(), 'Asset root unavailable')
    destination_path = _plain_path(destination)
    require(not destination_path.is_relative_to(asset_root) and not database.is_relative_to(destination_path),
            'Backup destination must be separate from active data')
    output = _destination(destination_path)
    snapshot = output / DB_NAME
    with _connect(database, readonly=True) as source:
        # Pin the snapshot before backup; writers may continue publishing new media.
        source.execute('BEGIN')
        source.execute('SELECT count(*) FROM sqlite_master').fetchone()
        target = sqlite3.connect(snapshot)
        try:
            source.backup(target, pages=256)
        finally:
            target.close()
        source.rollback()
    now = datetime.now(timezone.utc).isoformat().replace('+00:00', 'Z')
    with _connect(snapshot) as db:
        db.execute('PRAGMA journal_mode=DELETE')
        _inspect(db,asset_root)  # Reject uncertain provider obligations before normalization.
        recovery = _normalize(db, now)
        db.commit()
        assets = _inspect(db,asset_root)
        db.execute('VACUUM')  # Do not retain discarded/free page contents.
    with snapshot.open('rb') as handle:
        os.fsync(handle.fileno())
    files = [dict(path=DB_NAME, bytes=snapshot.stat().st_size, sha256=digest(snapshot))]
    (output / 'assets').mkdir(mode=0o700)
    for key, asset in sorted(assets.items()):
        relative = 'assets/' + key
        _copy(asset_root / key, output / relative, asset['bytes'], asset['sha256'], hardlinks=True)
        files.append(dict(path=relative, bytes=asset['bytes'], sha256=asset['sha256']))
    manifest = dict(version=1, contract_version='0.1.0', created_at=now,
                    recovery=recovery, files=files)
    encoded = (canonical(manifest) + '\n').encode()
    _write(output / 'manifest.json', encoded)
    _finish_marker(output, encoded)
    return manifest


def _verify_backup(directory):
    directory = _plain_path(directory)
    require(directory.is_dir(), 'Backup directory unavailable')
    manifest_path = _file(directory / 'manifest.json')
    require(manifest_path.stat().st_size <= 32 * 1024 * 1024, 'Manifest exceeds bounds')
    raw = manifest_path.read_bytes()
    marker = _file(directory / 'COMPLETE')
    require(marker.stat().st_size == 65 and marker.read_bytes() == (hashlib.sha256(raw).hexdigest() + '\n').encode(),
            'Backup is incomplete or manifest checksum changed')
    manifest = json.loads(raw)
    require(isinstance(manifest, dict) and set(manifest) == {'version','contract_version','created_at','recovery','files'} and
            type(manifest['version']) is int and manifest['version'] == 1 and manifest['contract_version'] == '0.1.0',
            'Unsupported backup manifest')
    require(isinstance(manifest['created_at'], str) and timestamp(manifest['created_at']).tzinfo is not None,
            'Invalid backup timestamp')
    recovery = manifest['recovery']
    require(isinstance(recovery, dict) and set(recovery) in (
                {'uploads_aborted','attempts_fenced'},
                {'uploads_aborted','attempts_fenced','worker_credentials_revoked'},
                {'uploads_aborted','attempts_fenced','worker_credentials_revoked','live_approvals_revoked'}) and
            all(type(v) is int and v >= 0 for v in recovery.values()), 'Invalid recovery summary')
    require(isinstance(manifest['files'], list) and 0 < len(manifest['files']) <= 100000, 'Invalid file inventory')
    entries = {}
    for entry in manifest['files']:
        require(isinstance(entry, dict) and set(entry) == {'path','bytes','sha256'}, 'Invalid file entry')
        key = _key(entry['path'])
        require(key == DB_NAME or key.startswith('assets/'), 'Unexpected backup path')
        require(key not in entries and type(entry['bytes']) is int and entry['bytes'] >= 0 and
                isinstance(entry['sha256'], str) and len(entry['sha256']) == 64 and
                all(c in '0123456789abcdef' for c in entry['sha256']), 'Invalid file metadata')
        file = _file(directory / key)
        require(file.stat().st_size == entry['bytes'] and digest(file) == entry['sha256'], 'Backup file checksum mismatch')
        entries[key] = entry
    require(DB_NAME in entries, 'Database missing from backup')
    actual = set()
    for parent, dirs, names in os.walk(directory, followlinks=False):
        for name in dirs + names:
            require(not (Path(parent) / name).is_symlink(), 'Backup contains symlink')
        actual.update(str((Path(parent) / name).relative_to(directory)) for name in names)
    require(actual == set(entries) | {'manifest.json','COMPLETE'}, 'Unlisted backup files')
    with _connect(directory / DB_NAME, readonly=True) as db:
        assets = _inspect(db,directory/'assets')
        if 'live_approvals' in _tables(db):
            require(db.execute('SELECT count(*) FROM live_approvals WHERE revoked!=1').fetchone()[0] == 0,
                    'Backup live approvals must be revoked before restore')
        if 'worker_credentials' in _tables(db):
            require(db.execute('SELECT count(*) FROM worker_credentials WHERE revoked!=1').fetchone()[0] == 0,
                    'Backup worker credentials must be revoked before restore')
    require(set(entries) == {DB_NAME} | {'assets/' + key for key in assets}, 'Manifest does not match database references')
    for key, asset in assets.items():
        entry = entries['assets/' + key]
        require((entry['bytes'],entry['sha256']) == (asset['bytes'],asset['sha256']), 'Asset record checksum mismatch')
    return manifest


def restore_backup(backup_dir, destination):
    """Validate then restore into a NEW/empty directory; never overwrite live data."""
    source = _plain_path(backup_dir)
    target_path = _plain_path(destination)
    require(not target_path.is_relative_to(source) and not source.is_relative_to(target_path), 'Restore destination overlaps backup')
    manifest = _verify_backup(source)
    target = _destination(target_path)
    (target / 'assets').mkdir(mode=0o700)
    for entry in manifest['files']:
        _copy(source / entry['path'], target / entry['path'], entry['bytes'], entry['sha256'])
    with _connect(target / DB_NAME, readonly=True) as db:
        _inspect(db,target/'assets')
    recovery = dict(database=str(target / DB_NAME), assets=str(target / 'assets'),
                    restored_at=datetime.now(timezone.utc).isoformat(), recovery=manifest['recovery'])
    _sync_directories(target)
    _write(target / 'RESTORED.tmp', (canonical(recovery) + '\n').encode())
    os.replace(target / 'RESTORED.tmp', target / 'RESTORED.json')
    sync_dir(target)
    return recovery


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest='command', required=True)
    create = commands.add_parser('create')
    create.add_argument('--database', required=True, type=Path)
    create.add_argument('--assets', required=True, type=Path)
    create.add_argument('--output', required=True, type=Path)
    restore = commands.add_parser('restore')
    restore.add_argument('--backup', required=True, type=Path)
    restore.add_argument('--output', required=True, type=Path)
    args = parser.parse_args()
    if args.command == 'create':
        result = create_backup(args.database, args.assets, args.output)
        print(json.dumps({'complete': True, 'files': len(result['files']), 'recovery': result['recovery']}))
    else:
        print(json.dumps(restore_backup(args.backup, args.output)))


if __name__ == '__main__':
    main()
