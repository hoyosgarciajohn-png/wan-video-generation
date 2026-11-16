# Controller hosting decision — November 15, 2026

Status: prepared; owner hosting spend approval and account sign-in required.
No server, volume, backup plan, DNS record or additional credential was created.

## Recommended concrete configuration

DigitalOcean Basic **Regular bundled** Droplet, Linux amd64, Ubuntu 24.04 LTS,
2 vCPU, 4 GiB RAM, 80 GiB persistent SSD, one server, US region if that exact plan
is available. Name: `wan-controller-01`. Enable weekly provider backups (four
retained weekly copies). Start with the existing SQLite/asset layout and separate
controller, cleanup and Caddy services. Verify a consistent application backup
and recovery separately; a provider disk snapshot alone is not proof of recovery.

| Item | Published monthly amount |
|---|---:|
| Basic Regular 2 vCPU / 4 GiB / 80 GiB | $24.00 |
| Weekly backup, 20% of server price | $4.80 |
| Subtotal before tax | **$28.80** |
| Requested authorization ceiling including tax | **$32.00/month** |

The $32 ceiling is a proposed authorization, not a provider-enforced hard cap.
Stop before purchase if checkout plus tax exceeds it. No paid upgrade, extra
volume, load balancer, managed database, domain registration or paid builder is
included. Keep network/storage within the bundled allowances; monitor actual
billing. Stopping a VM is not equivalent to deleting its billable resources.
The separate $5 GPU trial is unchanged. This fixed CPU-host expense keeps project
state and cleanup available when GPU Pods are off; it is not a Wan usage fee.

The DigitalOcean console currently requires owner sign-in. No existing Droplet,
region capacity, account payment state, final checkout or hostname is verified.
After sign-in, inspect existing resources first and reuse only if safely suitable.
If the exact plan is unavailable, report the revised option before purchasing.

## Alternatives checked

- Hetzner CX23: the official cost-optimized product page still marks it unavailable.
  Its published $6.49/month excludes IPv4, backup and tax; not an available quote.
  CPX22's current published European USD price is $22.99 before IPv4/backup/tax,
  so the old $9.49 figure must not be used.
- Runpod CPU3 compute-optimized: connected catalog shows 2 vCPU / 4 GiB available
  in several US regions, $0.03 per vCPU-hour. Two vCPUs cost $0.06/hour, or $43.20
  for 720 hours **before storage**. Not chosen as the always-on controller.
- No DigitalOcean/Hetzner VPS management plugin was returned by discovery. The
  browser console is the available account-access route and is left at sign-in.

## Installation and verification sequence

1. Confirm host approval, account access, exact capacity/price and owned hostname.
2. Provision one dedicated host and firewall; install dependencies and reviewed
   checkout. Transfer scoped secrets directly to protected host files.
3. Run the guarded fresh-host installer. Confirm public TLS, login, authorization,
   synthetic upload/export and persistence through process/server restart.
4. Exercise consistent application backup/restore with fictional data. Confirm
   primary monitor freshness, credential access and restart independence.
5. Install reviewed live authority/worker transport. Start the second-host guard
   with the actual admitted scope and original deadline; verify READY before Pod
   creation. Never use a fictional admission to claim live guard acceptance.
6. Recheck GPU capacity/price and mounts, then use the existing one-attempt trial
   for exact image pull, model checksums and Wan execution. Confirm teardown and
   retained output; reconcile authoritative billing before any further attempt.

Source preparation is not deployment acceptance. Deletion permission, actual
shutdown, private image pull, model/CUDA inference and billing collection stay open.

Sources checked November 16 UTC / November 15 owner local:

- https://www.digitalocean.com/pricing/droplets
- https://www.digitalocean.com/pricing/backups
- https://docs.digitalocean.com/products/droplets/how-to/create/
- https://www.hetzner.com/cloud/cost-optimized/
- https://docs.hetzner.com/general/infrastructure-and-availability/price-adjustment/
- Runpod connected CPU catalog, product POD, vcpuCount 2, live availability.
