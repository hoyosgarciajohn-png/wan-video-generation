"""Relay the actual independent READY event to the pinned production host."""
import json
import os
from pathlib import Path
import subprocess
import tempfile


def main():
    with tempfile.TemporaryDirectory() as temp:
        root=Path(temp);key=root/'key';key.write_text(os.environ.pop('WAN_HOST_SSH_KEY'));key.chmod(0o600)
        known=root/'known_hosts'
        with known.open('w') as f:subprocess.run(['ssh-keyscan','-T','15','-t','ed25519','64.225.114.46'],stdout=f,stderr=subprocess.DEVNULL,check=True)
        identity=subprocess.check_output(['ssh-keygen','-lf',str(known),'-E','sha256'],text=True).split()[1]
        assert identity=='SHA256:aU+cxUkky0P7tyOuS7JQjevb7gLGxeN/kjMVfQIDTr4'
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
