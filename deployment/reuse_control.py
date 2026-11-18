"""Separate signed suffix execution on the owner's already guarded physical Pod."""
import json,math,os,pwd,secrets,shutil,sqlite3,subprocess,sys,tarfile,time,runpy
from pathlib import Path
from urllib.request import Request,urlopen

SESSION=Path('/root/wan-longcat-session-20261118')
ROOT=Path('/var/lib/wan/longcat-production-20261118')
EXT=ROOT/'extension'
SCOPE='john-longcat-world-tour-20261118-extension-v1'
OLD_SCOPE='john-longcat-world-tour-20261118-v1'
POD='gn1lmaun88v7w8'
DEADLINE=1794987625
sys.path.insert(0,str(SESSION))
import longcat_session_original as original
from workers.gpu.longcat_batch import fingerprint,PROTOCOL
from workers.gpu.common import scoped
from services.controller.longcat import OWNER_DOMAIN,HOST_DOMAIN,CLEANUP_DOMAIN,source_digest,pod_name


def read(p):return json.loads(Path(p).read_text())

def journal(c,scope,manifest):
    with c.transaction() as db:
        rows=db.execute('SELECT shot,state,receipt FROM longcat_shots WHERE scope=?',(scope,)).fetchall()
    shots={s['id']:s for s in manifest['shots']}
    return dict(binding=fingerprint(manifest),scope_id=scope,deadline=read((EXT if scope==SCOPE else ROOT)/'grant.json')['execution']['deadline'],
        recovered_from_authenticated_controller=True,shots={ident:dict(status=state,input_sha256=fingerprint(shots[ident]),
            **({'receipt':json.loads(receipt)} if receipt else {})) for ident,state,receipt in rows})


def install():
    from continuation_prepare import prepare_missing_suffix
    assert not (EXT/'credential.json').exists(),'Extension already admitted'
    guard=read(SESSION/'extension-guard-ready.json')
    assert guard['pod_id']==POD and guard['scope_id']==SCOPE and guard['deadline']==DEADLINE
    with urlopen('https://api.github.com/repos/hoyosgarciajohn-png/wan-video-generation/actions/runs/'+guard['run_id'],timeout=20) as r:run=json.load(r)
    assert run['status']=='in_progress' and run['path']=='.github/workflows/longcat-reuse-guard.yml'
    assert run['head_sha']==guard['head_sha'] and guard['status']=='READY'
    assert subprocess.check_output(['git','-C','/opt/wan/current','rev-parse','HEAD'],text=True).strip()==original.RELEASE
    with urlopen(Request('https://api.runpod.io/v2/pods/'+POD,headers={'Authorization':'Bearer '+Path('/etc/wan/runpod-token').read_text().strip()}),timeout=20) as r:pod=json.load(r)
    assert pod['id']==POD and pod['name']==pod_name(SCOPE),'Existing guarded Pod identity changed'
    EXT.mkdir(mode=0o700);user=pwd.getpwnam('wan');os.chown(EXT,user.pw_uid,user.pw_gid)
    original.unprivileged();c,transport=original.runtime();full=read(ROOT/'inputs/manifest.json')
    before_journal=journal(c,OLD_SCOPE,full)
    assert len(before_journal['shots'])==67 and all(r['status']=='published' for r in before_journal['shots'].values()),'Original queue must be durable and stopped'
    from services.controller.studio import StudioWorkspace
    studio=StudioWorkspace(c);before=studio.get(original.OWNER);state=studio.create(original.OWNER,'Busca adentro · remaining 43 shots · same GPU','music_video',before['revision'])
    old={p['bundle']['project']['id'] for p in before['projects']};project=next(p['bundle']['project']['id'] for p in state['projects'] if p['bundle']['project']['id'] not in old)
    manifest,proof=prepare_missing_suffix(full,before_journal,project_id=project,batch_id='world-tour-production-extension-20261118-v1')
    inputs=EXT/'inputs';inputs.mkdir()
    for name in {s[k]['path'] for s in manifest['shots'] for k in ('image','audio')}:
        dst=inputs/name;dst.parent.mkdir(parents=True,exist_ok=True);shutil.copyfile(ROOT/'inputs'/name,dst)
    original.save(inputs/'manifest.json',manifest);original.save(EXT/'original-journal.json',before_journal);original.save(EXT/'provenance.json',proof)
    admitted=int(time.time());cap=math.ceil((DEADLINE-admitted)*878/3600)
    assert 90<DEADLINE-admitted<=2400 and 0<cap<=586,'Authorized extension bound exceeded'
    execution=dict(protocol=PROTOCOL,admitted_at=admitted,deadline=DEADLINE,gpu_count=2,max_hourly_cents=878,
        compute_cap_cents=cap,scope_id=SCOPE,guard_run_id=guard['run_id'],manifest_sha256=fingerprint(manifest))
    grant=dict(owner=original.OWNER,project=project,execution=execution,image_ref=original.IMAGE,source_sha256=source_digest(),
        budget_id='john-b07-owner-extension-20261118',budget_total_cents=600,prior_committed_cents=0,storage_reserve_cents=14)
    host=dict(owner=original.OWNER,project=project,grant_sha256=fingerprint(grant),source_sha256=source_digest(),
        image_ref=original.IMAGE,guard_run_id=guard['run_id'],deadline=DEADLINE,pod_name=pod_name(SCOPE),
        image_import_verified=True,guard_ready=True,storage_verified=True)
    keys={'owner':secrets.token_hex(32),'host':secrets.token_hex(32)};original.exclusive(EXT/'keys.json',keys)
    result=transport.admit(original.OWNER,manifest,inputs,
        original.signature(grant,OWNER_DOMAIN,bytes.fromhex(keys['owner'])),original.signature(host,HOST_DOMAIN,bytes.fromhex(keys['host'])),
        approval_keys={'production':(original.OWNER,bytes.fromhex(keys['owner']))},host_keys={'production':(original.OWNER,bytes.fromhex(keys['host']))})
    original.save(EXT/'credential.json',result);original.save(EXT/'grant.json',grant)
    original.save(EXT/'reuse-authorization.json',dict(physical_pod_id=POD,original_scope=OLD_SCOPE,extension_scope=SCOPE,
        old_deadline=1794985375,new_deadline=DEADLINE,new_allowance_cents=600,owner_direction='Extend runtime now to finish all shots without a new cold start',
        no_new_pod_create=True,old_records_unchanged=True))
    print(json.dumps(dict(status='SEPARATE_EXTENSION_ADMITTED',shots=len(manifest['shots']),deadline=DEADLINE,compute_cap_cents=cap,scope_id=SCOPE)))


