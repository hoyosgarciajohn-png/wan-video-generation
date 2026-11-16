#!/usr/bin/env bash
# Only the approved dedicated host. No provider creation or GPU dispatch.
set -euo pipefail
umask 0077
fail() { printf '%s\n' "$1" >&2; exit 1; }
operation=${WAN_HOST_OPERATION:?}
case "$operation" in inspect|install|resume|verify) ;; *) fail 'Invalid operation';; esac
[[ ${GITHUB_REF:-} == refs/heads/main ]] || fail 'Main branch required'
[[ ${GITHUB_SHA:-} =~ ^[a-f0-9]{40}$ ]] || fail 'Exact source commit required'
[[ -n ${WAN_HOST_SSH_KEY:-} ]] || fail 'Missing approved SSH secret'
host=64.225.114.46
hostname=wan-64-225-114-46.sslip.io
temp_dir=$(mktemp -d)
trap 'rm -rf "$temp_dir"' EXIT
printf '%s\n' "$WAN_HOST_SSH_KEY" > "$temp_dir/key"
unset WAN_HOST_SSH_KEY
ssh-keyscan -T 15 -t ed25519 "$host" > "$temp_dir/known_hosts" 2>/dev/null
[[ $(wc -l < "$temp_dir/known_hosts") == 1 ]] || fail 'Expected one host key'
fingerprint=$(ssh-keygen -lf "$temp_dir/known_hosts" -E sha256 | awk '{print $2}')
if [[ "$operation" != inspect ]]; then
    [[ -n ${WAN_HOST_FINGERPRINT:-} && "$fingerprint" == "$WAN_HOST_FINGERPRINT" ]] || fail 'Host fingerprint mismatch'
fi
printf 'Host ed25519 fingerprint: %s\n' "$fingerprint"
# Inspection is trust-on-first-use at the IP returned by the authenticated DO console.
# Subsequent operations pin that recorded key; they never disable host verification.
ssh_options=(-F /dev/null -i "$temp_dir/key" -o IdentitiesOnly=yes -o BatchMode=yes
    -o StrictHostKeyChecking=yes -o UserKnownHostsFile="$temp_dir/known_hosts"
    -o ConnectTimeout=15 -o ServerAliveInterval=15 -o ServerAliveCountMax=3)
if [[ "$operation" == inspect ]]; then
    ssh "${ssh_options[@]}" "root@$host" 'set -eu; hostname; uname -m; . /etc/os-release; printf "%s\n" "$PRETTY_NAME"; free -m; df -h /; cloud-init status --long; ssh-keygen -lf /etc/ssh/ssh_host_ed25519_key.pub -E sha256; test ! -e /opt/wan/current; test ! -e /var/lib/wan; printf "FRESH_HOST_ACCESS_PASS\n"'
    exit
fi
if [[ "$operation" == install ]]; then
    [[ $(git rev-parse HEAD) == "$GITHUB_SHA" ]] || fail 'Source mismatch'
    [[ -n ${RUNPOD_CLEANUP_TOKEN:-} ]] || fail 'Missing cleanup secret'
    (cd apps/studio && npm ci --no-audit --no-fund && npm run build)
    git diff --quiet && git diff --cached --quiet || fail 'Modified source'
    git archive --format=tar.gz HEAD > "$temp_dir/source.tar.gz"
    tar -czf "$temp_dir/git.tar.gz" .git
    tar -czf "$temp_dir/studio.tar.gz" -C apps/studio dist
    ssh "${ssh_options[@]}" "root@$host" "test ! -e /opt/wan/current && test ! -e /var/lib/wan && mkdir -m 700 /root/wan-bootstrap-$GITHUB_SHA"
    scp "${ssh_options[@]}" "$temp_dir/source.tar.gz" "$temp_dir/git.tar.gz" "$temp_dir/studio.tar.gz" "root@$host:/root/wan-bootstrap-$GITHUB_SHA/"
    # No shell tracing, secret artifacts or token output. Secret travels only in SSH stdin.
    printf '%s' "$RUNPOD_CLEANUP_TOKEN" | ssh "${ssh_options[@]}" "root@$host" "umask 077; cat > /root/wan-bootstrap-$GITHUB_SHA/runpod-token"
    unset RUNPOD_CLEANUP_TOKEN
    ssh "${ssh_options[@]}" "root@$host" "bash -s -- '$GITHUB_SHA' '$hostname'" < deployment/hosting/bootstrap-host.sh
fi
if [[ "$operation" == resume ]]; then
    # Only the observed pre-venv ownership failure from run 43793913368.
    # The already uploaded source/build remain bound to that exact reviewed SHA.
    ssh "${ssh_options[@]}" "root@$host" "bash -s -- 'e5cdd4fb0a138d44f53b40e62ee39b215c30f5c6' '$hostname' resume" < deployment/hosting/bootstrap-host.sh
fi
ssh "${ssh_options[@]}" "root@$host" "bash -s -- '$hostname'" < deployment/hosting/verify-host.sh
curl --fail --silent --show-error --retry 10 --retry-delay 6 --retry-connrefused "https://$hostname/healthz"
printf '\nEXTERNAL_HTTPS_PASS\n'
