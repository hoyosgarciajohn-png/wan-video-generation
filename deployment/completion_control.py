"""Final missing-only handoff; prior execution records remain unchanged."""
import json,math,os,pwd,secrets,shutil,sys,tarfile,time,runpy
from pathlib import Path
from urllib.request import Request,urlopen
SESSION=Path('/root/wan-longcat-session-20261118');sys.path.insert(0,str(SESSION))
import reuse_control as previous
import longcat_session_original as original
from continuation_prepare import rebase_suffix
from workers.gpu.longcat_batch import fingerprint,PROTOCOL
from workers.gpu.common import scoped,digest
from services.controller.longcat import OWNER_DOMAIN,HOST_DOMAIN,CLEANUP_DOMAIN,source_digest,pod_name
ROOT=previous.ROOT;EXT=previous.EXT;FINAL=ROOT/'completion'
SCOPE='john-longcat-world-tour-20261118-completion-v1'
DEADLINE=1794988500

def read(p):return json.loads(Path(p).read_text())

def records(c,directory,scope):
    manifest=read(directory/'inputs/manifest.json');shots={s['id']:s for s in manifest['shots']}
    with c.transaction() as db:rows=db.execute('SELECT shot,state,receipt FROM longcat_shots WHERE scope=?',(scope,)).fetchall()
    journal=dict(binding=fingerprint(manifest),scope_id=scope,deadline=read(directory/'grant.json')['execution']['deadline'],
        recovered_from_authenticated_controller=True,shots={i:dict(status=s,input_sha256=fingerprint(shots[i]),
            **({'receipt':json.loads(r)} if r else {})) for i,s,r in rows})
    return dict(manifest=manifest,journal=journal)

def directories():
    values=[(ROOT,previous.OLD_SCOPE),(EXT,previous.SCOPE)]
    if (FINAL/'credential.json').exists():values.append((FINAL,SCOPE))
    return values

def admit():
    assert not (FINAL/'credential.json').exists(),'Completion already admitted'
    assert time.time()>=1794987625-145,'Current queue has not reached its bounded handoff'
    guard=read(SESSION/'completion-guard-ready.json')
    assert guard['pod_id']==previous.POD and guard['scope_id']==SCOPE and guard['deadline']==DEADLINE
    with urlopen('https://api.github.com/repos/hoyosgarciajohn-png/wan-video-generation/actions/runs/'+guard['run_id'],timeout=20) as r:run=json.load(r)
    assert run['status']=='in_progress' and run['path']=='.github/workflows/longcat-completion-guard.yml' and run['head_sha']==guard['head_sha']
    with urlopen(Request('https://api.runpod.io/v2/pods/'+previous.POD,headers={'Authorization':'Bearer '+Path('/etc/wan/runpod-token').read_text().strip()}),timeout=20) as r:pod=json.load(r)
    assert pod['id']==previous.POD and pod['name']==pod_name(SCOPE)
    FINAL.mkdir(mode=0o700);user=pwd.getpwnam('wan');os.chown(FINAL,user.pw_uid,user.pw_gid)
    original.unprivileged();c,transport=original.runtime();runs=[records(c,d,s) for d,s in directories()]
    full=runs[0]['manifest'];published={}
    for run in runs:
        binding=fingerprint(run['manifest']);shots={s['id']:s for s in run['manifest']['shots']}
        for ident,row in run['journal']['shots'].items():
            assert row['status']=='published' and ident not in published,'Unpublished or duplicate work needs recovery'
            receipt=row['receipt'];assert receipt['binding']==binding and receipt['shot_id']==ident and receipt['scope_id']==run['journal']['scope_id']
            path=scoped(c.asset_root,receipt['object_key']);assert path.stat().st_size==receipt['bytes'] and digest(path)==receipt['sha256']
            published[ident]=receipt
    count=len(published);assert 67<count<110
    assert set(published)=={s['id'] for s in full['shots'][:count]},'Only a contiguous missing suffix may continue'
    from services.controller.studio import StudioWorkspace
    studio=StudioWorkspace(c);before=studio.get(original.OWNER);state=studio.create(original.OWNER,'Busca adentro · final missing footage','music_video',before['revision'])
    old={p['bundle']['project']['id'] for p in before['projects']};project=next(p['bundle']['project']['id'] for p in state['projects'] if p['bundle']['project']['id'] not in old)
    manifest,offset=rebase_suffix(full,full['shots'][count:],project_id=project,batch_id='world-tour-production-completion-20261118-v1')
    inputs=FINAL/'inputs';inputs.mkdir()
    for name in {s[k]['path'] for s in manifest['shots'] for k in ('image','audio')}:
        dst=inputs/name;dst.parent.mkdir(parents=True,exist_ok=True);shutil.copyfile(ROOT/'inputs'/name,dst)
    original.save(inputs/'manifest.json',manifest);original.save(FINAL/'prior-runs.json',runs)
    original.save(FINAL/'provenance.json',dict(source_manifest_sha256=fingerprint(full),source_offset_frames=offset,
        preserve_completed_shots=list(published),render_only_shots=[s['id'] for s in manifest['shots']],original_edits=full['shots'][count:]))
    admitted=int(time.time());cap=math.ceil((DEADLINE-admitted)*878/3600)
    assert 150<DEADLINE-admitted<=1200 and 0<cap<=286,'Final completion budget exceeded'
    execution=dict(protocol=PROTOCOL,admitted_at=admitted,deadline=DEADLINE,gpu_count=2,max_hourly_cents=878,compute_cap_cents=cap,
        scope_id=SCOPE,guard_run_id=guard['run_id'],manifest_sha256=fingerprint(manifest))
    grant=dict(owner=original.OWNER,project=project,execution=execution,image_ref=original.IMAGE,source_sha256=source_digest(),
        budget_id='john-b07-completion-remainder-20261118',budget_total_cents=300,prior_committed_cents=0,storage_reserve_cents=14)
    host=dict(owner=original.OWNER,project=project,grant_sha256=fingerprint(grant),source_sha256=source_digest(),image_ref=original.IMAGE,
        guard_run_id=guard['run_id'],deadline=DEADLINE,pod_name=pod_name(SCOPE),image_import_verified=True,guard_ready=True,storage_verified=True)
    keys={'owner':secrets.token_hex(32),'host':secrets.token_hex(32)};original.exclusive(FINAL/'keys.json',keys)
    result=transport.admit(original.OWNER,manifest,inputs,original.signature(grant,OWNER_DOMAIN,bytes.fromhex(keys['owner'])),
        original.signature(host,HOST_DOMAIN,bytes.fromhex(keys['host'])),approval_keys={'production':(original.OWNER,bytes.fromhex(keys['owner']))},
        host_keys={'production':(original.OWNER,bytes.fromhex(keys['host']))})
    original.save(FINAL/'credential.json',result);original.save(FINAL/'grant.json',grant)
    print(json.dumps(dict(status='FINAL_SUFFIX_ADMITTED',shots=len(manifest['shots']),scope_id=SCOPE,deadline=DEADLINE,compute_cap_cents=cap)))

