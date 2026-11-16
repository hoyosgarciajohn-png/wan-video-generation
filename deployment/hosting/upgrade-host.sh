#!/usr/bin/env bash
# Reviewed upgrade from the observed controller deployment; preserve private state.
set -euo pipefail
umask 0077
release_sha=${1:?}
[[ $EUID == 0 && $release_sha =~ ^[a-f0-9]{40}$ ]]
[[ $(hostname) == wan-controller-01 ]]
cd /opt/wan/current
old_sha=$(git rev-parse HEAD)
expected_old_sha=d30fa01aec7dc6bf50be8e5e2a950efb3c04fffc
if [[ $old_sha != "$expected_old_sha" ]]; then
    printf 'Upgrade baseline mismatch: expected %s; observed %s\n' "$expected_old_sha" "$old_sha" >&2
    exit 1
fi
git diff --quiet && git diff --cached --quiet
[[ ! -L /opt/wan/current ]]
bootstrap_dir=/root/wan-bootstrap-$release_sha
stage=/opt/wan/release-$release_sha
previous=/opt/wan/previous-$old_sha
[[ ! -e $stage && ! -e $previous ]]
install -d -m 0755 "$stage"
tar --no-same-owner -xzf "$bootstrap_dir/source.tar.gz" -C "$stage"
tar --no-same-owner -xzf "$bootstrap_dir/git.tar.gz" -C "$stage"
tar --no-same-owner -xzf "$bootstrap_dir/studio.tar.gz" -C "$stage/apps/studio"
chown -R root:root "$stage"
chmod -R a+rX "$stage"
[[ $(git -C "$stage" rev-parse HEAD) == "$release_sha" ]]
git -C "$stage" diff --quiet
git -C "$stage" remote remove origin
cmp deployment/requirements.lock "$stage/deployment/requirements.lock"
cmp deployment/hosting/requirements.lock "$stage/deployment/hosting/requirements.lock"
for unit in wan-controller.service wan-cleanup.service wan-proxy.service; do
    cmp "deployment/hosting/$unit" "$stage/deployment/hosting/$unit"
done
# The owner's new instruction permits this one expired unknown request to
# coexist with an isolated test. Keep the cleanup process running across the
# source swap; preserve the uncertain database in a non-restorable checkpoint.
(cd "$stage" && /opt/wan/venv/bin/python - <<'PY_GATE'
import json, sqlite3
from pathlib import Path
from deployment.validation_policy import quiescent, monitor_ready, verify_absent
from services.controller.runpod import https_transport
with sqlite3.connect('/var/lib/wan/studio.sqlite') as db:
    quiescent(db, allow_unknown=True)
    monitor_ready(db, json.loads(Path('/var/lib/wan/cleanup-status.json').read_text()), allow_unknown=True)
verify_absent(Path('/etc/wan/runpod-token').read_text().strip(), transport=https_transport())
PY_GATE
)
systemctl is-active --quiet wan-cleanup
systemctl stop wan-controller
trap 'systemctl start wan-controller' EXIT
(cd "$stage" && /opt/wan/venv/bin/python -m deployment.validation_policy "$bootstrap_dir/pre-upgrade")
mv /opt/wan/current "$previous"
mv "$stage" /opt/wan/current
if ! systemctl restart wan-controller wan-cleanup; then
    systemctl stop wan-controller wan-cleanup
    mv /opt/wan/current "$stage"
    mv "$previous" /opt/wan/current
    systemctl start wan-controller wan-cleanup
    exit 1
fi
trap - EXIT
printf '%s\n' 'REVIEWED_SOURCE_UPGRADED; PRIVATE_STATE_AND_UNRESOLVED_REQUEST_PRESERVED'
