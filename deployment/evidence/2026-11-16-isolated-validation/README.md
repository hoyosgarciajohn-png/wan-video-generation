# Isolated validation: explicit capacity rejection

Owner instruction: “we do not need to wait. we can make a new test in the mean time”.
This authorizes one fresh isolated one-second test and its necessary deployment,
using the existing $5 total / 1800 seconds / one create / one render envelope.
The exact historical unknown request retains its cleanup obligation and $4 reservation.
The persistent cleanup process stays alive across the source upgrade. The separate
new deadline guard also deletes any late allocation for the old exact request.

The entries below are chronological checkpoints. The final result supersedes earlier
statements that the new grant was unconsumed. `live-status.json` is the historical
18:14 UTC capacity snapshot; `allocation-result.json` is the final request outcome.

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

## Final live outcome — November 16, 18:52:46 UTC

PR #80 was merged as d30fa01aec7dc6bf50be8e5e2a950efb3c04fffc and deployed by
run 43931628684 / job 133525286064 at 18:42:48 UTC. All services and host checks
passed. Preparation was refreshed before registration to include EU-RO-1 and
US-TX-3. Admission 43931801108 / job 133525897137 at 18:43:32 UTC created batch
bee9e55b1d4a4f458771ad4ac69c3318 and fixed deadline 19:13:32 UTC.

Initial guard 43931920247 had no job and remained queued; GitHub displayed
“Failed to cancel workflow.” A single replacement guard 43932987270 / job
133530072729 delivered independent readiness at 18:50:21 UTC and was running
at the final evidence check. Both use the original fixed deadline and neither
can provision compute. Persistent host cleanup also remains active.

A fresh catalog quote showed EU-RO-1 LOW at $0.89/hour before launch. This catalog
does not filter host RAM; LOW is not a capacity reservation. The actual request
retained all requirements, including >=64GB host RAM. Launch run 43933406724 /
job 133531537501 issued exactly one create at 18:52:45 UTC (1:52:45 p.m. Eastern).
Runpod returned HTTP 400 with request ID
`req_c5b30a44-e3c4-4dd2-becf-5ad5c57063c9`:

> There are no longer any instances available with the requested specifications. Please refresh and try again.

The new redacted diagnostics retained the reason and explicitly classified the
outcome as rejected. Final state failed; cleanup confirmed; no Pod ID, zero worker
attempts, zero takes. The workflow's green success represents handled rejection,
not GPU-test success. See `allocation-result.json` for the structured result.

Complete provider inventory and audit search since 18:40 UTC were empty. Billing
18:00–19:00 UTC returned no records and zero totals; this is not final settlement.
No new GPU runtime occurred, but the $4 reservation remains retained. The older
repair request remains unresolved with its separate $4 reservation and monitoring.

The one-create scope is consumed and must not be rerun. Five seconds was not
started. An hourly read-only capacity watch is enabled, first scheduled for
2:49 p.m. Eastern; it cannot create Pods or reset consumed grants. A future
attempt needs a fresh isolated bounded authority. No tests were repeated for this
final evidence-only update; the 219 passing code checks above remain applicable.

- [Launch and provider response](https://github.com/hoyosgarciajohn-png/wan-video-generation/actions/runs/43933406724/job/133531537501)
- [Independent guard](https://github.com/hoyosgarciajohn-png/wan-video-generation/actions/runs/43932987270)
- [Deployed admission correction](https://github.com/hoyosgarciajohn-png/wan-video-generation/pull/80)
