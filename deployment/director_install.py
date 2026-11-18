"""Host-side guarded overlay, called only by director_release.py."""
import hashlib
import json
import os
from pathlib import Path
import shutil
import sqlite3
import subprocess
import sys
import tarfile
import time
from urllib.request import Request,urlopen

root=Path(sys.argv[1]);live=Path('/opt/wan/current');stage=root/'stage'
assert subprocess.check_output(['hostname'],text=True).strip()=='wan-controller-01'
assert not stage.exists(), 'Existing release stage: inspect prior outcome before retry'
stage.mkdir()
with tarfile.open(root/'director.tar.gz') as tar:tar.extractall(stage,filter='data')
m=json.loads((stage/'director-release.json').read_text())
assert m['release']=='d8957527559ba1fe25c92cbed6598cf4b4b35047'
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
for name,digest in m['files'].items():assert sha(stage/name)==digest,name
baseline=subprocess.check_output(['git','-C',str(live),'rev-parse','HEAD'],text=True).strip()
print('DIRECTOR_OBSERVED_BASELINE',baseline,flush=True)
for name,expected in m['expected'].items():
    p=live/name;actual=sha(p) if p.exists() else None
    print('DIRECTOR_FILE_CHECK',name,actual,actual==expected,flush=True)
    assert actual==expected,'Live application baseline differs: '+name
settings={}
for line in Path('/etc/wan/controller.env').read_text().splitlines():
    if line and not line.startswith('#') and '=' in line:
        k,v=line.split('=',1);settings[k]=v.strip().strip('"').strip("'")
database=Path(settings.get('WAN_STUDIO_DATABASE',settings['WAN_STATE']+'/studio.sqlite'))
assert database.is_file()
with sqlite3.connect(database) as db:
    for (raw,) in db.execute('SELECT bundle FROM projects'):
        b=json.loads(raw)
        assert all(x['state'] in ('succeeded','failed','canceled') for x in b['batches']), 'Active render batch'
        assert all(x['state'] in ('succeeded','failed','canceled') for x in b['exports']), 'Active export'
    before=db.execute('SELECT id,owner,bundle FROM projects ORDER BY id').fetchall()
    db.backup(sqlite3.connect(root/'pre-release.sqlite'))
for unit in ('wan-controller','wan-cleanup','wan-proxy'):
    subprocess.run(['systemctl','is-active','--quiet',unit],check=True)
backup=root/'previous';backup.mkdir()
for name in m['expected']:
    if (live/name).exists():
        dest=backup/name;dest.parent.mkdir(parents=True,exist_ok=True);shutil.copy2(live/name,dest)
shutil.copytree(live/'apps/studio/dist',backup/'dist')
subprocess.run(['systemctl','stop','wan-controller'],check=True)
try:
    for name in m['files']:
        dest=live/name;dest.parent.mkdir(parents=True,exist_ok=True);shutil.copy2(stage/name,dest);dest.chmod(0o644)
    # Parent directories must be traversable by the existing service identity.
    (live/'services/providers').chmod(0o755)
    subprocess.run(['systemctl','start','wan-controller'],check=True)
    origin=settings['WAN_STUDIO_ORIGIN']
    for attempt in range(20):
        try:
            with urlopen(Request('http://127.0.0.1:8080/healthz',headers={'Host':origin.split('://',1)[1]}),timeout=3) as r:
                assert json.load(r)['ready'];break
        except Exception:
            if attempt==19:raise
            time.sleep(1)
    with sqlite3.connect(database) as db:
        assert db.execute('SELECT id,owner,bundle FROM projects ORDER BY id').fetchall()==before,'Historical project mutation'
        assert db.execute("SELECT name FROM sqlite_master WHERE name='director_briefs'").fetchone()
    for unit in ('wan-controller','wan-cleanup','wan-proxy'):
        subprocess.run(['systemctl','is-active','--quiet',unit],check=True)
    manifest={**m,'previous_git_sha':baseline,'mode':'targeted-approved-overlay','historical_projects_preserved':len(before),'paid_dispatch':False}
    (live/'director-installed-release.json').write_text(json.dumps(manifest,indent=2));(live/'director-installed-release.json').chmod(0o644)
    print('DIRECTOR_RELEASE_INSTALLED',json.dumps({'release':m['release'],'projects_preserved':len(before),'paid_dispatch':False}),flush=True)
except BaseException:
    subprocess.run(['systemctl','stop','wan-controller'],check=False)
    for name,expected in m['expected'].items():
        if expected is None:(live/name).unlink(missing_ok=True)
        else:shutil.copy2(backup/name,live/name)
    shutil.rmtree(live/'apps/studio/dist');shutil.copytree(backup/'dist',live/'apps/studio/dist')
    # Keep any newly saved briefs intact. This is not a whole-database rollback.
    subprocess.run(['systemctl','start','wan-controller'],check=False)
    raise
