# Hosting and automatic cleanup

Updated November 15, 2026 (owner local date). **Not deployed.** Runpod has $10
prepaid credit, zero observed Pods, saved private registry credential wan-ghcr-pull,
and private template lehfc5qf3s. RUNPOD_CLEANUP_TOKEN is saved in GitHub Actions;
its Pod read access passed run 43784863537. No credential is installed on a
controller. John approved one DigitalOcean Basic Regular bundled server: 1 vCPU,
2 GiB RAM, 50 GiB SSD, $12/month plus $2.40/month weekly backups, before tax.
This replaces the earlier free-only direction. Account access is currently blocked
at the DigitalOcean sign-in page; no server was created or installed.
See [the approved hosting decision](HOSTING_DECISION.md) and
[non-executable configuration](digitalocean-controller-proposal.json).

## Approved starting deployment shape

Use Linux amd64 with Python 3.11+, Git, FFmpeg/ffprobe, persistent disk and Caddy
TLS. Build Studio with Node 22 outside the small host. Keep the full reviewed Git
checkout for source-bound admission; the earlier staging container lacks it.
The selected 1 vCPU / 2 GiB / 50 GiB configuration still needs actual memory,
load and recovery acceptance. It is not a verified capacity claim for 30-minute
production exports. Existing exports run one at a time; measure upload concurrency
and keep the independent cleanup process healthy under load. Do not automatically
upgrade capacity or add storage. The current amd64 installer fits this architecture.

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
   `wan` service user and `/var/lib/wan` owned by it. Build Studio off-host with `npm ci`
   and `npm run build` in `apps/studio`, then transfer the verified output.
   Verify installed FFmpeg/ffprobe.
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
The secret is installed and its read access is verified; the deadline workflow
itself is not scheduled or running. Deletion and actual deadline handling remain unverified.
Cancellation, an unavailable runner or provider outage can defeat this fallback;
the primary monitor and external operational alerting remain necessary.

The two monitors retry **cleanup only**, never rendering or resource creation.
Polling/HTTP delays can overrun a deadline and provider billing may lag. The $5
reservation is an admission limit, not a guaranteed provider hard billing stop.
Authoritative bill retrieval, alert delivery and installed live authority remain
unverified. Final billing must be reconciled before another trial.

## Fresh-host installer

`install-services.sh` automates the final service/configuration installation on an
approved **fresh dedicated Linux amd64/systemd host**. Before running it:

1. Install Python 3.11+, venv, Git, FFmpeg/ffprobe and the official Caddy package.
   The package starts a default Caddy service; stop/disable that default service
   on this new host so the dedicated WAN proxy can bind ports 80/443.
2. Create the dedicated `wan` system user/group. Place the complete reviewed
   checkout at `/opt/wan/current`, checked out to the exact merged release SHA.
   Do not give the service user write access to source or the virtual environment.
   Build Studio from package-lock with Node 22 on the build host.
   Copy verified build assets to apps/studio/dist. No live credential belongs in
   the source checkout or cloud-init/user-data.
3. Install the hash-locked hosting dependencies into `/opt/wan/venv`. Create
   `/etc/wan` as root:wan mode 0750. Provision studio-tokens.json and runpod-token
   there as root:wan mode 0640, via the approved secret transfer. The installer
   issues no credentials and refuses to replace existing settings/state.
4. Set the approved DNS hostname to this server; permit only 80/443 publicly and
   restrict SSH to approved administration. Verify no other service uses 80/443.
5. From `/opt/wan/current`, run as root:
   `bash deployment/hosting/install-services.sh EXACT_REVIEWED_COMMIT APPROVED_HOSTNAME`.

The installer validates source, architecture, dependencies and private-secret
permissions; initializes cleanup/admission/execution tables **with no keys or
provider transport**; installs three systemd units; validates the dedicated Caddy
configuration; and starts the controller, cleanup process and HTTPS proxy.
Existing data/settings cause refusal; upgrades and restore use their own procedure.
A partial installation failure requires inspection, not removal of retained data.
It is source-prepared and syntax checked, not executed on a production host.

`deployment.initialize_host` fixes an installation gap: the default web application
did not create live cleanup tables. A fresh cleanup service would otherwise fail
before its first sweep. Initialization is repeatable and preserves existing data;
restored state still requires explicit database and assets paths. The default
web app remains fixture-only, and no provider creation route is enabled.

## Inputs still required

- DigitalOcean account sign-in; the $14.40/month pre-tax configuration is already
  approved. Inspect existing resources and verify actual capacity/checkout price
  and expected tax before creation. Do not repeat the initial approval request.
- Approved hostname and DNS control; no domain purchase is included.
- Host-side operator and cleanup credentials and installed live authority.
- Off-host recovery arrangement, monitor acceptance, exact image pull and model setup.

Funding, private-pull credential, and GitHub cleanup-secret creation are complete.
Do not repeat those requests or rotate credentials implicitly.

## Acceptance record

Seven host/cleanup tests and two independent-deadline tests use fictional data.
They cover HTTPS session cookies, origin/ownership rejection, traversal and
symlink escape, body limits, unhealthy readiness, process-independent cleanup,
provider outage recovery, lost create responses, exact resource scoping and
refusal to create compute. These checks are not deployed-service evidence.
Before launch record the real URL, TLS, persistent storage/restore evidence,
monitor process/run IDs, fresh READY record, exact private digest pull, installed
trust/configuration, model checksums and the approved one-attempt envelope.

Two new fictional initialization checks pass: empty-schema cleanup without network
or authority, repeat initialization with retained data, and restored-path refusal.
The new installer and proxy/initializer bytes are part of the source-bound planning
inventory. These checks do not establish a running service or shutdown acceptance.
