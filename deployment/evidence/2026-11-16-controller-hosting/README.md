# Controller installation evidence

Recorded November 16 UTC / November 15 owner-local, 2026. Issue #7 remains open.
Contract 0.1.0. This records an installed disarmed CPU host, not a completed GPU trial.

## Active resource and authority

- DigitalOcean Droplet 619703894, wan-controller-01, SFO2, 64.225.114.46.
- Ubuntu 24.04.5 LTS amd64, Basic Regular 1 vCPU / 2 GiB / 50 GiB.
- Approved recurring rate: $12/month plus $2.40 weekly backups = $14.40 before expected tax. Billing started; accrued invoice amount was not retrieved.
- Weekly backups enabled, Wednesday 04:00–08:00 UTC. First backup not yet completed.
- HTTPS: https://wan-64-225-114-46.sslip.io. No domain purchase, extra volume, database or duplicate host.
- Dedicated SSH key registered and encrypted private key saved as WAN_HOST_SSH_KEY. Existing SUMAN key not used.
- Host fingerprint: SHA256:aU+cxUkky0P7tyOuS7JQjevb7gLGxeN/kjMVfQIDTr4; TOFU at authenticated provider-console IP, then strict pinning.
- Installed source: 42dbdc127b299b7e11e674630bef8683473f5a7a, PR #55, tree bf7e3ab511df0f98d05e03f71fe4626ab1279353.
- Private controller identity and Runpod cleanup credential installed. Live spending/worker authority absent; paid dispatch false.

## Actual cloud runs

| Run | Operation | Outcome and boundary |
|---|---|---|
| [43793819679](https://github.com/hoyosgarciajohn-png/wan-video-generation/actions/runs/43793819679) | Inspect | Passed fresh-host SSH, OS/architecture, memory/disk and host fingerprint. |
| [43793913368](https://github.com/hoyosgarciajohn-png/wan-video-generation/actions/runs/43793913368) | Install | Failed at Git ownership after archive extraction; before venv/private application state. PR #54 corrected root ownership and scoped recovery. |
| [43794353466](https://github.com/hoyosgarciajohn-png/wan-video-generation/actions/runs/43794353466) | Resume | Services installed and local readiness/cleanup/Runpod GET passed. Immediate external TLS probe failed while certificate was being issued. |
| [43794933132](https://github.com/hoyosgarciajohn-png/wan-video-generation/actions/runs/43794933132) | Upgrade | Installed CSP fix from PR #55 with consistent local backup and retained prior source. Immediate health probe failed before Waitress socket readiness. |
| [43795476474](https://github.com/hoyosgarciajohn-png/wan-video-generation/actions/runs/43795476474) | Verify | Passed clean installed source, active/enabled services, firewall, loopback app, SQLite integrity, fresh cleanup, authenticated Runpod GET and external HTTPS. |

Bounded excerpts retain observed outcomes; full logs remain at each private run.
The verification source now bounds startup retries to address the observed socket race.
No failed install/upgrade was blindly repeated. Verify makes no GPU mutations.

## Verified service boundary

wan-controller, wan-cleanup and wan-proxy are active and boot-enabled. SSH is
key-only with port22 rate limiting; incoming defaults to deny except SSH/HTTP/HTTPS.
App8080 and Caddy admin2019 bind loopback. SQLite integrity is okay and there are
zero live-job bindings. Cleanup status is ready with zero due batches and no
unresolved entries. An authenticated Pod GET succeeded with zero creates/deletes.

At verification: RAM1967 MiB total, 393 used, 1574 available; no swap; root disk
48 GiB filesystem, 2.6 used, 45 available. These are idle baseline observations.
Production-length exports and cleanup behavior under load are not established.

An application-consistent pre-upgrade backup exists under the private bootstrap
directory on this host. It is not an off-host backup or completed restore drill.

## UI and validation

The initial blank page came from runtime AJV Function compilation under strict
CSP. The reviewed fix compiles the schema at build time; unsafe-eval was not added.
The deployed sign-in screen renders. Browser session access remains rejected
(direct browser navigation returned403). Direct HTTP with same-origin fetch-site
returns expected401; cross-site returns expected403. No valid owner session was
established and no owner token was printed or delivered. Investigate request
provenance without weakening the origin boundary.

Fictional checks performed: 20 targeted hosting/initialization/preflight checks;
archive ownership regression; 17 Studio model/API/CSP checks; 17 UI checks;
production build; one affected source-inventory test after adding upgrade-host;
formatting, shell syntax and whitespace checks. No full suite was needlessly
repeated. Cloud Node22 production build also passed in the upgrade run.

## Still required

1. Resolve browser session rejection and securely deliver existing owner access.
2. Hosted fictional upload/render/export, retained-media restart, cleanup under load/failure, off-host restore arrangement and acceptance.
3. Installed live authority and worker/model bootstrap; ready independent deadline guard for the exact admission before provisioning.
4. Actual private image pull, Wan inference, output retention, confirmed Pod shutdown and authoritative billing retrieval under the existing $5/1800-second/one-attempt envelope.

No Runpod Pod, volume, endpoint or model download was started. The approved trial
is unused. The existing $10 prepaid credit does not expand that trial.
