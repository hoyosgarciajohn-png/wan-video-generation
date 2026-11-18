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
# Recovery only: the previous run admitted the exact suffix before its final SSH timed out.
ssh "${opts[@]}" root@64.225.114.46 '/opt/wan/venv/bin/python -' <<'PYREMOTE'
import json,time
from pathlib import Path
root=Path('/root/wan-longcat-session-20261118')
ext=Path('/var/lib/wan/longcat-production-20261118/extension')
credential=json.loads((ext/'credential.json').read_text());grant=json.loads((ext/'grant.json').read_text())
assert credential['scope_id']=='john-longcat-world-tour-20261118-extension-v1'
assert credential['deadline']==grant['execution']['deadline']==1794987625
assert credential['binding']==grant['execution']['manifest_sha256']
assert time.time()<1794987475 and (root/'longcat_session_original.py').exists()
(root/'longcat_session.py').write_text("import sys\nsys.path.insert(0,'/root/wan-longcat-session-20261118')\nfrom reuse_control import dispatch\ndispatch()\n")
print(json.dumps({'status':'EXISTING_EXTENSION_CONTROL_ACTIVATED','deadline':1794987625,'new_admissions':0}))
PYREMOTE
