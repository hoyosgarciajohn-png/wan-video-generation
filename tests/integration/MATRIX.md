# B05 acceptance matrix

Contract `0.1.0`. Baseline `c9c364ab3f68cfca24489715ab0cd8419d0d4f60`. Issue [#6](https://github.com/hoyosgarciajohn-png/wan-video-generation/issues/6). Fixture owners are `alpha-fictional-owner` and `beta-fictional-owner`. Runtime scenarios use injected time and a fake provider. Every result needs an exact source/deployment revision, command or request transcript, observed result and artifact reference.

PASS records an executed check with its expected outcome. FAIL records an observed mismatch. BLOCKED identifies a missing implementation, environment or authorization. Human creative acceptance is pending until observed in the live owner session. The local preparation results appear in EVIDENCE.md and its JSON log.

## Preparation coverage

| ID | Input and assertion | Executable coverage |
|---|---|---|
| P01 | Independent project bundles have distinct owners, IDs and paths and validate with synthetic media | `test_two_project_fixtures_validate_with_scoped_media` |
| P02 | Foreign batch, attempt, asset, review and export references are rejected | `test_foreign_references_are_rejected_across_component_boundaries` |
| P03 | Grafting another owner's asset by rewriting its project ID is rejected | `test_foreign_assets_cannot_be_grafted_by_rewriting_project_id` |
| P04 | Replacement retains the first take, timeline and captured export revision. Rejection blocks the replacement timeline | `test_replacement_preserves_old_take_and_export_revision` |
| P05 | Retry bundle validates, linking a take to a failed attempt is rejected | `test_failed_attempt_retry_cannot_receive_a_committed_take` |
| P06 | A retry completing after its static lease expires is rejected | `test_retry_with_expired_lease_cannot_commit` |
| P07 | Missing and truncated media fail before acceptance | `test_missing_and_partial_uploads_fail_media_verification` |
| P08 | An asset symlink escaping the local media root is rejected | `test_symlink_cannot_escape_media_root` |
| P09 | Music timeline at 300,000 ms and film/cartoon timelines at 1,800,000 ms validate. One extra millisecond is rejected | `test_music_film_and_cartoon_timeline_boundaries` |
| P10 | Both synthetic sources decode completely, retaining their original SHA-256 | `test_synthetic_sources_decode_completely_without_mutation` |
| P11 | Reporter retains failures/timeouts and blocks zero-test or skipped discovery | `EvidenceReportingTests`, four tests |

Existing B00 tests retain cost-field validation, budget overshoot accounting, frozen snapshots, duplicate take prevention, ambiguous fake creation, blind-retry duplicate detection and deletion failure/retry coverage. The runner executes them through the established root command.

## Integrated rehearsal after B01–B04 merge

All R cases are initially BLOCKED pending the merged application and staging setup. These are executable acceptance specifications for the next integration step. Static P checks provide fixture evidence for them.

| ID | Scenario through normal entry points | Expected result and evidence | Required owner |
|---|---|---|---|
| R01 | In Studio create a fictional music project, import synthetic audio, create shots, approve fixture batch, render, review takes, save timeline and export | Persisted IDs trace the whole journey. Completed scoped MP4 decodes and plays in the staging browser. Capture staging URL, deployed commit, request/response IDs and exported asset checksum | B01–B04, Command Center |
| R02 | Use beta identity and an anonymous session to access alpha project, asset upload/download, shots, batches/cancel, takes, reviews, timelines and exports. Substitute foreign linked IDs on writes | Missing identity receives 401. Inaccessible records receive 404. Store a route-by-route response matrix and confirm zero unauthorized state changes | B02, B03 |
| R03 | Concurrently submit identical batch requests using one idempotency key, then reuse the key with changed input. Repeat export submission | Same input produces one batch/reservation or export. Changed input receives 409. Capture committed row counts, provider call ledger and response IDs | B02, B04 |
| R04 | Edit a shot after batch approval, then submit a stale expected revision | Existing batch retains the frozen input. Stale edit receives 409. Persist both shot revision and frozen snapshot | B02, B03 |
| R05 | Allocate a fake Pod but lose the create response. Restart the controller before recording success and reconcile inventory before retry | One allocation is adopted. Uncertain inventory defers new launch. Capture durable launch key, row state and provider call sequence across restart | B02 |
| R06 | Stop a worker after claim, expire its lease and retry with a new worker. Send late heartbeat, fail and complete from the old worker | Old lease is fenced. Only the current valid attempt commits. Preserve claim/lease IDs, clock advances and take count | B01, B02 |
| R07 | Interrupt upload, remove the object, alter size/checksum or media metadata, then retry completion with verified bytes | Failed verification commits zero takes. Valid completion commits one. Identical replay returns that take and conflicting replay receives 409 | B01, B02 |
| R08 | Cancel queued and rendering batches, repeat cancellation and restart the controller during cleanup | Future claims stop. Obsolete attempts are fenced. Committed takes survive. Cancellation and cleanup remain durable and idempotent | B01, B02 |
| R09 | Exhaust a fictional budget, race reservations, advance past deadline and record a delayed charge exceeding the cap | Atomic reservations cannot exceed available approval. Further launches/retries stop. Actual overrun is retained and surfaced. Fixture mode keeps all cents zero | B02 |
| R10 | Delete a fake Pod with an error or timeout, lose inventory access, then let independent watchdog retry and establish absence | Cleanup stays pending/failed until a successful provider read establishes absence. Render success remains independently recorded. Capture alerts and watchdog evidence | B02 |
| R11 | Restart API/controller with persisted queue, accepted takes and timelines. Read them through owner identity and resume unfinished work | Durable state survives process restart. Completed work is retained and pending work resumes once. Capture process identities and state before/after | B02, B04 |
| R12 | Approve a new take, replace only the chosen timeline item, and reopen previous revision and its export | Prior take/revision remains readable, old export retains its captured revision, only selected item changes in the new timeline | B02–B04 |
| R13 | Export synthetic timelines including trims and audio offsets at 5- and 30-minute caps, then attempt a 1 ms overrun | Valid exports decode with measured duration and A/V sync. Overrun is rejected. Log ffprobe streams, first/last timestamps and declared tolerance before execution | B04 |
| R14 | Interrupt export, restart CPU worker, retry a failed export and replay completed requests | Output is committed atomically after verification. Partial objects remain unavailable as completed exports. Accepted timeline revision and source audio checksum survive | B02, B04 |
| R15 | Access the completed export from another project and use an expired download grant | Foreign and expired access fail. Owner access succeeds within its scope and lifetime. Capture status codes and asset ownership without retaining credentials | B02, B04 |

## Later release evidence

| Batch | Evidence required | Present status |
|---|---|---|
| B06 | Approved dollar/runtime envelope, pinned image/model, six-shot manifest, cold/warm timings, failures, peak VRAM, billed GPU/storage/transfer amounts, approved seconds, teardown latency and provider-confirmed absence. Re-read durable outputs after deletion and account for billing lag | BLOCKED pending B05 and approved spend |
| B07 | Music-video export up to five minutes, source-song checksum/alignment and selective replacement. John's recorded creative evaluation | BLOCKED pending B06, owner evaluation pending |
| B08 | Thirty-minute fixture export and representative generated continuity/dialogue/cartoon sequences. Explicit record of whether a full generated thirty-minute project was rendered and reviewed | BLOCKED pending B07 |
| B09 | Exact deployed commit, owner release authorization, rollback rehearsal, verified database/asset restore, billing monitor, shutdown alerts and operational owner | BLOCKED pending B08 and release approval |
