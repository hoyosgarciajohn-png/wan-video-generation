#!/usr/bin/env bash
set -euo pipefail
umask 077
temporary=$(mktemp -d)
trap 'rm -rf "$temporary"' EXIT
printf '%s\n' "$WAN_HOST_SSH_KEY" > "$temporary/key"
unset WAN_HOST_SSH_KEY
ssh-keyscan -T 15 -t ed25519 64.225.114.46 > "$temporary/known" 2>/dev/null
[[ $(ssh-keygen -lf "$temporary/known" -E sha256 | awk '{print $2}') == SHA256:aU+cxUkky0P7tyOuS7JQjevb7gLGxeN/kjMVfQIDTr4 ]]
opts=(-F /dev/null -i "$temporary/key" -o IdentitiesOnly=yes -o BatchMode=yes -o StrictHostKeyChecking=yes -o UserKnownHostsFile="$temporary/known" -o ConnectTimeout=15)
scp "${opts[@]}" deployment/completion_control.py root@64.225.114.46:/root/wan-longcat-session-20261118/
ssh "${opts[@]}" root@64.225.114.46 '/opt/wan/venv/bin/python -' <<'PY'
import json,time
from pathlib import Path
root=Path('/root/wan-longcat-session-20261118')
assert json.loads((root/'completion-guard-ready.json').read_text())['deadline']==1794988500
assert time.time()<1794987475
assert Path('/var/lib/wan/longcat-production-20261118/extension/credential.json').exists()
(root/'longcat_session.py').write_text("import sys\nsys.path.insert(0,'/root/wan-longcat-session-20261118')\nfrom completion_control import dispatch\ndispatch()\n")
print(json.dumps({'status':'FINAL_COMPLETION_CONTROL_PREPARED','admitted':False,'current_worker_unchanged':True}))
PY
