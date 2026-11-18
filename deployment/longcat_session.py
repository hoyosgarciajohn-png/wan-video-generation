"""One expiring, narrowly scoped operator session for the approved full song.

No shell, provider creation, arbitrary paths, or reusable SSH authority. GPU
creation stays with the connected Runpod account after a durable create fence.
"""
import hashlib
import hmac
import json
import math
import os
from pathlib import Path
import pwd
import secrets
import shutil
import sqlite3
import subprocess
import sys
import tarfile
import time
from urllib.request import Request, urlopen
from urllib.parse import quote
import zipfile

RELEASE = '9277e14a7d21a4f8bb142c50943fd3f8a1bfce4b'
IMAGE = 'ghcr.io/hoyosgarciajohn-png/wan-video-generation-gpu@sha256:7ba22cca295fd8290b1df14a349b0e5ee9a2bb46b22af424dc17ade69f23dcf7'
PACKAGE_SHA = '8f7bf34b5a6af48fc8822cf97c7f5e6d1f416ba0f783196abdb18884fba79093'
MASTER_SHA = '10c59dfb5aa01eeb629c9a6ef228dab271686f22a9e42d581aca4aafd9920b0d'
ROOT = Path('/var/lib/wan/longcat-production-20261118')
SESSION = Path('/root/wan-longcat-session-20261118')
OWNER = 'john-hoyos'
SCOPE = 'john-longcat-world-tour-20261118-v1'
PRIOR_PODS = {'22hk9nt6u1t76z', 'o2e7tsgrhdn3wd', 'xqbg5j9dqo4dd4'}


def require(value, message):
    if not value: raise ValueError(message)


def read(path): return json.loads(Path(path).read_text())


def save(path, value):
    from workers.gpu.common import atomic_json
    atomic_json(Path(path), value)


def exclusive(path, value):
    with Path(path).open('x') as f:
        json.dump(value, f, sort_keys=True); f.flush(); os.fsync(f.fileno())


