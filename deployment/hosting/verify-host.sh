#!/usr/bin/env bash
set -euo pipefail
wan_hostname=${1:?}
[[ $wan_hostname == wan-64-225-114-46.sslip.io ]]
cd /opt/wan/current
git rev-parse HEAD
git diff --quiet && git diff --cached --quiet
systemctl is-active wan-controller wan-cleanup wan-proxy
systemctl is-enabled wan-controller wan-cleanup wan-proxy
free -m
df -h /
ufw status
ss -lntp
curl --fail --silent --show-error -H "Host: $wan_hostname" http://127.0.0.1:8080/healthz
/opt/wan/venv/bin/python - <<'PY'
import json, time, sqlite3
from pathlib import Path
p=Path('/var/lib/wan/cleanup-status.json')
for _ in range(20):
    if p.is_file():
        status=json.loads(p.read_text())
        if status.get('ready') is True and time.time()-status['checked_at'] < 45:
            print(json.dumps(status)); break
    time.sleep(1)
else:
    raise SystemExit('Cleanup heartbeat is not ready')
with sqlite3.connect('/var/lib/wan/studio.sqlite') as db:
    assert db.execute('PRAGMA integrity_check').fetchone()[0] == 'ok'
    assert db.execute('SELECT count(*) FROM live_job_links').fetchone()[0] == 0
print('HOST_READY_DISARMED; NO_LIVE_JOB_BINDINGS')
PY
# One authenticated Runpod GET. No resource changes; does not verify deletion.
RUNPOD_CLEANUP_TOKEN=$(cat /etc/wan/runpod-token) /opt/wan/venv/bin/python -m deployment.check_cleanup_credential
