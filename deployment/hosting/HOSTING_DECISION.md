# Approved small DigitalOcean controller — November 15, 2026

Status: **HOST_INSTALLED_DISARMED**. John selected the lower-cost
DigitalOcean option and intends to consider capacity upgrades only if needed.
The approval replaces the earlier free-only controller direction. It does not
revive the former $24 server or $32 monthly ceiling.

## Exact approved purchase

One dedicated `wan-controller-01` CPU Droplet: **Basic Regular bundled**, Linux
amd64, Ubuntu 24.04 LTS preference, 1 vCPU, 2 GiB RAM, 50 GiB SSD, 2,000 GiB
monthly outbound allowance. SFO2 is selected and available in the inspected form;
the same Basic Regular plan was unavailable in NYC3.

| Item | Monthly published amount |
|---|---:|
| Server | $12.00 |
| Weekly percentage-based backups (20%) | $2.40 |
| Subtotal before expected tax | **$14.40** |

This is the initial configuration John approved. Do not ask him to approve it
again. Inspect existing resources first to avoid duplicate allocation. Confirm
actual regional capacity, plan and checkout price before creating anything.
No larger plan, v5 configuration, extra volume, managed database, paid builder,
new domain or other paid add-on is included. Future capacity upgrades have no
approved price yet. A budget alert is not a provider-enforced account spending cap.
Powering off a Droplet does not stop billing; its resources remain reserved.

The non-executable proposal is [digitalocean-controller-proposal.json](digitalocean-controller-proposal.json).
It records the approval and unresolved installation inputs; it does not create
resources, contain credentials or enable Runpod dispatch.

## Observed installed state

John confirmed the concrete dedicated SSH access with “yes”. One host was created
in My Team / first-project (9bf0133f-d248-4eef-a8c8-229efe4170f6): Droplet 619703894,
wan-controller-01, SFO2, 64.225.114.46, Ubuntu 24.04.5 LTS amd64. Weekly backups
are enabled for Wednesday 04:00–08:00 UTC; the first scheduled backup is pending.
Server billing is active at the approved recurring rate; accrued billing is not
retrieved. No extra host, volume, database or domain purchase was added.

The WAN public key is registered. Its private part is stored as encrypted
WAN_HOST_SSH_KEY in the private hoyosgarciajohn-png/wan-video-generation repository.
The unrelated SUMAN key was not selected. SSH is key-only, port 22 is rate limited,
HTTP/HTTPS are public, and application port 8080 is loopback-only. The client-key
fingerprint is SHA256:GGPDVk0v1xgocnC0P1OCvmSM/h9VggrKxAUDIbF1iKA. The host-key
fingerprint is SHA256:aU+cxUkky0P7tyOuS7JQjevb7gLGxeN/kjMVfQIDTr4 (TOFU at the
provider-console IP, then pinned strictly on all later cloud operations).

Controller, cleanup and Caddy services are active and enabled. Installed source
is 42dbdc127b299b7e11e674630bef8683473f5a7a. Studio was built off-host using Node22.
Private owner token and cleanup credential are installed under /etc/wan with
restricted permissions; neither is in source or logs. The owner token has not yet
been delivered. Live spending authority is absent and paid dispatch is disabled.

https://wan-64-225-114-46.sslip.io serves valid HTTPS without a domain purchase.
Cloud verification 43795476474 passed service, firewall, SQLite, fresh cleanup,
Runpod GET and external HTTPS checks. Studio now loads after the strict-CSP schema
fix, but owner access is not accepted: the browser session route returned 403.
Direct same-origin unauthenticated HTTP returns 401, and cross-site returns 403.
Investigate browser request provenance; preserve authentication/origin protections.

See ../evidence/2026-11-16-controller-hosting/README.md for actual run outcomes,
including failed partial checks. There are zero live-job bindings. Runpod GET
success does not prove deletion. No GPU has been launched.

## Remaining sequence

1. Resolve the browser session rejection and securely hand off the existing owner
   token. Do not implicitly rotate credentials or publish secrets in artifacts.
2. Measure fictional upload/export load and cleanup freshness on this actual
   2 GiB host. Keep one export at a time. Verify retained media across restart.
3. Verify consistent restore and off-host recovery. The pre-upgrade backup on the
   same host and scheduled provider backups do not establish recovery acceptance.
4. Install reviewed live authority and worker bootstrap/model paths. Require both
   primary cleanup and a ready independent deadline guard for the admitted scope.
5. Use only the already approved $5 / 1,800-second / one-attempt trial to verify
   actual image pull, Wan inference, output retention, shutdown and billing.

## Capacity and upgrade decision

2 GiB is a starting hypothesis for low-volume controller work, not a verified
capacity claim for 30-minute production video exports. The current export runner
serializes jobs and validates a 320x180 fixture profile; production export quality
and capacity remain separate work. The host also handles media transfer, so
concurrency and temporary disk use must be measured before broader access.

Collect baseline/peak RAM, swap/OOM events, CPU saturation, request latency,
cleanup heartbeat freshness and free disk during the actual fictional rehearsal.
If those show insufficient capacity, prepare a measured higher-tier proposal.
First remove avoidable build work and bound concurrency; do not sacrifice cleanup
reliability. Never automatically resize, add a volume or expand the GPU trial.

## Previous alternatives and evidence boundary

Existing Vercel / ChatGPT Sites and Supabase accounts were verified in the previous
inventory. Reuse requires adapting the persistent-file/process backend. Oracle
Always Free remains an alternate requiring ARM acceptance and available capacity;
Windows requires reliable power/network access. These routes are not the selected
installation after John's latest approval.

This checkpoint records an installed CPU host with verified HTTPS and cleanup
heartbeat. It does not establish owner login, workload capacity, off-host restore,
real image pull, GPU shutdown or billing collection. Contract 0.1.0 is unchanged.
The $5 GPU trial remains unused. No larger plan or add-on is authorized.

Published pricing references, checked November 16 UTC / November 15 owner local:

- https://www.digitalocean.com/pricing/droplets
- https://docs.digitalocean.com/products/backups/details/pricing/
- https://docs.digitalocean.com/products/droplets/details/pricing/
