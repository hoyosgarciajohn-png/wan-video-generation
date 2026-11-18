"""Prepare a missing suffix without authorizing another execution.

The resident model renders 93 frames from prompt/image/audio/seed, independently
of editorial offsets. Rebase those offsets for the existing worker validator;
retain the original edit map for later receipt-verified full-song assembly.
"""
from copy import deepcopy
import re

from workers.gpu.common import require
from workers.gpu.longcat_batch import fingerprint


def prepare_missing_suffix(manifest, journal, *, project_id, batch_id):
    binding = fingerprint(manifest)
    require(journal['binding'] == binding, 'Journal belongs to another manifest')
    for value in (project_id, batch_id):
        require(re.fullmatch(r'[A-Za-z0-9_-]{1,80}', value) is not None, 'Invalid preparation identity')
    require(batch_id != manifest['batch_id'], 'Never reuse the consumed batch')
    require(set(journal['shots']) <= {s['id'] for s in manifest['shots']}, 'Unknown journal shot')
    completed = []; missing = []; gap = False
    for shot in manifest['shots']:
        row = journal['shots'].get(shot['id'])
        if row is None:
            gap = True; missing.append(shot); continue
        require(not gap, 'Published takes are not a contiguous prefix')
        require(row['status'] == 'published', 'Started unpublished shot needs recovery before continuation')
        require(row['input_sha256'] == fingerprint(shot), 'Rendered input changed')
        receipt = row['receipt']
        require(receipt['binding'] == binding and receipt['shot_id'] == shot['id']
                and receipt['scope_id'] == journal['scope_id'], 'Foreign receipt')
        completed.append(shot['id'])
    require(completed and missing, 'An incomplete successful prefix is required')
    first = missing[0]
    result, offset = rebase_suffix(manifest, missing, project_id=project_id, batch_id=batch_id)
    provenance = dict(status='PREPARATION_ONLY_NO_RENTAL_OR_SPEND_AUTHORITY',
        source_manifest_sha256=binding, source_scope_id=journal['scope_id'],
        source_offset_frames=offset, first_original_frame=first['in_frame'],
        original_first_trim_frames=first['trim_in_frames'],
        complete_song_frames=manifest['duration_frames'], preparation_sha256=fingerprint(result),
        preserve_completed_shots=completed, render_only_shots=[s['id'] for s in missing],
        original_edits=deepcopy(missing))
    return result, provenance


def rebase_suffix(manifest, missing, *, project_id, batch_id):
    """Pure editorial transform; no receipts, authority or inference state created."""
    first = missing[0]; offset = first['audio_start_frame']
    result = deepcopy(manifest)
    result.update(project_id=project_id, batch_id=batch_id,
                  duration_frames=manifest['duration_frames']-offset, shots=deepcopy(missing))
    for i, shot in enumerate(result['shots']):
        shot['in_frame'] -= offset; shot['audio_start_frame'] -= offset
        if i == 0:
            # Keep the original look-behind in the conditioning audio. The final
            # full-song edit will discard it using the original trim, not this one.
            shot['frames'] += shot['trim_in_frames']
            shot['in_frame'] = 0; shot['trim_in_frames'] = 0
    cursor = 0
    for original, shot in zip(missing, result['shots']):
        require(shot['in_frame'] == cursor and 0 < shot['frames'] <= 93,
                'Rebased edit is not contiguous')
        require(shot['audio_start_frame'] == cursor-shot['trim_in_frames'], 'Audio offset changed')
        require(shot['audio_start_frame']+offset == original['audio_start_frame'], 'Original audio alignment changed')
        for key in original:
            if key not in ('in_frame', 'audio_start_frame', 'frames', 'trim_in_frames'):
                require(shot[key] == original[key], 'Generation input changed')
        cursor += shot['frames']
    require(cursor == result['duration_frames'], 'Continuation duration mismatch')
    return result, offset
