# Approved small DigitalOcean controller — November 15, 2026

Status: **APPROVED_AWAITING_ACCOUNT_SIGN_IN**. John selected the lower-cost
DigitalOcean option and intends to consider capacity upgrades only if needed.
The approval replaces the earlier free-only controller direction. It does not
revive the former $24 server or $32 monthly ceiling.

## Exact approved purchase

One dedicated `wan-controller-01` CPU Droplet: **Basic Regular bundled**, Linux
amd64, Ubuntu 24.04 LTS preference, 1 vCPU, 2 GiB RAM, 50 GiB SSD, 2,000 GiB
monthly outbound allowance. Use an available US region after checking the account.

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

## Observed account state

No DigitalOcean management integration was returned by current plugin discovery.
The connected Chrome session opened https://cloud.digitalocean.com/ and reached
https://cloud.digitalocean.com/login. The email/password fields are blank. The
page is retained for the owner to sign in. Account resources, region, capacity,
payment state and checkout are unverified. No server or subscription was created.

## Installation sequence after sign-in

1. Inspect account/project inventory. Select one dedicated host and exact plan;
   enable weekly percentage-based backups and confirm the final price.
2. Establish scoped host administration and HTTPS access. Do not put keys into
   user-data, repository content or screenshots. No domain purchase is included.
3. Build Studio outside this 2 GiB host. Install the reviewed source, hash-locked
   Python dependencies, FFmpeg/ffprobe and Caddy on the server. Keep model weights
   on Runpod; the CPU controller does not need the multi-gigabyte GPU image.
4. Start the separate controller, cleanup and proxy services using the fresh-host
   installer. Startup remains disarmed. Measure memory and disk on the actual
   host, including fictional upload/export and restart. Keep one export job at
   a time; tune request concurrency and service limits from measured evidence.
   Verify the cleanup monitor stays healthy during controller failure or load.
5. Verify HTTPS, authorization, durable media, consistent application backup and
   restore. Weekly disk backups do not by themselves prove SQLite recovery.
   Preserve old accepted takes; do not silently delete media to make space.
6. Install reviewed runtime authority and worker bootstrap. Require the primary
   cleanup service plus the independent GitHub guard to be ready for the real
   admitted scope before Runpod provisioning. Check included Actions allowance.
7. Use only the already approved $5 / 1,800-second / one-attempt Runpod trial for
   actual private image pull and Wan inference. Verify output retention, cleanup
   and billing. Do not retry rendering under this authorization.

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

This checkpoint records approval and deployment settings only. No runtime source,
credentials, other project, host, volume or GPU was changed. Documentation and JSON
consistency were checked; existing tests were not repeated. Actual installation,
TLS, shutdown, image pull and bill collection remain pending. Contract 0.1.0.

Published pricing references, checked November 16 UTC / November 15 owner local:

- https://www.digitalocean.com/pricing/droplets
- https://docs.digitalocean.com/products/backups/details/pricing/
- https://docs.digitalocean.com/products/droplets/details/pricing/
