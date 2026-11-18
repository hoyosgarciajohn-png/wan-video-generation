"""Private LongCat batch preparation and CPU-testable recovery boundaries.

This module cannot create Pods or mint runtime authority. A production operator
must bind its immutable manifest to a valid spend scope and independent guard.
Publishing receipts must come from storage outside the GPU before the next shot.
"""
import hashlib
import json
import math
from pathlib import Path
import re
import subprocess
import time
import wave

from .common import atomic_json, digest, require, scoped

PROTOCOL = 'longcat-song-batch-v1'
MAX_SHOTS = 200
MAX_DURATION_MS = 363000
MAX_RENTAL_SECONDS = 4800


def validate_reference_images(manifest, root):
    """Check decoded inputs before GPU admission; no image pixels are edited."""
    seen = set()
    for shot in manifest['shots']:
        asset = shot['image']
        if asset['path'] in seen: continue
        path = scoped(root, asset['path'])
        require(path.stat().st_size <= 16*1024*1024, 'Reference image too large')
        result = subprocess.run(['ffprobe','-v','error','-select_streams','v:0',
            '-show_entries','stream=width,height,codec_name','-of','json',str(path)],
            check=True,capture_output=True,text=True,timeout=10)
        streams=json.loads(result.stdout)['streams']
        require(len(streams)==1,'One reference image required')
        width,height=streams[0]['width'],streams[0]['height']
        require(streams[0]['codec_name'] in ('png','mjpeg') and
                0<width<=4096 and 0<height<=4096,'Unsupported reference image')
        # Pinned 480p / spatial-factor-32 upstream selects the 448x864 bucket.
        require(.475 < height/width < .55, 'Reference does not select measured 864x448 bucket')
        subprocess.run(['ffmpeg','-nostdin','-v','error','-xerror','-i',str(path),
                        '-frames:v','1','-f','null','-'],check=True,capture_output=True,timeout=10)
        seen.add(asset['path'])


def fingerprint(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, separators=(',', ':'),
                                     allow_nan=False).encode()).hexdigest()


def validate_manifest(value, root):
    """Read-only preflight; the caller uses the same check before allocation."""
    require(value.get('protocol') == PROTOCOL, 'Unknown LongCat batch protocol')
    for key in ('project_id', 'batch_id'):
        require(isinstance(value.get(key), str) and re.fullmatch(r'[a-zA-Z0-9_-]{1,80}', value[key]),
                'Invalid project or batch identity')
    require(value.get('fps') == 25 and type(value.get('duration_frames')) is int
            and 0 < value['duration_frames'] * 40 <= MAX_DURATION_MS, 'Invalid LongCat duration')
    shots = value.get('shots')
    require(isinstance(shots, list) and 1 <= len(shots) <= MAX_SHOTS, 'Invalid shot count')
    cursor = 0
    seen = set()
    for s in shots:
        require(isinstance(s.get('id'), str) and re.fullmatch(r'[a-zA-Z0-9_-]{1,80}', s['id'])
                and s['id'] not in seen, 'Duplicate or invalid shot ID')
        seen.add(s['id'])
        require(type(s.get('frames')) is int and 1 <= s['frames'] <= 93
                and type(s.get('in_frame')) is int and s['in_frame'] == cursor,
                'Noncontiguous or unsupported shot')
        trim = s.get('trim_in_frames')
        require(type(trim) is int and 0 <= trim <= min(cursor, 93 - s['frames']), 'Invalid shot trim')
        require(type(s.get('audio_start_frame')) is int and s['audio_start_frame'] == cursor - trim,
                'Audio offset does not match edit')
        require(type(s.get('seed')) is int and 0 <= s['seed'] < 2**31, 'Invalid seed')
        require(isinstance(s.get('prompt'), str) and s['prompt'].strip(), 'Prompt required')
        require(s.get('headwear_required') is True, 'Head covering is required')
        for kind in ('image', 'audio'):
            asset = s.get(kind, {})
            require(isinstance(asset.get('sha256'), str)
                    and re.fullmatch(r'[a-f0-9]{64}', asset['sha256']), 'Input hash required')
            path = scoped(root, asset['path'])
            require(path.is_file() and digest(path) == asset['sha256'], 'Input missing or changed')
        with wave.open(str(scoped(root, s['audio']['path']))) as audio:
            require((audio.getnchannels(), audio.getsampwidth(), audio.getframerate(), audio.getnframes())
                    == (1, 2, 16000, 75520), 'Conditioning must include one second of lookahead')
        cursor += s['frames']
    require(cursor == value['duration_frames'], 'Timeline duration mismatch')
    return value


def validate_execution(value, now):
    """Bounds are a proposal ceiling, not evidence of owner authorization."""
    require(value.get('protocol') == PROTOCOL, 'Execution protocol mismatch')
    require(type(value.get('admitted_at')) is int and type(value.get('deadline')) is int,
            'Fixed execution times required')
    require(value['admitted_at'] <= now < value['deadline']
            and 0 < value['deadline'] - value['admitted_at'] <= MAX_RENTAL_SECONDS,
            'Expired or extended execution envelope')
    require(value.get('gpu_count') == 2 and value.get('max_hourly_cents') == 878,
            'Unreviewed GPU configuration')
    require(type(value.get('compute_cap_cents')) is int and 0 < value['compute_cap_cents'] <= 1171,
            'Unreviewed compute cap')
    projected = math.ceil((value['deadline'] - value['admitted_at']) * 878 / 3600)
    require(projected <= value['compute_cap_cents'], 'Deadline exceeds compute cap')
    for key in ('scope_id', 'guard_run_id'):
        require(isinstance(value.get(key), str) and value[key].strip(), 'External scope/guard required')
    require(isinstance(value.get('manifest_sha256'), str)
            and re.fullmatch(r'[a-f0-9]{64}', value['manifest_sha256']), 'Manifest binding required')
    return value


