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
scp "${opts[@]}" deployment/longcat_session.py deployment/longcat_session_http.py deployment/longcat_session_recipient.pem deployment/evidence/longcat-production-release/publication.json root@64.225.114.46:/root/wan-longcat-session-20261118/
ssh "${opts[@]}" root@64.225.114.46 "OPS_SHA='$GITHUB_SHA' /opt/wan/venv/bin/python -" <<'PY'
import base64, json, os, pwd, secrets, time, subprocess, sys
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
token=secrets.token_urlsafe(32);(root/'http-token').write_text(token)
cipher=subprocess.check_output(['openssl','pkeyutl','-encrypt','-pubin','-inkey',str(root/'longcat_session_recipient.pem'),'-pkeyopt','rsa_padding_mode:oaep','-pkeyopt','rsa_oaep_md:sha256'],input=token.encode())
sys.path.insert(0,str(root));from longcat_session_http import ROUTE
caddy=Path('/etc/wan/Caddyfile');original=caddy.read_text()
assert 'wan-64-225-114-46.sslip.io {' in original and ROUTE not in original
caddy.write_text(original.replace('wan-64-225-114-46.sslip.io {\n','wan-64-225-114-46.sslip.io {\n'+ROUTE,1))
subprocess.run(['caddy','validate','--config',str(caddy),'--adapter','caddyfile'],check=True)
subprocess.run(['systemd-run','--unit=wan-longcat-production-session-20261118','--collect','--property=RuntimeMaxSec=14460','/opt/wan/venv/bin/python',str(root/'longcat_session_http.py')],check=True)
subprocess.run(['systemctl','reload','wan-proxy'],check=True)
print(json.dumps(dict(status='BOUNDED_PRODUCTION_SESSION_INSTALLED',expires_at=expires,source=p['source_commit'],sealed_token=base64.b64encode(cipher).decode(),gpu_started=False)))
PY
