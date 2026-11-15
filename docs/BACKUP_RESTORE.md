# Local backup and restore readiness

The backup CLI creates a checked recovery copy of the local Studio database and
its referenced immutable media. Restore creates a separate installation directory;
it never replaces an existing database or media directory. This is a local
operator workflow, not cloud backup provisioning or production deployment.

## Commands

Run from the repository with the normal Python dependencies installed. Choose an
existing empty output directory, or a new directory whose parent already exists.
Keep backups outside the active asset root.

```sh
python -m services.controller.backup create \
  --database /path/to/studio.sqlite \
  --assets /path/to/studio-assets \
  --output /path/to/backups/rehearsal-001

python -m services.controller.backup restore \
  --backup /path/to/backups/rehearsal-001 \
  --output /path/to/restored-rehearsal-001
```

Successful create returns `complete: true`, a file count, and recovery-state
normalization counts. Successful restore returns absolute `database` and `assets`
paths plus the same recovery summary. The output structure is:

- Backup: `database.sqlite`, `assets/`, `manifest.json`, `COMPLETE`.
- Restore: `database.sqlite`, `assets/`, `RESTORED.json`.

Start the local service against the restored database and asset paths only after
restore succeeds. Supply operator tokens again through the normal environment
configuration. Backup never reads token configuration, environment secrets,
session cookies, model weights, repository credentials or deployment files.
Project prompts, scripts, metadata and original media are included because they
are the work being protected; treat the backup as private project data.

For a recovery rehearsal, retain the original installation and use a different
local port for the restored instance. Do not run both instances against the same
new filesystem and do not redirect the original service to the restored paths
until the operator has reviewed the restored project.

## Consistent snapshot and included files

Create opens the source database read-only, pins a SQLite read transaction, and
uses SQLite's backup API. Committed WAL content is included without copying WAL or
SHM sidecars. Only the snapshot is normalized, checked and vacuumed. The source
schema, project rows, jobs and files remain untouched.

The current application publishes and flushes asset bytes before the transaction
that commits their metadata. Committed assets are immutable and no current route
deletes them. This permits copying the database snapshot's referenced media while
new work continues: later commits are outside that snapshot. Every copied object
must match its recorded byte size and SHA-256. References from frozen export-job
snapshots are included even when they are not in the current project bundle.

This consistency guarantee depends on that immutable committed-file lifecycle.
Do not externally edit/delete media during backup. A mutation detected by size or
checksum aborts creation. Any future garbage collector, mutable media operation,
remote filesystem or multi-host deployment must add an appropriate retention or
maintenance protocol before relying on online backup. Stopping the local service
for an operator backup is also supported.

The backup excludes uncommitted upload chunks, combined upload staging files,
worker completion journals and export intermediate/cache files. Unknown database
tables, views or triggers are rejected rather than silently archiving unexpected
state. The simulated budget ledger is preserved only when every reservation is explicitly
settled. Backup verifies owner/project/approval links and cumulative settlement
arithmetic, including late-charge overruns; confirmed deletion alone does not
make a liability safe to omit. Outstanding or uncertain Runpod obligations also cause creation to fail:
paid batches must be terminal with confirmed cleanup, and provider lifecycle rows
must have confirmed cleanup. This tool never calls a provider or asserts that
external resources have been deleted.

## Recovery states

| Snapshot state | Recovery copy behavior |
|---|---|
| Committed asset, accepted take, review or historical timeline | Preserved unchanged, including its original byte checksum. |
| Incomplete upload | Marked `aborted`; staging bytes are excluded. Start a new upload with a new key. |
| Completed upload | Asset, manifest and idempotent receipt preserved; finish replay returns the same asset. |
| Claimed/running render attempt | Marked failed with `backup_interrupted`; its old worker is fenced. |
| Fixture batch with unfinished shots | The normal runner can claim another attempt within existing retry limits and deadline. |
| Queued/rendering export | Persisted frozen input snapshot preserved; a new export runner rebuilds intermediates and finishes it. |
| Completed export | Verified output asset and original export identity preserved. |

Backup does not extend batch deadlines, reset retry counters, reopen failed jobs,
change creative approvals or select replacement takes. A batch whose retry budget
or deadline is exhausted will require an explicit new generation command. Export
recovery uses the captured timeline and approval state, even if the creator later
changed the current selection or reviewed the take differently.

## Verification and publication boundary

Each manifest file entry records a normalized relative path, exact byte size and
SHA-256. `COMPLETE` contains the manifest's SHA-256. Files and all containing
directories are flushed before that marker is atomically published. A failed or
interrupted create has no valid completion marker and is not restorable. An
interrupted restore has no final `RESTORED.json` marker. Incomplete output
directories are left for operator inspection; the CLI will not overwrite them.

Restore checks the marker, strict manifest fields, all file checksums, the full
file inventory, SQLite integrity, bundle relationships, export snapshots and
asset records before creating its destination. It rejects traversal, absolute or
ambiguous file keys, symlinks, backup hardlinks, extra unlisted files and existing
nonempty destinations. It copies files exclusively, rechecks each checksum, checks
the restored database again, and atomically publishes its restoration marker.
No database configuration or token is copied from the active installation.

Checksums detect accidental corruption and mismatched content; they are not a
digital signature or encryption. A party who can replace every backup file and
recompute the manifest can replace the backup. Store important copies on a
separate protected device/location and manage access outside this local tool.
There is no scheduled offsite replication, encryption/key management, retention
policy or disaster-recovery service in this batch.

## Evidence

```sh
python -m unittest discover -s tests -p 'test_backup.py' -v
python -m unittest discover -s tests -p 'test_backup_integration.py' -v
```

Targeted checks cover WAL snapshots, source edits after snapshot capture,
corruption, manifest tampering, traversal, symlinks/hardlinks, uncertain resource
obligations and refusal to overwrite data. The independent integration rehearsal
uses real synthetic fixture rendering and CPU export, backs up pending work,
restores into new paths, resumes runners, verifies history and byte checksums, and
fully decodes the recovered video exports. This is synthetic local evidence;
human creative acceptance and a production deployment remain separate approvals.
