#!/usr/bin/env bash
# Only the approved dedicated host. No provider creation or GPU dispatch.
set -euo pipefail
umask 0077
fail() { printf '%s\n' "$1" >&2; exit 1; }
operation=${WAN_HOST_OPERATION:?}
case "$operation" in inspect|install|resume|upgrade|verify|diagnose|owner-access|recovery|recovery-copy|trial-prepare|trial-admit|trial-launch|trial-observe) ;; *) fail 'Invalid operation';; esac
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
    -o ConnectTimeout=15 -o ServerAliveInterval=15 -o ServerAliveCountMax=3
    -o ControlMaster=auto -o ControlPersist=60 -o ControlPath="$temp_dir/control")
if [[ "$operation" == diagnose ]]; then
    ssh "${ssh_options[@]}" "root@$host" 'bash -s' <<'REMOTE'
set -euo pipefail
journalctl -u wan-controller --since "30 minutes ago" -o cat --no-pager | python3 -c 'import sys; print("".join(line[line.index("WAN_SESSION_REJECT "):] for line in sys.stdin if "WAN_SESSION_REJECT " in line))'
REMOTE
    exit
fi
if [[ "$operation" == owner-access ]]; then
    [[ -n ${WAN_ACCESS_PUBLIC_KEY:-} ]] || fail 'Encryption recipient required'
    printf '%s' "$WAN_ACCESS_PUBLIC_KEY" | base64 --decode > "$temp_dir/recipient.pem"
    openssl pkey -pubin -in "$temp_dir/recipient.pem" -text -noout | grep -Fx 'Public-Key: (3072 bit)' >/dev/null || fail 'RSA 3072 recipient required'
    scp "${ssh_options[@]}" "$temp_dir/recipient.pem" "root@$host:/root/wan-access-recipient.pem"
    ssh "${ssh_options[@]}" "root@$host" 'bash -s' <<'REMOTE'
set -euo pipefail
trap 'rm -f /root/wan-access-recipient.pem' EXIT
python3 -c 'import json; p=json.load(open("/etc/wan/studio-tokens.json")); assert len(p)==1 and list(p.values())==["john-hoyos"]; print(next(iter(p)),end="")' | openssl pkeyutl -encrypt -pubin -inkey /root/wan-access-recipient.pem -pkeyopt rsa_padding_mode:oaep -pkeyopt rsa_oaep_md:sha256 | base64 -w0
printf '\n'
REMOTE
    exit
fi
if [[ "$operation" == recovery || "$operation" == recovery-copy ]]; then
    if [[ "$operation" == recovery ]]; then
        scp "${ssh_options[@]}" deployment/host_acceptance.py "root@$host:/root/wan-host-acceptance.py"
        ssh "${ssh_options[@]}" "root@$host" 'cd /opt/wan/current; PYTHONPATH=/opt/wan/current WAN_SOURCE_ROOT=/opt/wan/current /opt/wan/venv/bin/python /root/wan-host-acceptance.py host'
    fi
    mkdir "$temp_dir/acceptance"
    scp -r "${ssh_options[@]}" "root@$host:/var/lib/wan/acceptance-20261116/backup" "root@$host:/var/lib/wan/acceptance-20261116/workflow.json" "root@$host:/var/lib/wan/acceptance-20261116/result.json" "$temp_dir/acceptance/"
    python3 -m venv "$temp_dir/venv"
    "$temp_dir/venv/bin/pip" install --require-hashes --only-binary=:all: -r deployment/hosting/requirements.lock
    "$temp_dir/venv/bin/python" -m deployment.host_acceptance off-host --directory "$temp_dir/acceptance"
    cp "$temp_dir/acceptance/result.json" "$temp_dir/acceptance/off-host-result.json" "$RUNNER_TEMP/"
    scp "${ssh_options[@]}" "$temp_dir/acceptance/off-host-result.json" "root@$host:/var/lib/wan/acceptance-20261116/off-host-result.json"
    exit
fi
if [[ "$operation" == trial-* ]]; then
    [[ "$operation" == trial-observe ]] || ssh "${ssh_options[@]}" "root@$host" "test \"\$(git -C /opt/wan/current rev-parse HEAD)\" = '$GITHUB_SHA'"
    guard_run=''
    if [[ "$operation" == trial-launch ]]; then
        ssh "${ssh_options[@]}" "root@$host" 'cat /var/lib/wan/live-trial-20261116/guard-ready.json' > "$temp_dir/guard.json"
        guard_run=$(python3 -c 'import json,sys; v=json.load(open(sys.argv[1]))["run_id"]; assert isinstance(v,str) and v.isdigit(); print(v)' "$temp_dir/guard.json")
        GUARD_RUN="$guard_run" python3 - <<'PY'
