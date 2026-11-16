# Hosted progressive validation — November 16, 2026

Operational release: 42b3e993dc8ac3540d1ae450d287c1a90b555338.
PRs #72–75 are merged. Contract remains 0.1.0.
Final upgrade run 43891224231 passed (job 133382638081):
reviewed source installed, private state preserved, all three services active and
enabled, cleanup heartbeat ready, two historical live jobs preserved, external
HTTPS health passed, paid public dispatch disabled.

The first upgrade (43889464546) stopped on an obsolete baseline pin before switching
the installed source. PR #73 corrected it. Subsequent upgrades 43890387733,
43890782933 and 43891224231 passed. Location selection now uses a fresh eligible
Secure RTX 4090 quote and binds the selected location before admission; prepared
authority cannot silently migrate to another location.

Hosted one-minute rehearsal 43890910756 passed on release 5ff04c6:
12 fictional five-second shots, 1,440 frames, 60-second audio-backed MP4,
1280x704 at 24fps. Export 17.517 seconds; total 27.158 seconds;
peak child RSS 110,680 KiB. Full decode and restart/idempotency passed.
The 320x180 source clips are synthetic blue fixtures, so this establishes export
mechanics and a limited CPU baseline, not Wan inference or detailed-scene performance.
Full machine-readable result: hosted-one-minute.json.

Repair preparation 43891758558 passed on operational release 42b3e993.
Project project-10088bb273fb41d78399957f2dc8cd83, immutable repaired image ending ed50,
manifest b980738d91f5d5870be6061ff8306137b931109a43c8cb52247e1d2b71d5cb18,
Secure RTX 4090 / EU-RO-1, quoted $0.89/hour.
New scope: /var/lib/wan/repair-trial-20261116; authority:
 /etc/wan/repair-trial-authority-20261116.json.
Preparation created no Pod, admitted no batch and started no deadline.
The approval/build/host evidence expires six hours after preparation, approximately
21:00 UTC; actual valid_until in the protected grant is authoritative.

The browser's old owner session expired following deployment. The sign-in screen
renders; no fresh authenticated owner visual acceptance is claimed.
Previous sign-in evidence remains historical, not evidence of the current session.

## Submitted repair attempt — unresolved allocation

Admission 43892215902 created batch 249c50635ec84ac38cef0eb66232efed at
15:03:20 UTC, fixed deadline 15:33:20 UTC. Independent guard 43892343231 was
verified running before launch 43892451814 made its single create request at
15:04:38 UTC. The latest connected inventory is empty; the controller has not
recorded a Pod ID. No actual worker inference or output is established.
The installed adapter discards the provider error details, so the exact cause is
unknown. Do not equate this outcome with GPU OOM or confirmed capacity rejection.

The launch and guard remain in progress at repair-checkpoint.json's observation.
Cleanup is pending, the $4 reservation is retained, and the guard watches through
15:38:20 UTC. No additional create or retry is authorized. An unknown create with
no observed allocation deliberately cannot be marked cleaned by an empty inventory.

Prepared follow-up diagnostics log numeric HTTP status without body/credentials
and place lifecycle fields in a compact live line; complete status stays on disk.
20 adapter/lifecycle/integration checks and 10 trial gates pass. These changes
are not installed while the admitted request is unresolved. They do not recover
the original response or change retry/cleanup/billing policy.
