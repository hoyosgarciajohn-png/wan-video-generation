#!/usr/bin/env bash
# One reviewed upgrade from the observed initial deployment; preserve private state.
set -euo pipefail
umask 0077
release_sha=${1:?}
[[ $EUID == 0 && $release_sha =~ ^[a-f0-9]{40}$ ]]
[[ $(hostname) == wan-controller-01 ]]
cd /opt/wan/current
old_sha=$(git rev-parse HEAD)
[[ $old_sha == 1a26af63e90193411c15a083c9bb1c84277d0b8e ]]
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
/opt/wan/venv/bin/python - <<'PY'
import sqlite3
with sqlite3.connect('/var/lib/wan/studio.sqlite') as db:
    assert db.execute('SELECT count(*) FROM live_job_links').fetchone()[0] == 0
PY
mkdir -m 0700 "$bootstrap_dir/pre-upgrade"
/opt/wan/venv/bin/python -m services.controller.backup create --database /var/lib/wan/studio.sqlite --assets /var/lib/wan/assets --output "$bootstrap_dir/pre-upgrade"
systemctl stop wan-controller wan-cleanup
mv /opt/wan/current "$previous"
mv "$stage" /opt/wan/current
if ! systemctl start wan-controller wan-cleanup; then
    systemctl stop wan-controller wan-cleanup
    mv /opt/wan/current "$stage"
    mv "$previous" /opt/wan/current
    systemctl start wan-controller wan-cleanup
    exit 1
fi
printf '%s\n' 'REVIEWED_SOURCE_UPGRADED; PRIVATE_STATE_PRESERVED'
