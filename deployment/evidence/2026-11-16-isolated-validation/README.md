# Isolated validation authorized while support reconciles the old request

Owner instruction: “we do not need to wait. we can make a new test in the mean time”.
This authorizes one fresh isolated one-second test and its necessary deployment,
using the existing $5 total / 1800 seconds / one create / one render envelope.
The exact historical unknown request retains its cleanup obligation and $4 reservation.
The persistent cleanup process stays alive across the source upgrade. The separate
new deadline guard also deletes any late allocation for the old exact request.

Baseline: 532f1025beba94b9a4218a1cab19d0c826fed3a2. Installed before upgrade: 42b3e993.
Contract: 0.1.0. No new Pod or runtime authority at this implementation checkpoint.

Verification on fictional data:
- 172 root tests passed in 34.261 seconds.
- 46 deployment, guard, hosting and exact historical-exception tests passed in 2.518 seconds.
- Contract validation, shell syntax and git diff whitespace checks passed.
- Normal backup/restore eligibility is unchanged. The private maintenance checkpoint
  preserves the unresolved record and is not an automatically restorable bundle.

Live deployment, run IDs, output and cleanup result will be appended after execution.

## Deployment

PR #78 merged as 3a2f0cafd420a50fc2b744dc0490541f52cbbf87.
Upgrade run 43926416349 / job 133506978641 succeeded at 18:13:08 UTC.
The installed source is exactly that merge. All three services are active/enabled,
SQLite integrity and internal/external HTTPS checks passed. Cleanup heartbeat
still lists only 249c50635ec84ac38cef0eb66232efed as unresolved, with three historical
live jobs and no billing reservations released. Provider authentication GET passed.
The private pre-upgrade checkpoint is under /root/wan-bootstrap-3a2f0cafd420a50fc2b744dc0490541f52cbbf87/pre-upgrade.

Capacity checks after upgrade fluctuated: one eligible EU-RO-1 location briefly
reported LOW, followed by global NONE. No admission or POST at this checkpoint.

Final capacity checks returned NONE three times for one Secure RTX 4090 with
CUDA >=12.8. Complete inventory is empty. No new preparation, admission, create or
render took place. The new test remains unconsumed; support is no longer its gate.
Fresh capacity is required next. This evidence update remains on a documentation
branch so main continues to match the installed operator source for dispatch.

## Resumed progression

John instructed the one-second GPU test when capacity becomes available, followed
by five seconds. Preparation run 43930617081 / job 133521716501 succeeded at
18:36:46 UTC, project project-bad45576e6c840cfbf3f4c633c8e3f87, source 3a2f0ca,
US-TX-3, $0.89/hour. This is preparation only, with no admitted batch or provider
create. Texas then disappeared while EU-RO-1 and EUR-IS-1 appeared. A targeted
operator correction refreshes location/source signatures only before authority
registration, retaining earlier preparation evidence and the same bounded scope.

Admission correction verification: 172 root tests passed in 38.150 seconds; 47
targeted deployment/guard/hosting tests passed in 1.666 seconds. Shell syntax and
whitespace checks passed. No provider credentials or network used in tests.
