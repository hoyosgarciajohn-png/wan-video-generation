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
ssh "${opts[@]}" root@64.225.114.46 'test ! -f /root/wan-longcat-session-20261118/longcat_session_original.py; cp /root/wan-longcat-session-20261118/longcat_session.py /root/wan-longcat-session-20261118/longcat_session_original.py'
scp "${opts[@]}" deployment/reuse_control.py root@64.225.114.46:/root/wan-longcat-session-20261118/
scp "${opts[@]}" workers/media/longcat_continuation.py root@64.225.114.46:/root/wan-longcat-session-20261118/continuation_prepare.py
ssh "${opts[@]}" root@64.225.114.46 'PYTHONPATH=/opt/wan/current /opt/wan/venv/bin/python /root/wan-longcat-session-20261118/reuse_control.py'
ssh "${opts[@]}" root@64.225.114.46 'cat > /root/wan-longcat-session-20261118/longcat_session.py' <<'PY'
import sys
sys.path.insert(0,'/root/wan-longcat-session-20261118')
from reuse_control import dispatch
dispatch()
PY