def dispatch():
    op=os.environ.get('SSH_ORIGINAL_COMMAND','')
    assert time.time()<read(SESSION/'authority.json')['expires_at']
    if op not in {'credential','status','shots','prepare','cleanup'}:
        runpy.run_path(str(SESSION/'longcat_session_original.py'),run_name='__main__');return
    if op=='cleanup':original.host_gate()
    original.unprivileged();c,transport=original.runtime()
    full=read(ROOT/'inputs/manifest.json');suffix=read(EXT/'inputs/manifest.json')
    runs=[dict(manifest=full,journal=journal(c,OLD_SCOPE,full)),dict(manifest=suffix,journal=journal(c,SCOPE,suffix))]
    if op=='credential':print(json.dumps(read(EXT/'credential.json')));return
    if op=='prepare':print(json.dumps(dict(runs=runs,provenance=read(EXT/'provenance.json'))));return
    if op=='status':
        rows=[dict(id=k,state=v['status']) for run in runs for k,v in run['journal']['shots'].items()]
        print(json.dumps(dict(scope_id=SCOPE,shots=len(rows),published=sum(r['state']=='published' for r in rows),
            states=sorted(rows,key=lambda r:r['id']),deadline=DEADLINE,original_published=67)));return
    if op=='shots':
        with tarfile.open(fileobj=sys.stdout.buffer,mode='w|') as archive:
            for run in runs:
                for ident,row in run['journal']['shots'].items():
                    if row['status']=='published':archive.add(scoped(c.asset_root,row['receipt']['object_key']),arcname=ident+'.mp4',recursive=False)
        return
    results=[]
    for directory,scope in ((ROOT,OLD_SCOPE),(EXT,SCOPE)):
        grant=read(directory/'grant.json');keys=read(directory/'keys.json')
        proof=dict(owner=original.OWNER,scope_id=scope,grant_sha256=fingerprint(grant),guard_run_id=grant['execution']['guard_run_id'],
            pod_name=pod_name(scope),absence_confirmed=True,confirmed_at=int(time.time()))
        results.append(transport.confirm_cleanup(original.OWNER,scope,original.signature(proof,CLEANUP_DOMAIN,bytes.fromhex(keys['host'])),
            host_keys={'production':(original.OWNER,bytes.fromhex(keys['host']))}))
    print(json.dumps(dict(status='BOTH_SCOPES_CLEANUP_CONFIRMED',results=results)))

if __name__=='__main__':install()
