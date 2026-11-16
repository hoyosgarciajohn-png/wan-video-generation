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
# systemd can report active before Waitress binds its socket after restart.
# Retry only this read-only probe, within a bounded startup window.
curl --fail --silent --show-error --connect-timeout 3 --max-time 3 \
    --retry 10 --retry-delay 2 --retry-max-time 30 --retry-connrefused \
    -H "Host: $wan_hostname" http://127.0.0.1:8080/healthz
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
    # Completed trials remain as audit/billing history. Reject missing, active or
    # unconfirmed lifecycle rows instead of requiring an unused database.
    assert db.execute("SELECT count(*) FROM pod_batches WHERE cleanup!='confirmed' OR state NOT IN ('succeeded','failed','canceled')").fetchone()[0] == 0
    assert db.execute('SELECT count(*) FROM live_job_links AS l LEFT JOIN pod_batches AS p ON p.id=l.batch WHERE p.id IS NULL').fetchone()[0] == 0
    retained = db.execute('SELECT count(*) FROM live_job_links').fetchone()[0]
print('HOST_READY; NO_ACTIVE_PROVIDER_OBLIGATIONS; historical_live_jobs=' + str(retained))
PY
# One authenticated Runpod GET. No resource changes; does not verify deletion.
RUNPOD_CLEANUP_TOKEN=$(cat /etc/wan/runpod-token) /opt/wan/venv/bin/python -m deployment.check_cleanup_credential