import json, os
from urllib.request import Request, urlopen
run=os.environ['GUARD_RUN']
url='https://api.github.com/repos/hoyosgarciajohn-png/wan-video-generation/actions/runs/'+run
req=Request(url,headers={'Authorization':'Bearer '+os.environ['GH_TOKEN'],'Accept':'application/vnd.github+json'})
with urlopen(req,timeout=20) as response: value=json.load(response)
assert value['status']=='in_progress' and value['event']=='workflow_dispatch'
assert value['path']=='.github/workflows/deadline-guard.yml' and value['head_sha']==os.environ['GITHUB_SHA']
print('INDEPENDENT_GUARD_RUNNING_VERIFIED')
PY
    fi
    ssh "${ssh_options[@]}" "root@$host" "cd /opt/wan/current; WAN_VERIFIED_GUARD_RUN='$guard_run' /opt/wan/venv/bin/python -u -m deployment.first_trial '${operation#trial-}'"
    exit
fi
if [[ "$operation" == inspect ]]; then
    ssh "${ssh_options[@]}" "root@$host" 'set -eu; hostname; uname -m; . /etc/os-release; printf "%s\n" "$PRETTY_NAME"; free -m; df -h /; cloud-init status --long; ssh-keygen -lf /etc/ssh/ssh_host_ed25519_key.pub -E sha256; test ! -e /opt/wan/current; test ! -e /var/lib/wan; printf "FRESH_HOST_ACCESS_PASS\n"'
    exit
fi
if [[ "$operation" == install || "$operation" == upgrade ]]; then
    [[ $(git rev-parse HEAD) == "$GITHUB_SHA" ]] || fail 'Source mismatch'
    if [[ "$operation" == install ]]; then
        [[ -n ${RUNPOD_CLEANUP_TOKEN:-} ]] || fail 'Missing cleanup secret'
    fi
    (cd apps/studio && npm ci --no-audit --no-fund && npm run build)
    git diff --quiet && git diff --cached --quiet || fail 'Modified source'
    git archive --format=tar.gz HEAD > "$temp_dir/source.tar.gz"
    tar -czf "$temp_dir/git.tar.gz" .git
    tar -czf "$temp_dir/studio.tar.gz" -C apps/studio dist
    if [[ "$operation" == install ]]; then
        ssh "${ssh_options[@]}" "root@$host" 'test ! -e /opt/wan/current && test ! -e /var/lib/wan'
    fi
    ssh "${ssh_options[@]}" "root@$host" "mkdir -m 700 /root/wan-bootstrap-$GITHUB_SHA"
    scp "${ssh_options[@]}" "$temp_dir/source.tar.gz" "$temp_dir/git.tar.gz" "$temp_dir/studio.tar.gz" "root@$host:/root/wan-bootstrap-$GITHUB_SHA/"
    # No shell tracing, secret artifacts or token output. Secret travels only in SSH stdin.
    if [[ "$operation" == install ]]; then
        printf '%s' "$RUNPOD_CLEANUP_TOKEN" | ssh "${ssh_options[@]}" "root@$host" "umask 077; cat > /root/wan-bootstrap-$GITHUB_SHA/runpod-token"
        unset RUNPOD_CLEANUP_TOKEN
        ssh "${ssh_options[@]}" "root@$host" "bash -s -- '$GITHUB_SHA' '$hostname'" < deployment/hosting/bootstrap-host.sh
    else
        ssh "${ssh_options[@]}" "root@$host" "bash -s -- '$GITHUB_SHA'" < deployment/hosting/upgrade-host.sh
    fi
fi
if [[ "$operation" == resume ]]; then
    # Only the observed pre-venv ownership failure from run 43793913368.
    # The already uploaded source/build remain bound to that exact reviewed SHA.
    ssh "${ssh_options[@]}" "root@$host" "bash -s -- 'e5cdd4fb0a138d44f53b40e62ee39b215c30f5c6' '$hostname' resume" < deployment/hosting/bootstrap-host.sh
fi
ssh "${ssh_options[@]}" "root@$host" "bash -s -- '$hostname'" < deployment/hosting/verify-host.sh
curl --fail --silent --show-error --retry 10 --retry-delay 6 --retry-all-errors "https://$hostname/healthz"
printf '\nEXTERNAL_HTTPS_PASS\n'
