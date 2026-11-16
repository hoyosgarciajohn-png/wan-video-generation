# Progressive validation preparation — November 16, 2026

Baseline: remote main 1d3e99820997ca2530a4e9a93c6e9a488341c8e4.
All 341 local tracked blob hashes matched that baseline before changes.
Issues #5 (export) and #7 (GPU validation); contract remains 0.1.0.

Completed local evidence:
- Shared contract/media validation: PASS.
- Python root discovery: 162 tests PASS (91.699 seconds).
- Trial/hosting affected gates: 17 tests PASS. Repaired image context matches the
  built artifact; both consumed image contexts are correctly rejected.
- Connected media HTTP checks: 2 PASS. Initial named-module invocation failed
  to import the sibling test harness; PYTHONPATH=tests corrected the invocation.
- HD/legacy export regression: new 1280x704 export succeeds, frozen legacy 320x180
  export succeeds, and mismatched dimensions are rejected.
- Studio TypeScript/Vite build: PASS; 17 UI/DOM tests PASS.
- Shell syntax, Python compilation, whitespace: PASS.
- One-minute fictional rehearsal: 12 admitted five-second shots, 1440 frames,
  1280x704 at 24fps with AAC, complete decode and restart/idempotency PASS.
  Export took 37.629 seconds on the local execution machine; this is not a
  DigitalOcean performance result. See local-one-minute.json.

No paid GPU was created during preparation. The new isolated repair trial preserves
both prior jobs, approvals, image references and billing reservations. New host and
GPU execution evidence will be appended after actual operations. The public render
path stays synthetic. This evidence does not close real five-second or minute-long
Wan acceptance, creative acceptance, final billing or larger scale validation.

Hosted continuation: see hosted-operations.md, hosted-one-minute.json and
repair-checkpoint.json. The HD exporter is installed and the hosted one-minute
fictional pipeline passed. The one-second repair scope made its sole create
request but allocation is unconfirmed; the launch and independent guard remain
active at the checkpoint. This does not establish any repaired Wan output.
