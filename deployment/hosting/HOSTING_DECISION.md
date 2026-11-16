# Free controller hosting decision — November 15, 2026

Status: **FREE_ONLY_EXISTING_HOSTING_REUSE_ASSESSMENT**.
John rejected DigitalOcean and new recurring controller-hosting charges. The
previous $28.80/month proposal and $32/month authorization request are withdrawn.
No paid host was ordered. The DigitalOcean sign-in tab was closed.

## Cost policy and recommendation

First assess reuse of **existing Vercel / ChatGPT Sites and Supabase services**.
Oracle Always Free remains the candidate requiring fewer backend changes if
existing hosting cannot meet the requirements at no additional charge. The
existing Windows computer remains a fallback. Additional recurring controller budget:
**$0**. Do not upgrade an account, buy a replacement VPS, or treat expiring trial
credit as permanent free hosting. Do not add a paid database, domain or backup.
The approved $5 / 1,800-second / one-attempt Runpod trial remains separate and unused.

| Candidate | Fit for this implementation | Decision |
|---|---|---|
| Existing Vercel / Sites plus durable backend | Existing accounts and projects verified; current SQLite/process model must change | Assess reuse before a new account; incremental cost unverified |
| Oracle Always Free A1 | Persistent Linux host; requires ARM adaptation | Persistent-server alternative; not provisioned |
| Existing Windows PC with WSL | Can host controller and CPU export while awake and online | Fallback; local capabilities and secure access unverified |
| Cloudflare Workers / Durable Objects | Free quotas exist, but current Python services, file storage and FFmpeg require redesign or relocation | Possible later architecture; not a direct deployment |
| Render Free | Sleeps after 15 minutes idle; filesystem is ephemeral and free persistent disks unavailable | Reject for the unchanged SQLite/media controller |
| GitHub Actions | Bounded build/deadline jobs within the private account's remaining included allowance | Keep watchdog role; not continuous controller hosting |

This recommendation is an implementation-fit inference, not a claim that free
infrastructure has already been allocated or accepted.

## Existing hosting inventory verified in connected accounts

| Service | Existing projects observed |
|---|---|
| Vercel | SIMIES, Swing Cubano, Cockpit / Board Autopilot, Wellness Home Visit, Transformational Resonance, OMNIVALE preview, Tu Idea private QA |
| ChatGPT Sites | Open Tomorrow, Tu Idea es tu Negocio public site, RAP Instituto Tecnico Valle, Dream House Studio; other prototypes |
| Supabase | Active databases for SIMIES, Swing Cubano (pelota-caliente-dev), Open Tomorrow, OMNIVALE, Transformational Resonance and Cockpit |

Vercel custom-domain mappings and Sites live URLs were read. This inventory does
not establish unused quotas, current billing plans, permission to merge application
data or the marginal cost of a new Supabase project. No other project was modified.

The Studio frontend is a plausible reuse candidate. The current controller stores
SQLite and media on disk, uses process-local sessions and runs background threads
plus a separate cleanup process. Vercel Functions use ephemeral scratch space and
bounded execution; Sites runs Worker modules. These are not drop-in systemd hosts.
A reuse implementation needs durable database/object storage, transactional job
admission, portable sessions, short request handlers, independent deadline cleanup
and an explicit execution location for FFmpeg exports. Keep Wan GPU work on Runpod.
Recheck quotas and isolate Wan from existing project data before choosing storage.
Do not create an additional billed project merely because the account exists.

## Oracle configuration and constraints

Current official A1 allowance: 2 OCPUs / 12 GB RAM equivalent; 200 GB combined
boot/block storage, in the account home region. Proposed dedicated Ubuntu A1:
2 OCPUs, 12 GB RAM, one 50 GB boot disk, only if existing usage leaves room.
Capacity shortages and idle-instance reclamation are possible. Free service has
no SLA. Signup requires card verification and may place a temporary hold.
Use an existing eligible account if present; no paid upgrade is authorized.

The current fresh-host installer is **amd64-only**. Do not bypass its architecture
check. Review dependency locks and native wheels for ARM, add explicit support,
and verify the actual ARM host. The Wan GPU container remains linux/amd64 on
Runpod; changing controller architecture does not require rebuilding that image.

## Next execution sequence

1. Compare a concrete Vercel/Sites plus durable-backend adaptation against the
   existing free Linux/Windows routes. Verify remaining account allowances,
   independent cleanup scheduling, media retention and additional cost first.
   If using Oracle, establish account access and confirm quota/capacity. If no
   free cloud route is available, use Windows; do not substitute a paid plan.
2. Adapt the installer and validate Python dependencies, FFmpeg/ffprobe, Studio,
   Caddy and systemd on the actual architecture. Retain disarmed startup.
3. Use an existing controlled hostname with HTTPS or another verified free access
   route. Install secrets in protected host storage, not repository/user-data.
4. Verify fictional upload/export, owner isolation, restart persistence and
   backup/restore. Set storage retention and quota stops; long-form projects need
   measured disk/export capacity. Keep recoverable copies outside the controller.
5. Install live authority and primary cleanup. Start the independent GitHub
   deadline guard for the actual admitted scope and original deadline; require
   READY before Pod creation. Recheck included minutes and blocked paid overages.
6. Only then use the existing single Runpod attempt for private image pull and
   Wan inference. Verify deletion, retained output and actual billing. Do not
   retry rendering or resource creation under this authorization.

For Windows, first verify WSL support, RAM, free disk and Linux services. Keep the
PC awake and online during a batch. Establish authenticated HTTPS worker access;
do not expose the development server directly. Docker Desktop is not required by
this controller design. This avoids an additional hosting bill but uses the PC's
power and internet connection. Independent cleanup remains mandatory if it sleeps,
loses internet or stops. No local installation or network change was made here.

## Evidence boundary

This step changes policy and documents only. No account/signup, server, recurring
subscription, GPU, storage allocation or new credential was created. No runtime
or compatibility check was repeated or newly claimed. Actual automatic shutdown,
Runpod image download, installed live authority and authoritative billing remain
unverified. Existing credential/build evidence and contract 0.1.0 are preserved.

Official sources checked November 16 UTC / November 15 owner local:

- https://vercel.com/docs/functions/runtimes
- https://vercel.com/docs/functions/limitations
- https://supabase.com/docs/guides/functions/limits
- Connected Vercel project/domain inventory, Sites inventory, and both Supabase account inventories.
- https://docs.oracle.com/en-us/iaas/Content/FreeTier/freetier_topic-Always_Free_Resources.htm
- https://www.oracle.com/cloud/free/faq/
- https://www.oracle.com/cloud/free/
- https://render.com/docs/free
- https://developers.cloudflare.com/durable-objects/platform/pricing/
- https://learn.microsoft.com/en-us/windows/wsl/install
- https://docs.github.com/en/billing/concepts/product-billing/github-actions
