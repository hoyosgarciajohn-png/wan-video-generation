# Resumed controller deployment and worker preparation

Command Center / B06 issue #7; contract 0.1.0. November 16, 2026, approximately 00:09–00:18 Eastern time (05:09–05:18 UTC).

## Observed outcome

- [PR #64](https://github.com/hoyosgarciajohn-png/wan-video-generation/pull/64) failure closure, safe diagnostics and guard corrections are installed in controller release `45559974d44797e26fb543c6e5ff9e4f75344dcb`, together with [PR #65](https://github.com/hoyosgarciajohn-png/wan-video-generation/pull/65) backup compatibility fixes.
- Upgrade [43808383545](https://github.com/hoyosgarciajohn-png/wan-video-generation/actions/runs/43808383545) stopped before replacement: the old backup checker compared the entire GPU object against two keys and disallowed unsettled bills. No live data was altered by that failed run.
- Upgrade [43808938735](https://github.com/hoyosgarciajohn-png/wan-video-generation/actions/runs/43808938735) created a complete four-file backup and installed the corrected source, preserving private state. Only the copied backup revoked one approval and one worker credential. Its final check still expected an unused database and failed after deployment.
- [PR #66](https://github.com/hoyosgarciajohn-png/wan-video-generation/pull/66) corrects that verification. Successful [verify run 43809179887](https://github.com/hoyosgarciajohn-png/wan-video-generation/actions/runs/43809179887) uses `19c7d8fc537354a656e6f438d524dd66d5cfb410`, confirms installed source `4555997`, healthy enabled controller/cleanup/proxy services, external HTTPS, no active provider obligations, one retained historical live job and paid public dispatch disabled. It does not replace the service again.
- Owner Chrome sign-in was restored after restart with the existing encrypted token. Saved synthetic project and accepted take remain visible. No credential was exposed or rotated.
- Private worker rebuild [43808492420](https://github.com/hoyosgarciajohn-png/wan-video-generation/actions/runs/43808492420) succeeded; detailed immutable identity and independent artifact review are in [../2026-11-16-private-rebuild/README.md](../2026-11-16-private-rebuild/README.md).

## Billing and resources

Connected provider billing is arriving incrementally. Observation imported by [43808824454](https://github.com/hoyosgarciajohn-png/wan-video-generation/actions/runs/43808824454) reported $0.1475849028211087 total ($0.1457330510020256 GPU, $0.0018518518190830946 disk). The ledger conservatively records 15 cents with 385 cents of the original $4 reservation remaining. This is NOT final settlement; the earlier zero and seven-cent observations were incomplete. The separate $1 storage allowance remains unchanged. Automatic application-side bill collection is still pending.

No new Pod, render, network volume or paid service was created during this continuation. Connected provider inventory contains zero Pods. The one approved DigitalOcean host remains at $14.40/month before tax; actual accrued hosting/CI/registry charges were not retrieved. The first one-attempt trial remains consumed. The existing deadline deletion evidence is valid; the newly corrected immediate-failure cleanup behavior has fictional regression evidence, not a second live GPU demonstration.

## Validation and remaining work

Fourteen backup/live integration checks passed, including actual synthetic-media decode, unsettled billing recovery, copied-authority revocation, pending-cleanup rejection, failed-attempt closure and corrupt-reservation rejection. Eight hosting checks passed. Shell syntax, diff whitespace and four fictional verification-query cases passed. No broad tests were repeated without a relevant change.

The earlier independent synthetic restore remains proved. This release produced a valid post-trial backup; a separate off-host restore of this new snapshot has not been executed. Weekly provider backups are enabled, but their first completed snapshot and recurring offsite application backup are still unverified.

The new worker's Runpod pull, actual inference, durable generated output and creative review remain open. See [../../diagnostic-trial-proposal.json](../../diagnostic-trial-proposal.json) for a pending, disabled one-second diagnostic proposal. No fresh signing grant or launch authorization is installed for it. Do not reuse or reset the consumed first-trial state.
