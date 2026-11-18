# Incomplete rendered footage and continuation

Issue #8 still requires the entire 362.880-second video. A partial export does
not meet that acceptance goal and must never be called the final music video.

The November 18 production run exposed a capacity shortfall: the remaining
cumulative allowance admits only 3,864 seconds for the two-H100 rental. Runtime
download/unpacking took about ten minutes, followed by input/weight loading.
Warm inference takes about 33–34 seconds per 93-frame shot; durable collection
adds further elapsed time. The initial 110-shot forecast did not allow enough
time for the complete cold-start and collection path.

The active run remains bound to its original deadline and budget. Preserve every
published take, exact manifest, authenticated receipt, input fingerprint and
original master. Do not renew the grant, rerender published footage, change the
approved soundtrack, add still-image fillers or label a partial assembly complete.

## Explicit partial export

`python -m workers.media.longcat_partial` takes `--manifest`, `--journal`,
`--takes`, `--master`, `--master-sha256` and `--destination`. The manifest/journal
must come from the authenticated production channel. Downloaded clip names must
match `S001.mp4` etc. The utility accepts only an incomplete contiguous prefix,
verifies every clip against its published receipt, and applies the original
integer-frame edits. The listening copy stops at the last covered frame; the
complete original WAV is never modified.

The sidecar declares `INCOMPLETE_RENDERED_PREFIX_NOT_FINAL_VIDEO`, exact covered
frames, full-song duration, included/missing shot IDs, scope and source/output
hashes. Gaps, foreign receipts, changed inputs/footage and overwriting an existing
export are rejected. The original complete-song assembler is unchanged and still
requires all 110 durable receipts in the execution it validates.

## Finish the original video

After the current run ends, record the exact missing suffix and provider cleanup.
A continuation must use new bounded authority within genuinely available funds
and runtime; the consumed scope and its reservation remain immutable. `prepare_missing_suffix` prepares only missing shots and preserves all generation
inputs. It rebases editorial offsets for the existing worker, retaining the
first shot's audio look-behind and original trim for final assembly. Started but
unpublished work blocks preparation until reconciled. `assemble_completed_runs`
validates each execution against the original plan, retains every original receipt
binding, rejects changed inputs, gaps and duplicate coverage, and uses the
original full-song edits and untouched master. These offline helpers do not
authorize or allocate another rental. The complete 6:03 video, varied camera angles, sports physics
and owner creative acceptance remain open until observed.

Validation: eight fictional-media tests cover partial duration, unchanged master,
continuation audio look-behind, complete assembly across two scopes, missing
coverage and refusal of altered receipts/inputs. The existing single-execution
complete-assembly regression also passes. This offline addition changes no live
worker, admission policy, controller deployment, GPU image or active queue.
