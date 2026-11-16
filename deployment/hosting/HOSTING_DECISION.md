# Approved small DigitalOcean controller — November 15, 2026

Status: **APPROVED_AWAITING_SSH_ACCESS_CONFIRMATION**. John selected the lower-cost
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

## Observed account state

No DigitalOcean management integration was returned by current plugin discovery.
John completed sign-in. The connected Chrome session verified the My Team account,
the first-project project and an empty global Droplet inventory. A primary payment
method exists. No payment was attempted. The prepared form selects Ubuntu 24.04
LTS x64, SFO2, Basic Regular s-1vcpu-2gb, quantity one, and weekly percentage
backups. Its displayed total is $14.40/month; tax is not itemized. Extra storage
and the managed database remain unchecked. Free monitoring is selected.

A dedicated ed25519 key named wan-controller-deploy was generated locally with
private-file mode 0600. Its fingerprint is
SHA256:GGPDVk0v1xgocnC0P1OCvmSM/h9VggrKxAUDIbF1iKA. The public-key form is prepared
but unsubmitted. Confirmation is pending before registering this new administrator
access and storing the private part as encrypted WAN_HOST_SSH_KEY in the private
hoyosgarciajohn-png/wan-video-generation repository. Use the key only for the WAN
controller; do not select the unrelated existing SUMAN staging key. No private
key is in source, documents or screenshots. No host or subscription was created.

## Remaining installation sequence

1. Obtain the concrete administrator-access confirmation, register the prepared
   public key, and retain the private part in the approved encrypted secret store.
   Recheck the existing prepared checkout before creating exactly one host.
2. Establish scoped host administration and HTTPS access. Do not put private keys into
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

This checkpoint records account inspection and prepared deployment settings. A new
local key pair exists but no external access was granted. No runtime source,
other project, host, volume or GPU was changed. Documentation and JSON
consistency were checked; existing tests were not repeated. Actual installation,
TLS, shutdown, image pull and bill collection remain pending. Contract 0.1.0.

Published pricing references, checked November 16 UTC / November 15 owner local:

- https://www.digitalocean.com/pricing/droplets
- https://docs.digitalocean.com/products/backups/details/pricing/
- https://docs.digitalocean.com/products/droplets/details/pricing/