def budget(records):
    rows = [r for r in records if r.get('podId') in PRIOR_PODS]
    require({r['podId'] for r in rows} == PRIOR_PODS, 'All prior B07 invoices required')
    require(all(isinstance(r.get('totalAmount'), (int,float)) and r['totalAmount'] >= 0
                and isinstance(r.get('gpuAmount'), (int,float)) and r['gpuAmount'] >= 0 for r in rows),
            'Invalid invoice amounts')
    spent = math.ceil(sum(r['totalAmount'] for r in rows)*100)
    # Conservative GPU-equivalent hours, counting both GPUs in the benchmark.
    prior_gpu_seconds = math.ceil(sum(r['gpuAmount'] for r in rows)/4.39*3600)
    seconds = min(4800, (14400-prior_gpu_seconds)//2, (2000-spent-200)*3600//878)
    require(seconds > 600, 'No remaining production envelope')
    cap = math.ceil(seconds*878/3600)
    require(spent+cap+200 <= 2000, 'Production budget exceeded')
    return dict(prior_committed_cents=spent, storage_reserve_cents=200,
                prior_gpu_seconds=prior_gpu_seconds, rental_seconds=seconds, compute_cap_cents=cap)


def safe_members(archive):
    names = set(); total = 0
    for member in archive.infolist():
        path = Path(member.filename)
        require(not path.is_absolute() and '..' not in path.parts and '\\' not in member.filename,
                'Unsafe package path')
        require(member.filename not in names, 'Duplicate package member')
        require((member.external_attr >> 16) & 0o170000 != 0o120000, 'Package symlink refused')
        names.add(member.filename); total += member.file_size
        require(total <= 400*1024*1024 and member.file_size <= 150*1024*1024, 'Package too large')
    return archive.infolist()


def runtime():
    from services.controller.service import ControlService
    from services.controller.longcat import LongCatTransport
    c = ControlService('/var/lib/wan/studio.sqlite', '/var/lib/wan/assets')
    return c, LongCatTransport(c)


def unprivileged():
    user = pwd.getpwnam('wan')
    os.setgroups([]); os.setgid(user.pw_gid); os.setuid(user.pw_uid)


def host_gate():
    from deployment.validation_policy import quiescent, monitor_ready, verify_absent
    from services.controller.runpod import https_transport
    require(subprocess.check_output(['git','-C','/opt/wan/current','rev-parse','HEAD'],text=True).strip()==RELEASE,
            'Installed release changed')
    subprocess.run(['git','-C','/opt/wan/current','diff','--exit-code'],check=True,stdout=subprocess.DEVNULL)
    with sqlite3.connect('/var/lib/wan/studio.sqlite') as db:
        require(db.execute('PRAGMA integrity_check').fetchone()[0]=='ok','Database integrity failed')
        quiescent(db, allow_unknown=True)
        monitor_ready(db, read('/var/lib/wan/cleanup-status.json'), allow_unknown=True)
    verify_absent(Path('/etc/wan/runpod-token').read_text().strip(), transport=https_transport())
    token=Path('/etc/wan/runpod-token').read_text().strip(); cursor=None; seen=set()
    for _ in range(100):
        url='https://api.runpod.io/v2/pods'+('?'+'cursor='+quote(cursor,safe='') if cursor else '')
        with https_transport()(Request(url,headers={'Authorization':'Bearer '+token}),timeout=20) as r:page=json.load(r)
        require(not page['pods'],'Provider inventory is not empty')
        if page['pagination']['hasNextPage'] is False:break
        cursor=page['pagination']['nextCursor']
        require(isinstance(cursor,str) and cursor and cursor not in seen,'Invalid provider pagination');seen.add(cursor)
    else:raise ValueError('Incomplete provider inventory')


def signature(payload, domain, key):
    from services.controller.service import canonical
    return dict(key_id='production', payload=payload,
        signature=hmac.new(key,(domain+'\n'+canonical(payload)).encode(),hashlib.sha256).hexdigest())


def main():
    os.umask(0o077)
    op = os.environ.get('SSH_ORIGINAL_COMMAND','')
    require(op in {'upload','prepare','admit','credential','fence-create','status','cleanup','assemble','export','shots','close'},
            'Unsupported production operation')
    require(time.time() < read(SESSION/'authority.json')['expires_at'], 'Operator session expired')
    if op == 'close':
        print(json.dumps(dict(status='OPERATOR_SESSION_CLOSING'))); return
    if op in {'prepare','admit','fence-create','cleanup'}: host_gate()
    guard = read(SESSION/'guard-ready.json') if op=='admit' else None
    if op=='admit':
        require(guard['status']=='READY' and time.time()-guard['at'] < 180, 'Fresh independently observed guard required')
        with urlopen('https://api.github.com/repos/hoyosgarciajohn-png/wan-video-generation/actions/runs/'+guard['run_id'],timeout=20) as r:
            run=json.load(r)
        require(run['status']=='in_progress' and run['event'] in ('workflow_dispatch','push')
                and run['path']=='.github/workflows/longcat-production-guard.yml'
                and run['head_sha']==read(SESSION/'authority.json')['ops_sha'], 'Independent guard is not running')
    unprivileged()
    from workers.gpu.common import digest
    from workers.gpu.longcat_batch import fingerprint, validate_manifest, validate_reference_images, PROTOCOL
    from services.controller.longcat import OWNER_DOMAIN, HOST_DOMAIN, CLEANUP_DOMAIN, source_digest, pod_name
    if op=='upload':
        require(not (ROOT/'package.zip').exists(), 'Package already received')
        p=ROOT/'package.partial'; size=0; checksum=hashlib.sha256()
        with p.open('xb') as f:
            while chunk:=sys.stdin.buffer.read(1024*1024):
                size+=len(chunk); require(size<=144509707,'Package too large')
                checksum.update(chunk); f.write(chunk)
            f.flush(); os.fsync(f.fileno())
        require(size==144509707 and checksum.hexdigest()==PACKAGE_SHA, 'Package integrity failed')
        p.rename(ROOT/'package.zip')
        with zipfile.ZipFile(ROOT/'package.zip') as archive:
            members=safe_members(archive); archive.extractall(ROOT/'package',members)
        print(json.dumps(dict(status='PACKAGE_RECEIVED',bytes=size))); return
    if op=='prepare':
        require(not (ROOT/'prepared.json').exists(), 'Production already prepared')
        payload=json.load(sys.stdin); require(0<=time.time()-payload['observed_at']<300,'Stale billing snapshot')
        limits=budget(payload['billing']['records'])
        manifests=list((ROOT/'package').rglob('inputs/manifest.json'))
        require(len(manifests)==1,'One input manifest required'); source=manifests[0].parent
        manifest=validate_manifest(read(source/'manifest.json'),source); validate_reference_images(manifest,source)
        require(manifest['duration_frames']==9072 and len(manifest['shots'])==110,'Approved full song required')
        masters=list((ROOT/'package').rglob('Busca_Adentro_Complete_Master.wav'))
        require(len(masters)==1 and digest(masters[0])==MASTER_SHA,'Original complete master required')
        require(shutil.disk_usage(ROOT).free > 5*1024**3,'Insufficient durable disk')
        c,_=runtime()
        from services.controller.studio import StudioWorkspace
        studio=StudioWorkspace(c); before=studio.get(OWNER)
        state=studio.create(OWNER,'Busca adentro · LongCat world concert · 6:03','music_video',before['revision'])
        old={p['bundle']['project']['id'] for p in before['projects']}
        project=next(p['bundle']['project']['id'] for p in state['projects'] if p['bundle']['project']['id'] not in old)
        manifest.update(project_id=project,batch_id='world-tour-production-20261118-v1')
        shutil.copytree(source,ROOT/'inputs'); save(ROOT/'inputs/manifest.json',manifest)
        shutil.copyfile(masters[0],ROOT/'master.wav')
        result=dict(project=project,manifest_sha256=fingerprint(manifest),scope_id=SCOPE,pod_name=pod_name(SCOPE),
                    source_sha256=source_digest(),image_ref=IMAGE,**limits)
        exclusive(ROOT/'prepared.json',result); save(ROOT/'billing.json',payload)
        print(json.dumps(result)); return
    prepared=read(ROOT/'prepared.json'); manifest=read(ROOT/'inputs/manifest.json')
    c,transport=runtime()
    if op=='admit':
        require(not (ROOT/'credential.json').exists(),'Scope already consumed')
        require(guard['name']==prepared['pod_name'] and guard['deadline']-guard['admitted_at']<=prepared['rental_seconds'],
                'Guard exceeds retained allowance')
        execution=dict(protocol=PROTOCOL,admitted_at=guard['admitted_at'],deadline=guard['deadline'],gpu_count=2,
            max_hourly_cents=878,compute_cap_cents=prepared['compute_cap_cents'],scope_id=SCOPE,
            guard_run_id=guard['run_id'],manifest_sha256=prepared['manifest_sha256'])
        grant=dict(owner=OWNER,project=prepared['project'],execution=execution,image_ref=IMAGE,
            source_sha256=prepared['source_sha256'],budget_id='john-b07-cumulative-20261117',budget_total_cents=2000,
            prior_committed_cents=prepared['prior_committed_cents'],storage_reserve_cents=prepared['storage_reserve_cents'])
        host=dict(owner=OWNER,project=prepared['project'],grant_sha256=fingerprint(grant),source_sha256=source_digest(),
            image_ref=IMAGE,guard_run_id=guard['run_id'],deadline=guard['deadline'],pod_name=prepared['pod_name'],
            image_import_verified=True,guard_ready=True,storage_verified=True)
        # Runtime import/source/image evidence is immutable and was checked by installer.
        keys={'owner':secrets.token_hex(32),'host':secrets.token_hex(32)}; exclusive(ROOT/'keys.json',keys)
        owner_key,host_key=bytes.fromhex(keys['owner']),bytes.fromhex(keys['host'])
        with (ROOT/'credential.json').open('x') as f:
            result=transport.admit(OWNER,manifest,ROOT/'inputs',signature(grant,OWNER_DOMAIN,owner_key),
                signature(host,HOST_DOMAIN,host_key),approval_keys={'production':(OWNER,owner_key)},
                host_keys={'production':(OWNER,host_key)})
            json.dump(result,f);f.flush();os.fsync(f.fileno())
        save(ROOT/'grant.json',grant)
        print(json.dumps(dict(status='ADMITTED',scope_id=SCOPE,deadline=execution['deadline']))); return
    if op=='credential': print(json.dumps(read(ROOT/'credential.json'))); return
    if op=='fence-create':
        payload=json.load(sys.stdin); grant=read(ROOT/'grant.json')
        require(0<=time.time()-payload['observed_at']<180,'Fresh connected GPU quote required')
        gpu=payload['gpu'];require(gpu['id']=='NVIDIA H100 80GB HBM3' and gpu['secure']
            and 0<gpu['price']['secure']<=4.39 and gpu['availability'] in ('LOW','MEDIUM','HIGH'),'GPU quote not eligible')
        require(time.time()+600<grant['execution']['deadline'],'Insufficient execution time')
        exclusive(ROOT/'create-fence.json',dict(at=time.time(),scope_id=SCOPE,quote=payload,outcome='unknown_until_reconciled'))
        print(json.dumps(dict(status='ONE_CREATE_FENCED',name=prepared['pod_name'],image=IMAGE,
            dataCenterIds=[d['id'] for d in gpu['dataCenters'] if d['availability'] in ('LOW','MEDIUM','HIGH')]))); return
    if op=='status':
        with c.transaction() as db:
            rows=db.execute('SELECT shot,state,receipt FROM longcat_shots WHERE scope=?',(SCOPE,)).fetchall()
        print(json.dumps(dict(scope_id=SCOPE,shots=len(rows),published=sum(r[1]=='published' for r in rows),
            states=[dict(id=r[0],state=r[1]) for r in rows if r[1]!='pending'],
            deadline=read(ROOT/'grant.json')['execution']['deadline'] if (ROOT/'grant.json').exists() else None)));return
    if op=='cleanup':
        grant=read(ROOT/'grant.json');key=bytes.fromhex(read(ROOT/'keys.json')['host'])
        proof=dict(owner=OWNER,scope_id=SCOPE,grant_sha256=fingerprint(grant),guard_run_id=grant['execution']['guard_run_id'],
            pod_name=prepared['pod_name'],absence_confirmed=True,confirmed_at=int(time.time()))
        result=transport.confirm_cleanup(OWNER,SCOPE,signature(proof,CLEANUP_DOMAIN,key),host_keys={'production':(OWNER,key)})
        print(json.dumps(dict(status='CLEANUP_CONFIRMED',result=result)));return
    if op=='assemble':
        from workers.media.longcat_assemble import assemble_review
        with c.transaction() as db:
            rows=dict(db.execute("SELECT shot,receipt FROM longcat_shots WHERE scope=? AND state='published'",(SCOPE,)))
        require(len(rows)==110,'Full coverage not yet rendered')
        result=assemble_review(manifest,[json.loads(rows[s['id']]) for s in manifest['shots']],c.asset_root,
            ROOT/'master.wav',MASTER_SHA,ROOT/'Busca_Adentro_Final_Video.mp4')
        print(json.dumps(result));return
    if op=='export':
        with (ROOT/'Busca_Adentro_Final_Video.mp4').open('rb') as f:shutil.copyfileobj(f,sys.stdout.buffer)
        return
    if op=='shots':
        with c.transaction() as db:
            receipts=[json.loads(row[0]) for row in db.execute("SELECT receipt FROM longcat_shots WHERE scope=? AND state='published'",(SCOPE,))]
        with tarfile.open(fileobj=sys.stdout.buffer,mode='w|') as tar:
            for receipt in receipts:
                tar.add(c.asset_root/receipt['object_key'],arcname=receipt['shot_id']+'.mp4')
        return


if __name__=='__main__':
    try: main()
    except Exception as error:
        print(json.dumps(dict(status='OPERATION_FAILED',type=type(error).__name__,message=str(error)[:180])),file=sys.stderr)
        raise SystemExit(1)
