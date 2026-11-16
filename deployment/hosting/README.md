# Hosting and automatic cleanup

Prepared November 15, 2026 (owner local date). **Not deployed.** The Runpod account
has no Pods, a displayed balance of $0, and no container registry credential.
The connected Vercel account has no matching WAN project. No compatible existing
Linux controller host or approved recurring hosting expense has been established.

## Selected deployment shape

Use a Linux amd64 CPU host with Python 3.11+, Node 22 for the Studio build, Git,
FFmpeg/ffprobe, persistent disk and Caddy TLS. Start with 2 vCPU, 4 GB RAM and
40 GB disk for the trial. This is not a capacity claim for 30-minute production
exports. Retain a complete reviewed Git checkout for source-bound admission;
the earlier local-staging container does not contain that checkout.

The new Waitress 3.0.2 WSGI adapter binds only to 127.0.0.1:8080, behind Caddy.
It preserves strict Host/Origin checks, secure cookies, scoped media, bounded
uploads and streamed downloads. One process keeps current in-memory sessions
consistent; restarting it requires signing in again. Jobs/media use SQLite and
the persistent asset directory. It starts the existing fixture/export runners.
Its default entry point **does not install live admission or provider authority**.
The trusted live runtime still needs installation and source/build/host acceptance
before the GPU trial. There is no public provider-create HTTP endpoint.

## Install on an approved host

1. Check out the reviewed release under `/opt/wan/current`; create a dedicated
   `wan` service user and `/var/lib/wan` owned by it. Build Studio with `npm ci`
   and `npm run build` in `apps/studio`. Verify installed FFmpeg/ffprobe.
2. Create `/opt/wan/venv` and install
   `python -m pip install --require-hashes --only-binary=:all: -r deployment/hosting/requirements.lock`.
3. Provision `/etc/wan/controller.env` from the example and install the existing
   owner-token map at its private file path. Use mode 0640 root:wan or tighter.
   Never commit actual credentials or populate examples with real secrets.
4. Configure an owned DNS hostname, install the vendor's Caddy package, replace
   the example hostname and validate the Caddy configuration before enabling it.
   Expose only HTTPS/HTTP needed for TLS, and tightly restrict administration.
   Keep port 8080 loopback-only. There are no public GPU Pod ports.
5. Install the systemd controller unit. Check HTTPS, sign-in, protected requests,
   synthetic upload/export and restart persistence using fictional data.
6. Exercise the repository's backup/restore procedure onto a separate temporary
   state directory; verify checksums, owner boundaries and persistent media.
   Backups need an approved off-host destination and retention rule.
   If the state directory has `RESTORED.json`, explicitly set both
   `WAN_STUDIO_DATABASE` and `WAN_STUDIO_ASSETS` in the controller environment;
   point cleanup at that same `WAN_STUDIO_DATABASE`. Startup refuses to silently
   create a new empty database over a restored installation.

## Two cleanup layers

`wan-cleanup.service` runs a **separate process** from the web server. It scans
the existing durable live-job bindings every 15 seconds after each sweep and
terminates the exact resources on completion, cancellation, failure or deadline.
It uses a GET/DELETE-only transport and cannot create Pods. It recovers ambiguous
creation and uncertain deletion through inventory reconciliation. A failed API
call remains unresolved; empty inventory alone is not proof of an uncertain
create being absent. It does not delete model volumes or settle bills.

Install its private Runpod API credential only on the trusted cleanup host, using
`cleanup.env.example`; never reuse/export the connected app's token or place the
account key on the GPU. Start only after the reviewed live schema is initialized.
Monitor the status JSON and journal; missing/stale/error status is not readiness.
The included systemd unit restarts independently of the web process, but the two
services on one machine do not protect against loss of that machine or disk.

For the first trial, `.github/workflows/deadline-guard.yml` supplies a second-host
fallback. It requires a deliberately provisioned `RUNPOD_CLEANUP_TOKEN` repository
secret. After admission and **before provisioning**, start the manual workflow
with the exact owner/project scope, batch and original absolute deadline. Verify
its `READY` record and exact provider name before dispatch. It cannot extend the
30-minute envelope, create compute, or target other Pods. At the deadline it
terminates matching Pods and keeps reconciling for five minutes for late creates.
This workflow is prepared, not scheduled or running. No secret has been installed.
Cancellation, an unavailable runner or provider outage can defeat this fallback;
the primary monitor and external operational alerting remain necessary.

The two monitors retry **cleanup only**, never rendering or resource creation.
Polling/HTTP delays can overrun a deadline and provider billing may lag. The $5
reservation is an admission limit, not a guaranteed provider hard billing stop.
Authoritative bill retrieval, alert delivery and installed live authority remain
unverified. Final billing must be reconciled before another trial.

## Remaining owner/account inputs

| Input | Why needed | Scope |
|---|---|---|
| GHCR classic token with `read:packages` | Runpod private-image pull | Save directly in Runpod Container registry auth; do not paste into chat |
| Application/cleanup Runpod credential | Services must operate after this chat ends | Private host secret and separate-host watchdog secret |
| Existing compatible host, or new recurring hosting approval | HTTPS, persistent state and cleanup process | Separate from the $5 GPU trial |
| Runpod credit funding | Account currently displays $0 | A top-up is not the same as the approved compute consumption cap |

No new host/subscription/top-up has been purchased. A low-cost candidate is
Hetzner CX23 in Europe (2 vCPU, 4 GB, 40 GB): the official June 2026 adjustment
lists **$6.49/month before IPv4, backups and tax**. Its product page currently
reports unavailable capacity. Therefore this is a planning candidate, not a
deployable quote. Prefer a compatible existing host; approve the final available
host and total price before provisioning. Do not silently substitute ARM or a
larger paid plan. Public references checked November 15 local / November 16 UTC:

- https://docs.hetzner.com/general/infrastructure-and-availability/price-adjustment/
- https://www.hetzner.com/cloud/cost-optimized/
- https://docs.pylonsproject.org/projects/waitress/en/stable/arguments.html
- https://caddyserver.com/docs/caddyfile/directives/reverse_proxy
- https://docs.runpod.io/get-started/credentials

## Acceptance record

Seven host/cleanup tests and two independent-deadline tests use fictional data.
They cover HTTPS session cookies, origin/ownership rejection, traversal and
symlink escape, body limits, unhealthy readiness, process-independent cleanup,
provider outage recovery, lost create responses, exact resource scoping and
refusal to create compute. These checks are not deployed-service evidence.
Before launch record the real URL, TLS, persistent storage/restore evidence,
monitor process/run IDs, fresh READY record, exact private digest pull, installed
trust/configuration, model checksums and the approved one-attempt envelope.
