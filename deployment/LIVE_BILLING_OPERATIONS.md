# Live billing and resource closure

This is the operator contract for the execution integration. No real Runpod bill,
signing key, resource or project spending approval was obtained in this batch.
Automated evidence uses fictional amounts and mocked provider responses.

## Authority and evidence

Owner approval authorizes a bounded project expenditure. Host acceptance certifies
the operator's deployment review. Billing authority reports observed charges and
final reconciliation. Install their keys separately; none is a worker credential.
Never accept a worker's estimated cost as an authoritative billing receipt.

A signed billing receipt proves the installed billing key holder authenticated
those exact terms. It is not a signature from Runpod and does not independently
prove the charge. The trusted reconciler must retain the underlying provider
evidence and verify its resource/project mapping before issuing a receipt. No
public client should be able to choose an amount and mark a reservation settled.

Runpod's [Pod billing history](https://docs.runpod.io/api-reference-v2/billing/get-pod-billing-history)
returns time-bucketed GPU/CPU/disk/total amounts and query metadata. Requested
windows can expand to bucket boundaries. The documented response does not supply
a final-invoice closure signal. Therefore a successful query, empty result or
unchanged recent total must not automatically settle a job. Overlapping queries
must not be counted twice. This integration's signed receipts are a delegated
reconciliation boundary; automated provider billing collection remains separate.

## Reconciliation procedure

1. Resolve the provider Pod ID from the durable job record. Match it to the correct
   account, owner, project and batch. Retain evidence outside source control.
2. Reconcile the covered billing interval and currency. Convert monetary values
   using decimal arithmetic and an explicit cents policy; do not round each poll
   independently or sum repeated snapshots. The ledger consumes integer USD cents.
3. Submit a uniquely identified signed charge receipt. A retry must retain its
   original identity and content. A changed amount requires the documented new
   correction/charge path, not replacement of an old receipt.
4. Keep the remaining reservation while compute allocation, cleanup or final
   billing is uncertain. Stop scheduling additional work when observed spending
   and outstanding liabilities exhaust the project cap.
5. Verify resource termination through the independent cleanup process. Then
   reconcile the final cumulative amount using the documented settlement receipt.
   Provider absence alone is insufficient to settle. A final receipt cannot erase
   earlier recorded charges.
6. Record later charges even after settlement or an overrun. Alert the operator
   and block additional expenditure where required. A newer owner grant must not
   reset historical project spending.

The first implementation preserves nonnegative charge history. Do not disguise
credits or refunds as negative charge receipts or reduce settled history by
editing the database. A reviewed adjustment mechanism is required before applying
such corrections to available budget.

## Independent cleanup

The cleanup host must run outside the GPU and hold only the provider permissions
needed for its role. Keep durable batch/resource identity available across restart.
An expired grant, revoked owner approval, expired worker token, exhausted cap or
changed application source must not prevent reconciliation and termination of an
already allocated resource. Those conditions must prevent a new allocation.

Do not recreate a Pod after an ambiguous create response. Reconcile the original
request and preserve its liability. Do not interpret HTTP timeout or a partial
inventory as absence. An acknowledged delete still needs the adapter's subsequent
absence checks. Escalate unresolved cleanup to the designated operator.

This code supplies callable lifecycle operations; deploying and supervising the
independent monitor is an infrastructure task. An unstarted watchdog cannot stop
charges. Document its host, polling interval, restart policy, alert destination,
and recovery drill before permitting the first GPU launch.

## Cost scope

The ledger enforces admission and launch decisions against recorded liabilities;
it is not a provider-level hard spending stop. Delayed billing, network outages,
startup, retries and termination delay can cause actual charges to exceed an
estimate. Include those possibilities in the owner's approved envelope.

Retained network/model volumes and other shared resources require their own
allocation and retention policy. Terminating a Pod does not authorize deleting a
shared volume. Establish how storage, transfer and build costs count against the
total project allowance before launch; do not describe untracked costs as zero.

Actual owner spending terms, verified image/host/storage evidence, reconciler
credentials, live invoice ingestion and observed cleanup remain operational inputs.
No test receipt in the repository is an approval to use John's account.