def verify_output(path):
    result = subprocess.run(['ffprobe', '-v', 'error', '-select_streams', 'v:0', '-count_frames',
        '-show_entries', 'stream=width,height,avg_frame_rate,nb_read_frames', '-of', 'json', str(path)],
        check=True, capture_output=True, text=True)
    streams = json.loads(result.stdout)['streams']
    require(len(streams) == 1, 'Expected one video stream')
    video = streams[0]
    require(video['avg_frame_rate'] == '25/1' and int(video['nb_read_frames']) == 93,
            'Unexpected output frame count or rate')
    require((video['width'], video['height']) == (864, 448), 'Unreviewed output geometry')
    subprocess.run(['ffmpeg', '-nostdin', '-v', 'error', '-xerror', '-i', str(path),
                    '-map', '0:v:0', '-f', 'null', '-'], check=True, capture_output=True)
    return dict(sha256=digest(path), bytes=Path(path).stat().st_size, **video)


class BatchJournal:
    """A frozen input binding; completed takes are never silently regenerated."""
    def __init__(self, root, manifest, execution, *, clock=time.time):
        self.root = Path(root)
        self.root.mkdir(parents=True, exist_ok=True)
        self.path = self.root / 'batch-journal.json'
        self.manifest, self.execution, self.clock = manifest, execution, clock
        self.binding = fingerprint(manifest)
        validate_execution(execution, clock())
        require(execution['manifest_sha256'] == self.binding, 'Execution manifest changed')
        self.state = {'binding': self.binding, 'scope_id': execution['scope_id'],
                      'deadline': execution['deadline'], 'shots': {}}
        if self.path.exists():
            self.state = json.loads(self.path.read_text())
            require(self.state['binding'] == self.binding
                    and self.state['scope_id'] == execution['scope_id']
                    and self.state['deadline'] == execution['deadline'], 'Queue scope changed')
        self.save()

    def save(self):
        atomic_json(self.path, self.state)

    def output_path(self, shot):
        return self.root / shot['id'] / 'ai2v_demo_1.mp4'

    def decision(self, shot, *, estimated_seconds=60, recovery_seconds=90):
        row = self.state['shots'].get(shot['id'])
        if row is not None:
            require(row['input_sha256'] == fingerprint(shot), 'Shot changed after admission')
            if row['status'] == 'published':
                return 'skip'
            if row['status'] == 'rendered':
                path = self.output_path(shot)
                require(path.is_file() and digest(path) == row['output']['sha256'],
                        'Unpublished output missing or changed')
                return 'publish'
            raise ValueError('Interrupted/failed shot needs explicit recovery; automatic rerender refused')
        if self.clock() + estimated_seconds + recovery_seconds >= self.execution['deadline']:
            return 'stop'
        self.state['shots'][shot['id']] = {'input_sha256': fingerprint(shot), 'status': 'rendering'}
        self.save()
        return 'render'

    def rendered(self, shot, output):
        row = self.state['shots'][shot['id']]
        require(row['status'] == 'rendering', 'Invalid render transition')
        row.update(status='rendered', output=output)
        self.save()

    def publish(self, shot, publisher):
        row = self.state['shots'][shot['id']]
        require(row['status'] == 'rendered', 'Invalid publish transition')
        receipt = publisher(shot['id'], self.output_path(shot), self.binding, row['output'])
        require(isinstance(receipt, dict) and receipt.get('binding') == self.binding
                and receipt.get('shot_id') == shot['id']
                and receipt.get('sha256') == row['output']['sha256']
                and receipt.get('bytes') == row['output']['bytes'], 'Invalid durable receipt')
        row.update(status='published', receipt=receipt)
        self.save()

    def restore_published(self, shot, receipt):
        """Only call with a receipt fetched from the authenticated controller."""
        require(isinstance(receipt, dict) and receipt.get('binding') == self.binding
                and receipt.get('shot_id') == shot['id'] and receipt.get('scope_id') == self.execution['scope_id']
                and isinstance(receipt.get('sha256'), str) and re.fullmatch(r'[a-f0-9]{64}', receipt['sha256'])
                and type(receipt.get('bytes')) is int and receipt['bytes'] > 0, 'Foreign recovery receipt')
        old = self.state['shots'].get(shot['id'])
        if old and 'output' in old:
            require(old['output']['sha256'] == receipt['sha256'], 'Recovery output changed')
        self.state['shots'][shot['id']] = dict(input_sha256=fingerprint(shot), status='published', receipt=receipt)
        self.save()


def run_queue(manifest, execution, input_root, output_root, adapter_factory, publisher,
              *, clock=time.time, verify=verify_output):
    """CPU-testable serial driver; one model load and durable publish per shot."""
    validate_manifest(manifest, input_root)
    journal = BatchJournal(output_root, manifest, execution, clock=clock)
    adapter = None
    try:
        for shot in manifest['shots']:
            action = journal.decision(shot)
            if action == 'stop':
                break
            if action == 'skip':
                continue
            if action == 'render':
                if adapter is None:
                    adapter = adapter_factory()
                adapter.render(shot, input_root, journal.output_path(shot))
                journal.rendered(shot, verify(journal.output_path(shot)))
            journal.publish(shot, publisher)
    finally:
        if adapter is not None:
            adapter.close()
    return journal.state
