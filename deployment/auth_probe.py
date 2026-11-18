"""Read-only mail capability inspection. Never prints secret values."""
import os, tempfile, subprocess
from pathlib import Path
from deployment.director_release import HOST,FINGERPRINT,run,out
with tempfile.TemporaryDirectory() as td:
    root=Path(td); key=root/'key'; key.write_text(os.environ.pop('WAN_HOST_SSH_KEY'));key.chmod(0o600)
    known=root/'known'
    with known.open('w') as f:run('ssh-keyscan','-T','15','-t','ed25519',HOST,stdout=f,stderr=subprocess.DEVNULL)
    assert out('ssh-keygen','-lf',str(known),'-E','sha256').split()[1]==FINGERPRINT
    command="""from pathlib import Path
import json,shutil
p=Path('/etc/wan/controller.env')
names=[s.split('=',1)[0] for s in p.read_text().splitlines() if '=' in s and not s.startswith('#')]
print(json.dumps({'mail_env_names':[n for n in names if any(k in n.upper() for k in ('MAIL','SMTP','BREVO','RESEND'))], 'sendmail':bool(shutil.which('sendmail'))}))
"""
    run('ssh','-F','/dev/null','-i',str(key),'-o','IdentitiesOnly=yes','-o','BatchMode=yes','-o','StrictHostKeyChecking=yes','-o','UserKnownHostsFile='+str(known),'root@'+HOST,'python3 -',input=command,text=True)
