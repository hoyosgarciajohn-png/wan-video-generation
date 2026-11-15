"""Shared schema validation, media inspection and immutable local storage."""
import hashlib
import json
import math
import os
from datetime import datetime, timezone
from fractions import Fraction
from pathlib import Path
import subprocess
import tempfile

from jsonschema import Draft202012Validator, FormatChecker

ROOT = Path(__file__).resolve().parents[2]
SCHEMA = json.loads((ROOT / 'contracts/bundle.schema.json').read_text())
LOCK = json.loads(Path(__file__).with_name('model.lock.json').read_text())
FIXTURE_PROFILE = dict(id='fixture-v1', revision='1', checkpoint_ref='fictional:no-model',
                       code_revision='fixture-generator-v1')


def require(condition, message):
    if not condition:
        raise ValueError(message)


def record(kind, value):
    schema = {'$ref': '#/$defs/' + kind, '$defs': SCHEMA['$defs']}
    Draft202012Validator(schema, format_checker=FormatChecker()).validate(value)


def utcnow():
    return datetime.now(timezone.utc)


def stamp():
    return utcnow().isoformat().replace('+00:00', 'Z')


def timestamp(value):
    result = datetime.fromisoformat(value.replace('Z', '+00:00'))
    require(result.tzinfo is not None, 'Timezone required')
    return result


def digest(path):
    with Path(path).open('rb') as source:
        return hashlib.file_digest(source, 'sha256').hexdigest()


def scoped(root, key):
    root = Path(root).resolve()
    require(not Path(key).is_absolute() and '..' not in Path(key).parts and '\\' not in key,
            'Unsafe object key')
    path = (root / key).resolve()
    require(path.is_relative_to(root) and path != root, 'Object escapes mount')
    return path


def atomic_json(path, value):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile(mode='w', dir=path.parent, delete=False) as out:
        temp = Path(out.name)
        json.dump(value, out, indent=2, allow_nan=False)
        out.write('\n')
        out.flush()
        os.fsync(out.fileno())
    try:
        os.replace(temp, path)
        sync_dir(path.parent)
    finally:
        temp.unlink(missing_ok=True)


def sync_dir(path):
    fd = os.open(path, os.O_RDONLY | os.O_DIRECTORY)
    try:
        os.fsync(fd)
    finally:
        os.close(fd)


def frame_count(snapshot, mode):
    requested = math.ceil(snapshot['target_duration_ms'] * 24 / 1000)
    if mode == 'fixture':
        return requested
    # Round upward to the first 4n+1 count, preserving enough footage to trim.
    return 4 * math.ceil((requested - 1) / 4) + 1


def validate_claim(claim):
    require(claim['contract_version'] == '0.1.0', 'Unsupported contract')
    for key, kind in [('project', 'project'), ('batch', 'batch'),
                      ('attempt', 'attempt'), ('shot_snapshot', 'shot_snapshot')]:
        record(kind, claim[key])
    p, b, a, s = (claim[k] for k in ('project', 'batch', 'attempt', 'shot_snapshot'))
    require(p['id'] == b['project_id'] == a['project_id'], 'Project mismatch')
    require(a['batch_id'] == b['id'] and a['shot_id'] == s['shot_id'], 'Assignment mismatch')
    require(a['shot_revision'] == s['revision'] and s in b['shot_snapshots'], 'Snapshot mismatch')
    require(a['settings'] == s['settings'] and a['model_profile'] == b['model_profile'],
            'Frozen configuration mismatch')
    require(a['state'] in ('claimed', 'running'), 'Attempt must be active')
    require(b['state'] == 'rendering', 'Batch must be rendering')
    require(a['completed_at'] is None and a['failure_reason'] is None, 'Attempt already terminal')
    require(timestamp(b['approved_at']) <= timestamp(a['started_at']) < timestamp(b['deadline_at']),
            'Invalid batch window')
    settings = s['settings']
    require(settings['frame_rate'] == {'numerator': 24, 'denominator': 1}, 'Requires 24 fps')
    require(settings['seed'] <= 2**63 - 1 and len(s['prompt']) <= 10000, 'Input exceeds limits')
    mode = b['execution_mode']
    profile = FIXTURE_PROFILE if mode == 'fixture' else LOCK['profile']
    require(a['model_profile'] == profile, 'Unsupported model revision')
    if mode == 'fixture':
        require(all(b['budget'][k] == 0 for k in ('approved_cents','reserved_cents','spent_cents')),
                'Fixture cost must be zero')
        require((settings['width'], settings['height'], settings['steps']) == (320, 180, 1),
                'Fixture requires 320x180 and one step')
        require(1 <= s['target_duration_ms'] <= 5000 and not s['reference_asset_ids'],
                'Fixture duration or references unsupported')
    else:
        require(b['budget']['approved_cents'] > 0, 'Missing approved budget')
        require((settings['width'], settings['height']) in ((1280,704), (704,1280)),
                'Wan profile supports 1280x704 or 704x1280')
        require(1 <= s['target_duration_ms'] <= 5000 and settings['steps'] == 50,
                'Wan profile supports up to five seconds and 50 steps')
        require(len(s['reference_asset_ids']) <= 1, 'One reference image supported')
    assets = claim['input_assets']
    require(len({x['id'] for x in assets}) == len(assets), 'Duplicate input asset')
    require({x['id'] for x in assets} == set(s['reference_asset_ids']), 'Input asset set mismatch')
    for asset in assets:
        record('asset', asset)
        require(asset['project_id'] == p['id'] and asset['owner_id'] == p['owner_id'],
                'Input ownership mismatch')
        require(asset['kind'] == 'image' and asset['bytes'] <= 20_000_000, 'Invalid reference')
        require(asset['object_key'].startswith(f"projects/{p['id']}/"), 'Unscoped input')


def probe(path, settings, frames):
    result = json.loads(subprocess.check_output([
        'ffprobe', '-v', 'error', '-show_streams', '-show_format', '-of', 'json', str(path)
    ], text=True, timeout=30))
    videos = [s for s in result['streams'] if s['codec_type'] == 'video']
    require(len(videos) == 1 and len(result['streams']) == 1, 'Requires one silent video stream')
    video = videos[0]
    require(video['codec_name'] == 'h264', 'Requires H264')
    require((video['width'], video['height']) == (settings['width'], settings['height']),
            'Output dimensions mismatch')
    require(Fraction(video['avg_frame_rate']) == 24 and int(video['nb_frames']) == frames,
            'Output frame count or rate mismatch')
    duration_ms = round(float(result['format']['duration']) * 1000)
    require(abs(duration_ms - round(frames * 1000 / 24)) <= 1, 'Output duration mismatch')
    return dict(duration_ms=duration_ms, width=video['width'], height=video['height'],
                frame_rate={'numerator': 24, 'denominator': 1})

