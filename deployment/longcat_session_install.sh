#!/usr/bin/env bash
set -euo pipefail
umask 077
[[ $GITHUB_REF == refs/heads/main ]]
temp_dir=$(mktemp -d)
trap 'rm -rf "$temp_dir"' EXIT
printf '%s\n' "$WAN_HOST_SSH_KEY" > "$temp_dir/key"
unset WAN_HOST_SSH_KEY
ssh-keyscan -T 15 -t ed25519 64.225.114.46 > "$temp_dir/known_hosts" 2>/dev/null
[[ $(ssh-keygen -lf "$temp_dir/known_hosts" -E sha256 | awk '{print $2}') == SHA256:aU+cxUkky0P7tyOuS7JQjevb7gLGxeN/kjMVfQIDTr4 ]]
opts=(-F /dev/null -i "$temp_dir/key" -o IdentitiesOnly=yes -o BatchMode=yes -o StrictHostKeyChecking=yes -o UserKnownHostsFile="$temp_dir/known_hosts" -o ConnectTimeout=15)
ssh "${opts[@]}" root@64.225.114.46 'mkdir -p /root/wan-longcat-session-20261118; chmod 700 /root/wan-longcat-session-20261118'
scp "${opts[@]}" deployment/longcat_session.py deployment/evidence/longcat-production-release/publication.json root@64.225.114.46:/root/wan-longcat-session-20261118/
ssh "${opts[@]}" root@64.225.114.46 "OPS_SHA='$GITHUB_SHA' /opt/wan/venv/bin/python -" <<'PY'
import json, os, pwd, time, subprocess
from pathlib import Path
root=Path('/root/wan-longcat-session-20261118')
assert subprocess.check_output(['git','-C','/opt/wan/current','rev-parse','HEAD'],text=True).strip()=='9277e14a7d21a4f8bb142c50943fd3f8a1bfce4b'
p=json.loads((root/'publication.json').read_text())
assert p['source_commit']=='9277e14a7d21a4f8bb142c50943fd3f8a1bfce4b' and p['offline_import']=='PASS' and p['registry_status']=='PASS'
assert p['image'].endswith('@sha256:7ba22cca295fd8290b1df14a349b0e5ee9a2bb46b22af424dc17ade69f23dcf7')
authority=root/'authority.json'
assert not authority.exists(), 'A consumed session cannot be reset'
expires=int(time.time())+14400
authority.write_text(json.dumps(dict(expires_at=expires,ops_sha=os.environ['OPS_SHA'])))
work=Path('/var/lib/wan/longcat-production-20261118');work.mkdir(mode=0o700)
user=pwd.getpwnam('wan');os.chown(work,user.pw_uid,user.pw_gid)
key='ssh-ed25519 AAAAC3NzaC1lZDI1NTE5AAAAIEG319hIalr5XgOhlDxI1muJw6QakkedwFH3IcnZ17Em wan-longcat-production-20261118'
expiry=time.strftime('%Y%m%d%H%M%SZ',time.gmtime(expires))
line='restrict,expiry-time="'+expiry+'",command="env PYTHONPATH=/opt/wan/current /opt/wan/venv/bin/python /root/wan-longcat-session-20261118/longcat_session.py" '+key+'\n'
auth=Path('/root/.ssh/authorized_keys')
assert key not in auth.read_text()
with auth.open('a') as f:f.write('\n'+line)
os.chmod(auth,0o600)
print(json.dumps(dict(status='BOUNDED_PRODUCTION_SESSION_INSTALLED',expires_at=expires,source=p['source_commit'],gpu_started=False)))
PY
