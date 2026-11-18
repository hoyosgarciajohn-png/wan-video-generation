"""Install only the approved Director overlay; preserve live private state.

Executed by the dedicated GitHub workflow using the existing host SSH secret.
This cannot rent GPUs, call generation APIs or change service credentials.
"""
import hashlib
import json
import os
from pathlib import Path
import subprocess
import tarfile
import tempfile

RELEASE='d8957527559ba1fe25c92cbed6598cf4b4b35047'
BASE='ce9063c2d62bbd9283962cea7b96d03bba0a93be'
HOST='64.225.114.46'
FINGERPRINT='SHA256:aU+cxUkky0P7tyOuS7JQjevb7gLGxeN/kjMVfQIDTr4'
FILES=['services/controller/http_api.py','services/controller/backup.py',
       'services/controller/director.py','services/providers/fal_music.py',
       'services/providers/music_models.json']

def run(*args,**kw):return subprocess.run(args,check=True,**kw)
def out(*args):return subprocess.check_output(args,text=True).strip()

def main():
    assert os.environ.get('GITHUB_REF')=='refs/heads/main'
    key_value=os.environ.pop('WAN_HOST_SSH_KEY')
    with tempfile.TemporaryDirectory() as td:
        root=Path(td);key=root/'key';key.write_text(key_value);key.chmod(0o600)
        known=root/'known_hosts'
        with known.open('w') as f:run('ssh-keyscan','-T','15','-t','ed25519',HOST,stdout=f,stderr=subprocess.DEVNULL)
        assert out('ssh-keygen','-lf',str(known),'-E','sha256').split()[1]==FINGERPRINT
        opts=['-F','/dev/null','-i',str(key),'-o','IdentitiesOnly=yes','-o','BatchMode=yes',
              '-o','StrictHostKeyChecking=yes','-o','UserKnownHostsFile='+str(known),'-o','ConnectTimeout=15']
        manifest={'release':RELEASE,'files':{},'expected':{}}
        archive=root/'director.tar.gz'
        with tarfile.open(archive,'w:gz') as tar:
            for name in FILES:
                expected=subprocess.check_output(['git','show',RELEASE+':'+name])
                assert Path(name).read_bytes()==expected
                manifest['files'][name]=hashlib.sha256(expected).hexdigest()
                tar.add(name,arcname=name)
                old=subprocess.run(['git','show',BASE+':'+name],capture_output=True)
                manifest['expected'][name]=hashlib.sha256(old.stdout).hexdigest() if old.returncode==0 else None
            for file in Path('apps/studio/dist').rglob('*'):
                if file.is_file():
                    name=str(file);manifest['files'][name]=hashlib.sha256(file.read_bytes()).hexdigest();tar.add(file,arcname=name)
            p=root/'manifest.json';p.write_text(json.dumps(manifest));tar.add(p,arcname='director-release.json')
        remote='/root/wan-director-'+RELEASE
        run('ssh',*opts,'root@'+HOST,'umask 077; mkdir -p '+remote)
        run('scp',*opts,str(archive),'root@'+HOST+':'+remote+'/director.tar.gz')
        run('scp',*opts,'deployment/director_install.py','root@'+HOST+':'+remote+'/install.py')
        run('ssh',*opts,'root@'+HOST,'/opt/wan/venv/bin/python '+remote+'/install.py '+remote)

if __name__=='__main__':main()
