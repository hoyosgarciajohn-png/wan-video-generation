#!/usr/bin/env bash
set -euo pipefail
umask 0077
temporary=$(mktemp -d)
trap 'rm -rf "$temporary"' EXIT
printf '%s\n' "$WAN_HOST_SSH_KEY" > "$temporary/key"
unset WAN_HOST_SSH_KEY
ssh-keyscan -T 15 -t ed25519 64.225.114.46 > "$temporary/known_hosts" 2>/dev/null
test "$(ssh-keygen -lf "$temporary/known_hosts" -E sha256 | awk '{print $2}')" = 'SHA256:aU+cxUkky0P7tyOuS7JQjevb7gLGxeN/kjMVfQIDTr4'
ssh_options=(-F /dev/null -i "$temporary/key" -o IdentitiesOnly=yes -o BatchMode=yes -o StrictHostKeyChecking=yes -o UserKnownHostsFile="$temporary/known_hosts" -o ConnectTimeout=15)
scp "${ssh_options[@]}" benchmarks/longcat/prepare_inputs.py root@64.225.114.46:/root/longcat-prepare-inputs.py
ssh "${ssh_options[@]}" root@64.225.114.46 'cd /opt/wan/current; /opt/wan/venv/bin/python /root/longcat-prepare-inputs.py'
mkdir -p "$RUNNER_TEMP/longcat-inputs"
scp -r "${ssh_options[@]}" root@64.225.114.46:/var/lib/wan/longcat-benchmark-20261117/inputs/. "$RUNNER_TEMP/longcat-inputs/"
