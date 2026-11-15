# Real-run preflight: planning evidence only

`services.controller.preflight` produces an immutable, source-bound planning
artifact. It never admits a live batch, creates a Pod, downloads weights, builds
an image, runs Docker, contacts a provider or issues worker credentials. Every
result retains `execution_authorized: false` and `ready_for_live_run: false`.

A missing budget or hostname is not the only remaining blocker. The live admission
and real-model worker/storage connection are **not implemented**. The existing
`SimulationCoordinator` still accepts only the fictional provider, and
`WorkerTransport` still rejects non-fixture batches. Supplying documents or changing
an input file cannot activate Wan execution.

## Produce and check a plan

```sh
python -m services.controller.preflight --output /new/path/missing-gates.json

python -m services.controller.preflight \
  --intent /private/path/non-secret-intent.json \
  --build-evidence /path/to/existing-gpu-build-evidence \
  --approval /private/path/owner-attestation.json \
  --output /new/path/review-plan.json
```

The output parent must already exist and the file must be new. `write_plan()` writes
it exclusively with mode 0600 and fsync. `verify_plan(path)` checks its content hash
and current source inventory; changed source requires a new plan and review.
Hashes provide content integrity, not signatures or authenticated approval.

With no intent supplied, the output lists missing inputs and implementation gates
without inventing a project, spending cap, host, image or acceptance result.
`docs/REAL_RUN_PREFLIGHT.json` is that current missing-input report, not a completed
readiness certificate.

## Exact owner inputs needed

John must select the following before a concrete benchmark can be reviewed:

1. The actual project/owner IDs, proposed batch and worker IDs, GPU type, provider
   and region. Selecting a provider is not a provisioning request.
2. A maximum dollar budget expressed in USD cents and the maximum runtime/window.
   The reservation estimate is separate from the cap. No estimate is a guaranteed
   final provider bill, and no numerical value is filled in automatically.
3. The exact reviewed worker image registry reference ending in `@sha256:...`,
   supported by actual build evidence. The pinned runtime base image is not proof
   that the project's worker image has been built or is pullable from a registry.
4. A specific durable controller/storage host and HTTPS worker origin, plus an
   output retention period and backup/restore owner. These are planning selections;
   public hosting, TLS and storage acceptance still need separate verification.
5. The exact benchmark release/action approval after the missing code and host
   checks have been completed. A simulated budget record is not that approval.

Never put a provider API token, bearer credential, password, presigned URL or
arbitrary environment variables into these files. Credentials remain separately
provisioned secrets. The evaluator rejects unknown fields and credential-bearing
endpoint URLs; its failure summaries do not echo supplied invalid values. Evidence
logs are checked locally but their raw contents are not embedded into the plan.

## Intent format

The JSON intent contains exactly these top-level fields:

| Fields | Meaning |
|---|---|
| `project_id`, `owner_id`, `batch_id`, `worker_id` | Exact proposed identity scope. No credential is issued. |
| `provider`, `region`, `gpu_type`, `gpu_count` | Proposed provider-neutral GPU selection; one GPU in this benchmark plan. |
| `image_ref` | Immutable registry digest for the built worker image. |
| `worker_endpoint` | HTTPS origin without path, query, fragment or embedded credentials; not a local/private IP. |
| `runtime_seconds`, `reservation_cents`, `worker_ttl_seconds` | Explicit bounded runtime, estimated reservation and scoped credential lifetime. The TTL must exceed the runtime and be at most one hour. |
| `storage` | `{kind:"controller_bridge", namespace:"projects/PROJECT_ID", durable_artifact_id:"OWNER_SELECTED_ID", retention_days:...}`. |
| `pod` | `{disk_gib:..., model_mount:"/models", output_mount:"/worker", public_ports:[], privileged:false}`. |

Disk capacity is checked against the sum of the pinned model-file bytes. This is a
necessary minimum, not proof of sufficient operational space; image layers,
transient work and filesystem overhead still need measured host acceptance.
Mount paths, private ports and non-privileged configuration are explicit plan
constraints, not an implemented provider launch template.

The intent digest binds the normalized intent, exact model-lock hash and current
source hashes. The model profile, checkpoint revision, source revision, base-image
locks and dependency files are read from the repository rather than accepted as
caller-selected substitutions. A field or source change produces a new digest.

## Evidence checks and their limits

Optional GPU build evidence must come in the existing `deployment.build_verify`
format. The evaluator checks current captured source inventory, verifier and smoke
helper hashes, a completed local execution record, hashed command logs, the built
image ID, Linux/amd64 identity, selected registry digest and the actual checksum-
verified CPU fixture artifact. Runtime import evidence must name the pinned Wan
source revision. It never executes the recorded command arguments. PASS strings
without those records do not satisfy this consistency check.

The status `CONSISTENT` means the supplied local evidence agrees with itself and
the current reviewed inputs. It does not authenticate who produced it or establish
registry access, successful CUDA inference, GPU speed, live TLS/storage behavior
or a deployment. A malicious party able to rewrite all evidence can fabricate
self-consistent files; these hashes are not signed provenance.

An optional owner attestation must contain exactly `schema_version:1`, `owner_id`,
`project_id`, `intent_sha256`, `currency:"USD"`, `approved_cents`,
`max_runtime_seconds`, `issued_at`, `expires_at` and `reference`. The evaluator
checks identity, exact intent, bounds and current validity. It stores only a file
hash and safe numeric/expiry terms in the plan, not the raw approval reference.
The attestation is a content-consistency input, **not authenticated authority**.
An actual live approval verifier still has to be implemented and reviewed.

## Gates that remain blocked regardless of supplied files

- Authenticated real approval verification and transactional live queue/budget
  admission, without weakening the simulation-only coordinator.
- The real-model lifecycle-to-attempt, lease, credential and remote storage bridge,
  without weakening the current fixture-only worker transport.
- A verified durable host, TLS endpoint, storage retention and recovery acceptance.
- Registry access, actual locked weight verification on the selected volume, CUDA
  inference and measured cold/warm GPU behavior.
- Authoritative provider usage/final-invoice ingestion and independently observed
  cleanup, including ambiguous creation and delayed charges.
- Explicit authorization for the specific benchmark release and capped resource
  action after those code/evidence reviews.

The next implementation step is to design and review a distinct live admission
adapter and its real-model worker/storage authorization flow behind a disabled
execution gate. The next owner decision is the concrete project, spend ceiling,
runtime window and host/GPU selection. Neither step is replaced by another fixture
success report. Actual image build, GPU execution and hosted acceptance remain
unverified until performed with explicit authorization and recorded evidence.

Targeted checks: `python -m unittest discover -s tests -p 'test_preflight.py' -v`.
They cover immutable artifacts, source changes, expired/mismatched attestations,
secret omission, malformed/PASS-only evidence and a deliberately synthetic
self-consistent evidence fixture that still cannot authorize execution.
