#!/usr/bin/env bash
# Fresh dedicated Ubuntu server; called over the approved SSH connection.
set -euo pipefail
umask 0077
release_sha=${1:?}
wan_hostname=${2:?}
[[ $EUID == 0 && $release_sha =~ ^[a-f0-9]{40}$ ]]
[[ $wan_hostname == wan-64-225-114-46.sslip.io ]]
[[ $(hostname) == wan-controller-01 && $(uname -m) == x86_64 ]]
. /etc/os-release
[[ $ID == ubuntu && $VERSION_ID == 24.04 ]]
[[ ! -e /opt/wan/current && ! -e /var/lib/wan && ! -e /etc/wan/controller.env ]]
bootstrap_dir=/root/wan-bootstrap-$release_sha
[[ -s $bootstrap_dir/runpod-token ]]
cloud-init status --wait >/dev/null
export DEBIAN_FRONTEND=noninteractive
apt-get update -qq
apt-get install -y --no-install-recommends python3 python3-venv git ffmpeg curl ca-certificates gnupg debian-keyring debian-archive-keyring apt-transport-https ufw
curl -1sLf https://dl.cloudsmith.io/public/caddy/stable/gpg.key | gpg --dearmor -o /usr/share/keyrings/caddy-stable-archive-keyring.gpg
curl -1sLf https://dl.cloudsmith.io/public/caddy/stable/debian.deb.txt > /etc/apt/sources.list.d/caddy-stable.list
chmod 0644 /usr/share/keyrings/caddy-stable-archive-keyring.gpg /etc/apt/sources.list.d/caddy-stable.list
apt-get update -qq
apt-get install -y --no-install-recommends caddy
systemctl disable --now caddy
id wan >/dev/null 2>&1 || useradd --system --home-dir /var/lib/wan --shell /usr/sbin/nologin wan
install -d -m 0755 /opt/wan/current
tar -xzf "$bootstrap_dir/source.tar.gz" -C /opt/wan/current
tar -xzf "$bootstrap_dir/git.tar.gz" -C /opt/wan/current
tar -xzf "$bootstrap_dir/studio.tar.gz" -C /opt/wan/current/apps/studio
cd /opt/wan/current
git remote remove origin
[[ $(git rev-parse HEAD) == "$release_sha" ]]
python3 -m venv /opt/wan/venv
/opt/wan/venv/bin/python -m pip install --require-hashes --only-binary=:all: -r deployment/hosting/requirements.lock
chmod -R a+rX /opt/wan/current /opt/wan/venv
install -d -o root -g wan -m 0750 /etc/wan
install -o root -g wan -m 0640 "$bootstrap_dir/runpod-token" /etc/wan/runpod-token
/opt/wan/venv/bin/python - <<'PY'
import json, os, grp, secrets
from pathlib import Path
p=Path('/etc/wan/studio-tokens.json')
with p.open('x') as f:
    json.dump({secrets.token_urlsafe(48): 'john-hoyos'}, f)
os.chown(p, 0, grp.getgrnam('wan').gr_gid)
os.chmod(p, 0o640)
PY
# Keep administrative SSH key-only. This preserves the approved key and DO console.
printf '%s\n' 'PasswordAuthentication no' 'KbdInteractiveAuthentication no' 'PermitRootLogin prohibit-password' > /etc/ssh/sshd_config.d/00-wan-key-only.conf
sshd -t
systemctl reload ssh
ufw default deny incoming
ufw default allow outgoing
ufw limit 22/tcp
ufw allow 80/tcp
ufw allow 443/tcp
ufw --force enable
bash deployment/hosting/install-services.sh "$release_sha" "$wan_hostname"
rm -f "$bootstrap_dir/runpod-token"
printf '%s\n' 'CONTROLLER_INSTALLED_DISARMED'