def dispatch():
    op=os.environ.get('SSH_ORIGINAL_COMMAND','');assert time.time()<read(SESSION/'authority.json')['expires_at']
    if op=='admit':admit();return
    if not (FINAL/'credential.json').exists():previous.dispatch();return
    if op not in {'credential','status','shots','prepare','cleanup'}:
        runpy.run_path(str(SESSION/'longcat_session_original.py'),run_name='__main__');return
    if op=='cleanup':original.host_gate()
    original.unprivileged();c,transport=original.runtime();runs=[records(c,d,s) for d,s in directories()]
    if op=='credential':print(json.dumps(read(FINAL/'credential.json')));return
    if op=='prepare':print(json.dumps(dict(runs=runs,provenance=read(FINAL/'provenance.json'))));return
    if op=='status':
        rows=[dict(id=i,state=r['status']) for run in runs for i,r in run['journal']['shots'].items()]
        print(json.dumps(dict(scope_id=SCOPE,shots=len(rows),published=sum(r['state']=='published' for r in rows),
            states=sorted(rows,key=lambda r:r['id']),deadline=DEADLINE)));return
    if op=='shots':
        with tarfile.open(fileobj=sys.stdout.buffer,mode='w|') as archive:
            for run in runs:
                for ident,row in run['journal']['shots'].items():
                    if row['status']=='published':archive.add(scoped(c.asset_root,row['receipt']['object_key']),arcname=ident+'.mp4',recursive=False)
        return
    results=[]
    for directory,scope in directories():
        grant=read(directory/'grant.json');keys=read(directory/'keys.json')
        proof=dict(owner=original.OWNER,scope_id=scope,grant_sha256=fingerprint(grant),guard_run_id=grant['execution']['guard_run_id'],
            pod_name=pod_name(scope),absence_confirmed=True,confirmed_at=int(time.time()))
        results.append(transport.confirm_cleanup(original.OWNER,scope,original.signature(proof,CLEANUP_DOMAIN,bytes.fromhex(keys['host'])),
            host_keys={'production':(original.OWNER,bytes.fromhex(keys['host']))}))
    print(json.dumps(dict(status='ALL_EXECUTION_SCOPES_CLEANUP_CONFIRMED',results=results)))
