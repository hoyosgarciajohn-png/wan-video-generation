"""Relay the actual independent READY event to the pinned production host."""
import json
import os
from pathlib import Path
import subprocess
import tempfile
import time


def main():
    with tempfile.TemporaryDirectory() as temp:
        root=Path(temp);key=root/'key';key.write_text(os.environ.pop('WAN_HOST_SSH_KEY'));key.chmod(0o600)
        known=root/'known_hosts'
        with known.open('w') as f:subprocess.run(['ssh-keyscan','-T','15','-t','ed25519','64.225.114.46'],stdout=f,stderr=subprocess.DEVNULL,check=True)
        identity=subprocess.check_output(['ssh-keygen','-lf',str(known),'-E','sha256'],text=True).split()[1]
        assert identity=='SHA256:aU+cxUkky0P7tyOuS7JQjevb7gLGxeN/kjMVfQIDTr4'
        ssh=['ssh','-F','/dev/null','-i',str(key),'-o','IdentitiesOnly=yes','-o','BatchMode=yes',
            '-o','StrictHostKeyChecking=yes','-o','UserKnownHostsFile='+str(known),'-o','ConnectTimeout=15','root@64.225.114.46']
        if os.environ.get('GITHUB_EVENT_NAME')=='push':
            request=json.loads(Path('deployment/longcat-production-request.json').read_text())
            assert request==dict(scope_id='john-longcat-world-tour-20261118-v1',
                pod_name='wan-longcat-song-5a339ca02dcbfe49',rental_seconds=3864)
            for attempt in range(30):
                installed=json.loads(subprocess.check_output(ssh+['cat /root/wan-longcat-session-20261118/authority.json'],text=True,timeout=20))
                if installed['ops_sha']==os.environ['GITHUB_SHA']:break
                time.sleep(3)
            else:raise ValueError('Matching operator deployment not ready')
            admitted=int(time.time())
            os.environ.update(LONGCAT_POD_NAME=request['pod_name'],LONGCAT_ADMITTED_AT=str(admitted),
                LONGCAT_DEADLINE=str(admitted+request['rental_seconds']))
        process=subprocess.Popen(['python3','-u','-m','deployment.longcat_guard'],stdout=subprocess.PIPE,text=True)
        for line in process.stdout:
            print(line,end='',flush=True)
            event=json.loads(line)
            if event['status']=='READY':
                event['run_id']=os.environ['GITHUB_RUN_ID']
                command=['ssh','-F','/dev/null','-i',str(key),'-o','IdentitiesOnly=yes','-o','BatchMode=yes',
                    '-o','StrictHostKeyChecking=yes','-o','UserKnownHostsFile='+str(known),'-o','ConnectTimeout=15',
                    'root@64.225.114.46','umask 077; set -C; cat > /root/wan-longcat-session-20261118/guard-ready.json']
                subprocess.run(command,input=json.dumps(event),text=True,check=True,timeout=30)
                print('INDEPENDENT_READY_RECORDED',flush=True)
        raise SystemExit(process.wait())


if __name__=='__main__':main()
