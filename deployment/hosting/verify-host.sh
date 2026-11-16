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
from deployment.validation_policy import quiescent, monitor_ready, verify_absent
from services.controller.runpod import https_transport
p=Path('/var/lib/wan/cleanup-status.json')
for _ in range(20):
    try:
        status=json.loads(p.read_text())
        with sqlite3.connect('/var/lib/wan/studio.sqlite') as db:
            assert db.execute('PRAGMA integrity_check').fetchone()[0] == 'ok'
            retained_unknown=quiescent(db, allow_unknown=True)
            monitor_ready(db, status, allow_unknown=True)
            retained=db.execute('SELECT count(*) FROM live_job_links').fetchone()[0]
        break
    except (AssertionError, FileNotFoundError):
        time.sleep(1)
else:
    raise SystemExit('Cleanup heartbeat or historical state is not acceptable')
verify_absent(Path('/etc/wan/runpod-token').read_text().strip(), transport=https_transport())
print(json.dumps(status))
print(json.dumps({'host_operational':True, 'historical_live_jobs':retained,
                  'old_request_still_unresolved':retained_unknown,
                  'billing_reservations_released':False}))
PY
# One authenticated Runpod GET. No resource changes; does not verify deletion.
RUNPOD_CLEANUP_TOKEN=$(cat /etc/wan/runpod-token) /opt/wan/venv/bin/python -m deployment.check_cleanup_credential
