# Bounded live trial operations

The original five-second trial is consumed. John separately approved one additional
one-second diagnostic on November 16, 2026. Each scope has its own $5 ceiling,
1,800 seconds from admission, one Pod-create attempt and one render attempt.
The dedicated controller's monthly cost is separate. Neither scope authorizes a retry.

The workflow `trial` input defaults to `first`; select `diagnostic` explicitly for
the approved additional trial. The CLI equivalent is `--trial diagnostic`.
The new project, grant, operator directory, signing keys and idempotency key remain
separate. Historical first-trial billing and evidence must never be reset or reused.

1. Finish hosted and independent recovery verification. The copy-only operation preserves the successful original rehearsal and copies its independent restore receipt back to the host.
2. Upgrade the existing controller to the reviewed release. `trial-prepare` checks the immutable published build, fresh RTX 4090 quote from the connected Runpod account (at most $1/hour, at most 180 seconds old), cleanup heartbeat and recovery receipts, then creates one project and private owner/host/billing keys. It enables worker reception without exposing admission, provisioning or provider credentials through the web API.
3. `trial-admit` creates the one $4 Pod reservation and starts the original 30-minute deadline. The remaining $1 is a separately recorded allowance; this configuration uses only an 80GB ephemeral container disk and no network/persistent volume.
4. Start **Guard one Runpod deadline** with exactly the emitted scope, batch and deadline. Its separate runner authenticates a provider read, starts its watch and transfers a fresh readiness receipt over pinned SSH. It cannot create Pods. Do not cancel that runner during the trial.
5. `trial-launch` verifies that the exact guard run is in progress at the same reviewed commit, checks its fresh receipt and rechecks GPU price/availability before the single create. An ambiguous result is reconciled through GET only. The root operator monitors the attempt; the persistent cleanup service remains independent of both it and the web process.
6. The existing private image downloads only the pinned, checksummed Wan weights, then runs its exact worker command. Image pull and model download consume the original deadline. Only the scoped worker token enters the Pod; inbound ports stay closed. No model-license or generation-API charge is introduced.
7. Completed media is transferred to the controller before cleanup. Terminal state or deadline triggers deletion and a confirming provider read. The separate runner continues reconciling for five minutes after the deadline to catch late allocation. No second attempt is automatic.
8. Read the exact Pod billing through the existing connected Runpod account and pass its timestamped JSON into `trial-observe`. The operator ingests cumulative increases from that record. The cleanup key cannot read catalog or billing and is not broadened. Automatic application-side bill retrieval remains pending. A missing/lagging bill never becomes a zero-cost settlement; the reservation remains open until final billing is independently confirmed.

`trial-observe` can safely inspect/reconcile the same attempt after an operator interruption. It never issues a fresh create. If cleanup is unresolved, use the exact bound Pod identity and preserve the reservation; never start another attempt.

The first trial's private image pull, pinned model download, worker claim and
deadline deletion are verified; inference failed before committing a take.
See ../evidence/2026-11-16-first-live-trial/README.md. Recovery uses separate synthetic
media. Failure closure, safe stage diagnostics and stronger guard readiness are now
installed in controller `8e07ba3`; the rebuilt private image ends `f993b`.

The additional diagnostic was admitted at 05:42:07 UTC on November 16 with fixed
deadline 06:12:07 UTC. Its sole Pod is `hzprkb5xllm8p0`. Follow the exact terminal
result in ../evidence/2026-11-16-diagnostic-trial/README.md; do not rerun its
prepare/admit/launch operations. `trial-observe --trial diagnostic` remains the
inspection and connected billing import path. The source proposal is a validated
description, not an executable grant; its approved status does not reset the
durable single-attempt runtime ledger.
