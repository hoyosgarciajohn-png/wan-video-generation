# Runpod deployment preparation

Status: source preparation only. No host, registry image, volume, API credential,
GPU or public deployment has been provisioned. The worksheet has deliberately
empty owner values and cannot authorize a launch.

## API migration

Use the current [Runpod API v2](https://docs.runpod.io/api-reference-v2/overview).
The official [migration guide](https://docs.runpod.io/api-reference-v2/migrate-from-v1)
states that v1 retires November 15, 2026. v2 uses nested GPU/storage configuration
and paginated inventory; a host URL replacement alone is insufficient. Provider
reconciliation must inspect all inventory pages. A truncated or failed read is
not evidence that a resource is absent.

The [create reference](https://docs.runpod.io/api-reference-v2/pods/create-a-pod)
defines the container configuration. Network volumes must match the selected
data center. Use explicit storage mounts and no public Pod ports. The worker
makes outbound HTTPS requests to the controller. A persistent model cache and
durable worker journal are separate from the controller's authoritative media.

## Configuration worksheet

Copy `deployment/runpod-config.example.json` outside Git and fill in references
after the corresponding resources and approval exist. It is an operator worksheet,
not the raw provider body, not an environment file, and not consumed as authority.
Keep `execution_enabled` false; changing it has no effect on the application.
Never put secret values into this worksheet, a PR, a command argument or logs.

| Component | Required evidence | Current state |
|---|---|---|
| Build host | Linux amd64 Docker/runc; captured build and smoke logs | Unverified |
| GPU image | Successful pinned build; registry digest bound to built image | Missing |
| GPU placement | Catalog ID, data center, capacity and driver compatibility | Unselected |
| Model cache | Exact locked checkpoint files verified on selected volume | Missing |
| Worker state | Private writable journal/cache paths; restart recovery | Host unverified |
| Controller | Durable database/media, HTTPS, authentication, restore acceptance | Local source only |
| Cleanup monitor | Independent host, bounded polling, failure alert and recovery | Not deployed |
| Approval | Authenticated project cap, runtime, retry count and cost scope | Unspecified |
| Accounting | Observed usage and final bill reconciliation | Not integrated live |

The model mount must contain the locked files, not just a matching directory
name. Read-only model handling must be verified on the chosen runtime; do not
assume a provider mount option exists. Worker outputs under `/worker` must be
uploaded and verified by the controller before teardown. The controller database
and accepted media must never exist solely on the temporary Pod.

## Ordered activation work

1. Select an existing approved build host. Follow `BUILD_VERIFICATION.md` and
   preserve the immutable image identity and logs. Publish to an approved registry
   and verify the registry digest corresponds to the tested image. A digest-shaped
   string alone proves neither a build nor registry availability.
2. Choose a GPU/data center and model/journal storage. Check capacity and total
   cost before creating resources. Stage and verify the locked weights once;
   include image layers, cache, temporary files and outputs in disk sizing.
3. Deploy and verify the controller's durable storage, HTTPS and recovery.
   The existing loopback staging Compose file is not a public deployment recipe.
   Preserve its binding; do not expose the development server to the Internet.
4. Complete a separately reviewed live admission/authority factory. Bind the
   exact image, model, placement, scope, budget reservation and deadline to the
   canonical job. Never reuse simulation approvals or test links as live authority.
   The provider adapter alone does not supply this factory.
5. Provision the Runpod API key only to the trusted controller/cleanup service.
   Issue the worker a short-lived token scoped to its batch. Inject that token as
   `WAN_WORKER_TOKEN`, with `WAN_WORKER_API_URL` set to the verified controller
   origin. No Runpod account credential belongs on the GPU worker. Confirm the
   chosen secret injection method without recording resolved secret values.
6. Start the independent cleanup monitor before allowing dispatch. It must run
   outside the GPU, survive controller restarts, retry uncertain cleanup and alert
   on unresolved allocations. Worker exit is not proof of Pod termination. A local
   deadline cannot guarantee a hard provider billing ceiling during an outage.
7. With the owner's specific release and cost envelope approved, admit one
   fictional shot. The current CLI handles one claimed attempt per invocation;
   it is not a resident multi-shot worker loop. Keep this first run to one shot.
8. Observe verified output, provider termination and final charges. Preserve
   unresolved liabilities until billing settlement; only then schedule larger
   batches. Human creative acceptance remains pending until observed live.

The reviewed GPU image's entrypoint is `python -m workers.gpu.cli`. Its eventual
CMD arguments for one attempt are:

```text
worker --output-root /worker/output --input-root /worker/inputs --weights /models --result /worker/result.json
```

These arguments describe the existing worker interface; they are not a launch
command. The host still needs verified mounts, scoped credentials and live queue
authority. Do not add `--allow-local-http` to a cloud deployment.

## Cost and recovery controls

Terminate temporary compute after verified completion or deadline/cancellation.
Retained model/journal volumes may continue to incur storage charges; identify
their owner and retention separately. Do not delete a shared model volume during
Pod cleanup. Account for cold start, model verification, failed attempts, upload,
cleanup delay and retained storage in the approved cost scope. No current hourly
price or real per-clip cost has been established by these fictional checks.

On an ambiguous create response, reconcile the original scoped request; never
blindly resubmit. On delete timeout, retain cleanup liability and check again.
On restart, recover the durable job/resource identity before issuing work. On
credential expiry, use trusted reconciliation; the worker journal cannot simply
be replayed with a replacement token. Final bill ingestion and token rotation
still need their production integrations.

## Acceptance record

Record the reviewed commit, image and model hashes, approval reference, Pod ID,
timestamps, observed driver/VRAM, actual output checksum, cleanup confirmation,
compute/storage/transfer charges and remaining human acceptance. Keep secrets
and user media out of source control. A successful mocked HTTP response or an
offline preflight is not evidence of a real Runpod operation or Wan inference.
