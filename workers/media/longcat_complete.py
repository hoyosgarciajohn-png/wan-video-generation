"""Assemble complete original coverage from separately authenticated executions.

Receipts retain their original scope and manifest bindings. Inputs must match
the original plan exactly, allowing only the documented suffix timing rebase.
"""
from pathlib import Path
import re
import wave

from workers.gpu.common import atomic_json, digest, require
from workers.gpu.longcat_batch import fingerprint, verify_output
from workers.media.longcat_continuation import rebase_suffix
from workers.media.longcat_partial import encode_review


def assemble_completed_runs(manifest, runs, master, master_sha256, destination):
    master, destination = Path(master), Path(destination)
    require(not destination.exists(), 'Review output exists; do not overwrite')
    require(digest(master) == master_sha256, 'Complete master changed')
    frames = manifest['duration_frames']
    with wave.open(str(master)) as audio:
        require((audio.getnchannels(),audio.getsampwidth(),audio.getframerate(),audio.getnframes())
                == (2,2,48000,frames*1920), 'Complete master must match timeline')
    originals = manifest['shots']; index = {}; cursor = 0
    for i, shot in enumerate(originals):
        require(re.fullmatch(r'[A-Za-z0-9_-]{1,80}',shot['id']) is not None and shot['id'] not in index,
                'Invalid or duplicate original shot')
        require(shot['in_frame'] == cursor and 0 < shot['frames'] <= 93
                and 0 <= shot['trim_in_frames'] <= min(cursor,93-shot['frames']), 'Invalid original edit')
        index[shot['id']] = i; cursor += shot['frames']
    require(cursor == frames and manifest['fps'] == 25, 'Original timeline changed')
    saved = {}; provenance = {}
    for run in runs:
        source, journal = run['manifest'], run['journal']; binding = fingerprint(source)
        require(journal['binding'] == binding, 'Journal belongs to another execution')
        require(source['shots'] and source['shots'][0]['id'] in index, 'Unknown continuation start')
        first = index[source['shots'][0]['id']]
        expected, _ = rebase_suffix(manifest, originals[first:],
            project_id=source['project_id'], batch_id=source['batch_id'])
        require(source == expected, 'Continuation changed original generation inputs or timing')
        shots = {s['id']:s for s in source['shots']}
        require(set(journal['shots']) <= set(shots), 'Unknown execution shot')
        for shot_id, row in journal['shots'].items():
            require(row['status'] == 'published', 'Unresolved inference requires explicit recovery')
            require(shot_id not in saved, 'Duplicate coverage needs an explicit take selection')
            require(row['input_sha256'] == fingerprint(shots[shot_id]), 'Rendered input changed')
            receipt = row['receipt']
            require(receipt['binding'] == binding and receipt['scope_id'] == journal['scope_id']
                    and receipt['shot_id'] == shot_id, 'Foreign receipt')
            path = Path(run['takes'])/(shot_id+'.mp4'); metadata = verify_output(path)
            require((metadata['sha256'],metadata['bytes']) == (receipt['sha256'],receipt['bytes']),
                    'Saved footage differs from durable receipt')
            saved[shot_id] = path
            provenance[shot_id] = dict(scope_id=receipt['scope_id'],binding=binding,sha256=receipt['sha256'])
    require(set(saved) == set(index), 'Every original shot must have verified coverage')
    encode_review(originals, [saved[s['id']] for s in originals], master, destination, frames, partial=False)
    result = dict(status='FULL_SONG_REVIEW_ASSEMBLED_NOT_CREATIVE_APPROVAL',
        manifest_sha256=fingerprint(manifest),sha256=digest(destination),frames=frames,
        duration_seconds=frames/25,width=864,height=448,master_wav_sha256=master_sha256,
        sources=provenance)
    atomic_json(destination.with_suffix('.json'),result)
    return result
