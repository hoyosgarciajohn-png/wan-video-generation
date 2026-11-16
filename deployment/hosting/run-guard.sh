#!/usr/bin/env bash
# This runner can only observe/delete the exact authorized Runpod request.
set -euo pipefail
umask 0077
[[ ${GITHUB_REF:-} == refs/heads/main ]]
case "${WAN_TRIAL:-first}" in
    first) trial_dir=/var/lib/wan/live-trial-20261116 ;;
    diagnostic) trial_dir=/var/lib/wan/diagnostic-trial-20261116 ;;
    repair) trial_dir=/var/lib/wan/repair-trial-20261116 ;;
    validation) trial_dir=/var/lib/wan/validation-trial-20261116 ;;
        fallback) trial_dir=/var/lib/wan/fallback-trial-20261116 ;;
        allocation) trial_dir=/var/lib/wan/allocation-trial-20261116 ;;
    *) exit 1 ;;
esac
task_dir=$(mktemp -d)
guard_pid=''
trap '[[ -z "$guard_pid" ]] || kill "$guard_pid" 2>/dev/null || true; rm -rf "$task_dir"' EXIT
printf '%s\n' "${WAN_HOST_SSH_KEY:?}" > "$task_dir/key"
unset WAN_HOST_SSH_KEY
ssh-keyscan -T 15 -t ed25519 64.225.114.46 > "$task_dir/known_hosts" 2>/dev/null
[[ $(ssh-keygen -lf "$task_dir/known_hosts" -E sha256 | awk '{print $2}') == SHA256:aU+cxUkky0P7tyOuS7JQjevb7gLGxeN/kjMVfQIDTr4 ]]
export WAN_GUARD_READY_FILE="$task_dir/ready.json"
python3 -m deployment.deadline_guard &
guard_pid=$!
for _ in {1..30}; do
    [[ ! -f "$WAN_GUARD_READY_FILE" ]] || break
    kill -0 "$guard_pid"
    sleep 1
done
[[ -f "$WAN_GUARD_READY_FILE" ]]
scp -F /dev/null -i "$task_dir/key" -o IdentitiesOnly=yes -o BatchMode=yes \
  -o StrictHostKeyChecking=yes -o UserKnownHostsFile="$task_dir/known_hosts" -o ConnectTimeout=15 \
  "$WAN_GUARD_READY_FILE" "root@64.225.114.46:$trial_dir/guard-ready.json"
printf 'INDEPENDENT_GUARD_READY_DELIVERED\n'
# Keep launch readiness current while this independent guard is alive. A
# delivery failure after startup must never stop deadline enforcement.
while kill -0 "$guard_pid" 2>/dev/null; do
    sleep 30
    kill -0 "$guard_pid" 2>/dev/null || break
    if ! scp -F /dev/null -i "$task_dir/key" -o IdentitiesOnly=yes -o BatchMode=yes \
      -o StrictHostKeyChecking=yes -o UserKnownHostsFile="$task_dir/known_hosts" -o ConnectTimeout=15 \
      "$WAN_GUARD_READY_FILE" "root@64.225.114.46:$trial_dir/guard-ready.json"; then
        printf 'GUARD_RECEIPT_DELIVERY_UNAVAILABLE; deadline watch continues\n'
    fi
done
wait "$guard_pid"
guard_pid=''
