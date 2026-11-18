"""Owner-authorized extension guard for one already running physical Pod."""
import json,os,subprocess,tempfile,time
from pathlib import Path
from urllib.request import Request,urlopen
from urllib.error import HTTPError
from deployment.longcat_guard import watch

POD='gn1lmaun88v7w8'
DEADLINE=1794987625
SCOPE='john-longcat-world-tour-20261118-extension-v1'

def main():
    import hashlib
    name='wan-longcat-song-'+hashlib.sha256(SCOPE.encode()).hexdigest()[:16]
    admitted=int(time.time());assert admitted<1794985345,'Original cleanup handoff already passed'
    token=os.environ['RUNPOD_CLEANUP_TOKEN']
    def request(method,path):
        assert method=='GET' or (method=='DELETE' and path=='/pods/'+POD)
        try:
            with urlopen(Request('https://api.runpod.io/v2'+path,method=method,
                         headers={'Authorization':'Bearer '+token}),timeout=15) as response:
                value=None if method=='DELETE' else json.load(response)
        except HTTPError as error:
            if method=='DELETE' and error.code==404:return None
            raise
        if method=='GET' and path.startswith('/pods'):
            value['pods']=[{**p,'name':name} for p in value['pods'] if p['id']==POD]
        return value
    with tempfile.TemporaryDirectory() as temporary:
        root=Path(temporary);key=root/'key';key.write_text(os.environ.pop('WAN_HOST_SSH_KEY'));key.chmod(0o600)
        known=root/'known'
        with known.open('w') as f:subprocess.run(['ssh-keyscan','-T','15','-t','ed25519','64.225.114.46'],stdout=f,stderr=subprocess.DEVNULL,check=True)
        assert subprocess.check_output(['ssh-keygen','-lf',str(known),'-E','sha256'],text=True).split()[1]=='SHA256:aU+cxUkky0P7tyOuS7JQjevb7gLGxeN/kjMVfQIDTr4'
        ssh=['ssh','-F','/dev/null','-i',str(key),'-o','IdentitiesOnly=yes','-o','BatchMode=yes',
             '-o','StrictHostKeyChecking=yes','-o','UserKnownHostsFile='+str(known),'-o','ConnectTimeout=15','root@64.225.114.46']
        def emit(line,**kwargs):
            event=json.loads(line)
            if event['status']=='READY':
                event.update(pod_id=POD,run_id=os.environ['GITHUB_RUN_ID'],head_sha=os.environ['GITHUB_SHA'],
                    scope_id=SCOPE,authorization='Owner requested same-Pod runtime extension to finish all shots',
                    additional_compute_cap_cents=586,original_deadline=1794985375)
                subprocess.run(ssh+['umask 077; set -C; cat > /root/wan-longcat-session-20261118/extension-guard-ready.json'],
                    input=json.dumps(event),text=True,check=True,timeout=30)
                Path(os.environ['EXTENSION_READY_PATH']).write_text(json.dumps(event))
            print(json.dumps(event),flush=True)
        watch(name,admitted,DEADLINE,request,emit=emit)

if __name__=='__main__':main()
