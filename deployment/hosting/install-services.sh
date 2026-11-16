#!/usr/bin/env bash
# Fresh dedicated host only. Does not install packages, issue keys or launch GPUs.
set -euo pipefail
umask 0077
fail() { printf '%s\n' "$1" >&2; exit 1; }
[[ $# == 2 ]] || fail 'Usage: bash deployment/hosting/install-services.sh EXPECTED_COMMIT HOSTNAME'
release_sha=$1
wan_hostname=$2
[[ $EUID == 0 ]] || fail 'Run on the approved host as root'
[[ $release_sha =~ ^[a-f0-9]{40}$ ]] || fail 'Exact reviewed commit required'
[[ $wan_hostname =~ ^[a-z0-9]([a-z0-9-]*[a-z0-9])?(\.[a-z0-9]([a-z0-9-]*[a-z0-9])?)+$ ]] || fail 'DNS hostname required'
[[ $wan_hostname != *.invalid && $wan_hostname != *.test && $wan_hostname != *.local ]] || fail 'Use the approved public hostname'
[[ $(uname -m) == x86_64 ]] || fail 'Linux amd64 required'
[[ -d /run/systemd/system ]] || fail 'A running systemd host is required'
[[ $(pwd -P) == /opt/wan/current ]] || fail 'Use the reviewed checkout at /opt/wan/current'
[[ $(git rev-parse HEAD) == "$release_sha" ]] || fail 'Source revision mismatch'
git diff --quiet && git diff --cached --quiet || fail 'Tracked source is modified'
[[ -z $(git ls-files --others --exclude-standard) ]] || fail 'Untracked source is present'
for required_command in git ffmpeg ffprobe caddy systemctl runuser; do
    command -v "$required_command" >/dev/null || fail "Missing command: $required_command"
done
[[ -f apps/studio/dist/index.html ]] || fail 'Build the pinned Studio before installation'
[[ -x /opt/wan/venv/bin/python ]] || fail 'Install the hash-locked hosting dependencies first'
/opt/wan/venv/bin/python -c 'import sys,waitress,jsonschema; assert sys.version_info >= (3,11)'
id wan >/dev/null 2>&1 || fail 'Dedicated wan service user required'
for target in /etc/wan/controller.env /etc/wan/cleanup.env /etc/wan/Caddyfile /etc/systemd/system/wan-controller.service /etc/systemd/system/wan-cleanup.service /etc/systemd/system/wan-proxy.service; do
    [[ ! -e $target && ! -L $target ]] || fail "Existing installation retained: $target"
done
[[ ! -e /var/lib/wan && ! -L /var/lib/wan ]] || fail 'Existing state retained; use the separate recovery/upgrade procedure'
systemctl is-active --quiet caddy && fail 'Default Caddy service must be stopped on this fresh dedicated host'
# Reject missing, linked, broadly readable, or differently owned host secrets.
WAN_HOSTNAME="$wan_hostname" /opt/wan/venv/bin/python - <<'PY'
import grp,json,os,stat
from pathlib import Path
group=grp.getgrnam('wan').gr_gid
directory=Path('/etc/wan')
assert directory.is_dir() and not directory.is_symlink()
assert directory.stat().st_uid == 0 and directory.stat().st_gid == group
assert stat.S_IMODE(directory.stat().st_mode) == 0o750
for name in ('studio-tokens.json','runpod-token'):
    p=directory/name
    assert p.is_file() and not p.is_symlink()
    s=p.stat()
    assert s.st_uid == 0 and s.st_gid == group and stat.S_IMODE(s.st_mode) == 0o640
tokens=json.loads((directory/'studio-tokens.json').read_text())
assert isinstance(tokens,dict) and tokens
assert all(isinstance(k,str) and len(k)>=32 and isinstance(v,str) and v.strip() for k,v in tokens.items())
assert (directory/'runpod-token').read_text().strip()
PY
install -d -o wan -g wan -m 0700 /var/lib/wan
sed "s/wan.example.invalid/$wan_hostname/g" deployment/hosting/controller.env.example > /etc/wan/controller.env
cp deployment/hosting/cleanup.env.example /etc/wan/cleanup.env
sed "s/wan.example.invalid/$wan_hostname/g" deployment/hosting/Caddyfile.example > /etc/wan/Caddyfile
chown root:wan /etc/wan/controller.env /etc/wan/cleanup.env /etc/wan/Caddyfile
chmod 0640 /etc/wan/controller.env /etc/wan/cleanup.env /etc/wan/Caddyfile
runuser -u wan -- env WAN_STATE=/var/lib/wan PYTHONDONTWRITEBYTECODE=1 /opt/wan/venv/bin/python -m deployment.initialize_host
install -m 0644 deployment/hosting/wan-controller.service deployment/hosting/wan-cleanup.service deployment/hosting/wan-proxy.service /etc/systemd/system/
runuser -u wan -- env XDG_DATA_HOME=/var/lib/wan/caddy XDG_CONFIG_HOME=/var/lib/wan/caddy-config caddy validate --config /etc/wan/Caddyfile --adapter caddyfile
systemctl daemon-reload
systemctl enable --now wan-cleanup.service wan-controller.service wan-proxy.service
systemctl is-active --quiet wan-controller.service wan-cleanup.service wan-proxy.service
printf '%s\n' 'Services started. Paid dispatch remains disabled. Complete HTTPS, recovery, credential and monitor acceptance before any GPU admission.'
