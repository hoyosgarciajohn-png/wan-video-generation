"""Verified local uploads and immutable timeline/export admission."""
import base64
import binascii
from copy import deepcopy
import hashlib
import json
import math
import os
import subprocess
import tempfile
from uuid import uuid4

from services.controller.commands import RenderCommands
from services.controller.service import canonical, stamp
from services.controller.studio import require
from workers.gpu.common import scoped, sync_dir

TYPES = {
    'image/png': ('image', 'png_pipe', 'png', '.png'),
    'image/jpeg': ('image', 'jpeg_pipe', 'mjpeg', '.jpg'),
    'image/webp': ('image', 'webp_pipe', 'webp', '.webp'),
    'audio/wav': ('audio', 'wav', None, '.wav'),
    'audio/mpeg': ('audio', 'mp3', 'mp3', '.mp3'),
}


def inspect_upload(path, data, mime, duration_cap):
    kind, demuxer, codec, _ = TYPES[mime]
    signatures = {
        'image/png': data.startswith(b'\x89PNG\r\n\x1a\n'),
        'image/jpeg': data.startswith(b'\xff\xd8\xff'),
        'image/webp': data[:4] == b'RIFF' and data[8:12] == b'WEBP',
        'audio/wav': data[:4] == b'RIFF' and data[8:12] == b'WAVE',
        'audio/mpeg': data.startswith(b'ID3') or (len(data) > 1 and data[0] == 255 and data[1] & 224 == 224),
    }
    require(signatures[mime], 'Media signature does not match MIME type')
    args = ['-protocol_whitelist', 'file,pipe', '-f', demuxer, '-i', str(path)]
    try:
        result = json.loads(subprocess.check_output(['ffprobe', '-v', 'error', *args,
                            '-show_streams', '-show_format', '-of', 'json'], stderr=subprocess.DEVNULL, timeout=15))
        streams = result.get('streams', [])
        require(len(streams) == 1, 'Upload must contain exactly one media stream')
        stream = streams[0]
        require(stream.get('codec_type') == ('video' if kind == 'image' else 'audio'), 'Unexpected media stream')
        actual_codec = stream.get('codec_name', '')
        require(actual_codec == codec if codec else actual_codec in ('pcm_s16le','pcm_s24le','pcm_s32le','pcm_f32le','pcm_u8'),
                'Unsupported upload codec')
        if kind == 'image':
            require(0 < stream.get('width', 0) <= 4096 and 0 < stream.get('height', 0) <= 4096,
                    'Image dimensions exceed 4096 pixels')
            duration = None
        else:
            seconds = float(result['format']['duration'])
            require(math.isfinite(seconds) and 0 < seconds * 1000 <= duration_cap and
                    0 < stream.get('channels', 0) <= 2 and 0 < int(stream.get('sample_rate', 0)) <= 96000,
                    'Audio exceeds duration or channel/sample-rate limits')
            duration = round(seconds * 1000)
        subprocess.run(['ffmpeg', '-nostdin', '-v', 'error', '-xerror', '-threads', '1', *args,
                        '-f', 'null', '-'], check=True, stdout=subprocess.DEVNULL,
                       stderr=subprocess.DEVNULL, timeout=20)
        return kind, duration
    except (subprocess.SubprocessError, KeyError, TypeError, json.JSONDecodeError) as error:
        raise ValueError('Upload failed media verification') from error


class MediaCommands:
    def __init__(self, studio):
        self.studio, self.control = studio, studio.control
        self.commands = RenderCommands(studio)
        with self.control.transaction() as db:
            db.execute('''CREATE TABLE IF NOT EXISTS export_jobs (
                id TEXT PRIMARY KEY, project TEXT NOT NULL, owner TEXT NOT NULL,
                snapshot TEXT NOT NULL, state TEXT NOT NULL, error TEXT)''')

    def _existing(self, db, owner, project, operation, request, collection):
        bundle = self.control._load(db, owner, project)
        prior = self.commands._receipt(db, project, operation, request)
        if prior:
            value = next(v for v in bundle[collection]
                         if (f"{v['id']}:{v['revision']}" if collection == 'timelines' else v['id']) == prior)
            return dict(**{operation: deepcopy(value)}, workspace=self.studio._get(db, owner))
        return None

    def upload(self, owner, project_id, payload):
        self.studio._owner(owner)
        self.commands._request(payload, ('name','mime_type','data_base64','expected_revision','idempotency_key'))
        require(isinstance(payload['name'], str) and 0 < len(payload['name'].strip()) <= 500, 'Invalid asset name')
        mime = payload['mime_type']
        require(isinstance(mime, str) and mime in TYPES, 'Unsupported media MIME type')
        encoded = payload['data_base64']
        limit = (1 if TYPES[mime][0] == 'image' else 4) * 1024 * 1024
        require(isinstance(encoded, str) and 0 < len(encoded) <= 4 * ((limit + 2) // 3), 'Upload exceeds size limit')
        # Authorize before expensive media parsing. Recheck in the commit transaction.
        bundle = self.control.bundle(owner, project_id)
        try:
            data = base64.b64decode(encoded, validate=True)
        except (binascii.Error, ValueError) as error:
            raise ValueError('Invalid base64 media') from error
        require(0 < len(data) <= limit, 'Upload exceeds size limit')
        checksum = hashlib.sha256(data).hexdigest()
        request = {k: v for k, v in payload.items() if k != 'data_base64'}
        request.update(sha256=checksum, bytes=len(data))
        with self.control.transaction() as db:
            prior = self._existing(db, owner, project_id, 'asset', request, 'assets')
            if prior:
                return prior
            self.studio._check_revision(db, owner, payload['expected_revision'])
        stage_root = self.control.asset_root / '.staging'
        stage_root.mkdir(exist_ok=True, mode=0o700)
        with tempfile.TemporaryDirectory(dir=stage_root) as directory:
            from pathlib import Path
            stage = Path(directory) / ('input' + TYPES[mime][3])
            stage.write_bytes(data)
            kind, duration = inspect_upload(stage, data, mime, bundle['project']['runtime_limit_ms'])
            asset_id = 'asset-' + uuid4().hex
            key = f'projects/{project_id}/uploads/{asset_id}{TYPES[mime][3]}'
            destination = scoped(self.control.asset_root, key)
            asset = dict(id=asset_id, project_id=project_id, owner_id=owner, kind=kind,
                         object_key=key, mime_type=mime, bytes=len(data), sha256=checksum, duration_ms=duration)
            published = False
            try:
                with self.control.transaction() as db:
                    prior = self._existing(db, owner, project_id, 'asset', request, 'assets')
                    if prior:
                        return prior
                    self.studio._check_revision(db, owner, payload['expected_revision'])
                    bundle = self.control._load(db, owner, project_id)
                    require(duration is None or duration <= bundle['project']['runtime_limit_ms'], 'Audio exceeds project duration')
                    metadata = self.studio._project(db, bundle)
                    bundle['assets'].append(asset)
                    metadata['assetNames'][asset_id] = payload['name'].strip()
                    values = {k: metadata[k] for k in ('scenes','shotHistory','selectedTakes','assetNames','script')}
                    destination.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
                    with stage.open('rb') as source:
                        os.fsync(source.fileno())
                    os.link(stage, destination)
                    published = True
                    sync_dir(destination.parent)
                    self.control._save(db, bundle)
                    db.execute('UPDATE studio_projects SET metadata=? WHERE project=?', (canonical(values), project_id))
                    self.studio._advance(db, owner)
                    self.commands._remember(db, project_id, 'asset', request, asset_id)
                    response = dict(asset=deepcopy(asset), workspace=self.studio._get(db, owner))
                return response
            except Exception:
                if published:
                    destination.unlink(missing_ok=True)
                raise

    def assemble(self, owner, project_id, payload):
        self.studio._owner(owner)
        self.commands._request(payload, ('expected_revision','idempotency_key','audio_asset_id'))
        require(payload['audio_asset_id'] is None or isinstance(payload['audio_asset_id'], str), 'Invalid soundtrack')
        with self.control.transaction() as db:
            prior = self._existing(db, owner, project_id, 'timeline', payload, 'timelines')
            if prior:
                return prior
            self.studio._check_revision(db, owner, payload['expected_revision'])
            bundle = self.control._load(db, owner, project_id)
            project = self.studio._project(db, bundle)
            takes = {t['id']: t for t in bundle['takes']}
            items = []
            for shot in bundle['shots']:
                take = takes.get(project['selectedTakes'].get(shot['id']))
                require(take is not None and take['shot_id'] == shot['id'] and take['duration_ms'] >= shot['target_duration_ms'],
                        'Every saved shot requires a selected approved take long enough for its trim')
                items.append(dict(take_id=take['id'], source_in_ms=0, source_out_ms=shot['target_duration_ms']))
            require(bool(items), 'Timeline needs at least one shot')
            duration = sum(i['source_out_ms'] for i in items)
            audio = []
            if payload['audio_asset_id']:
                asset = next((a for a in bundle['assets'] if a['id'] == payload['audio_asset_id'] and a['kind'] == 'audio'), None)
                if asset is None:
                    raise KeyError('Soundtrack unavailable')
                audio.append(dict(asset_id=asset['id'], source_in_ms=0, source_out_ms=min(duration, asset['duration_ms']), timeline_start_ms=0))
            previous = bundle['timelines']
            timeline_id = previous[0]['id'] if previous else 'timeline-' + uuid4().hex
            revision = max((t['revision'] for t in previous if t['id'] == timeline_id), default=0) + 1
            timeline = dict(id=timeline_id, project_id=project_id, revision=revision, duration_ms=duration,
                            items=items, audio=audio, created_at=stamp(self.control.clock()))
            bundle['timelines'].append(timeline)
            self.control._save(db, bundle)
            self.studio._advance(db, owner)
            self.commands._remember(db, project_id, 'timeline', payload, f'{timeline_id}:{revision}')
            return dict(timeline=deepcopy(timeline), workspace=self.studio._get(db, owner))

    def export(self, owner, project_id, payload):
        self.studio._owner(owner)
        require(isinstance(payload, dict) and set(payload) == {'timeline_id','timeline_revision','idempotency_key'}, 'Invalid export command')
        require(isinstance(payload['timeline_id'], str) and type(payload['timeline_revision']) is int and payload['timeline_revision'] > 0 and
                isinstance(payload['idempotency_key'], str) and 0 < len(payload['idempotency_key'].strip()) <= 200, 'Invalid export identity')
        with self.control.transaction() as db:
            prior = self._existing(db, owner, project_id, 'export', payload, 'exports')
            if prior:
                return prior
            bundle = self.control._load(db, owner, project_id)
            if not any(t['id'] == payload['timeline_id'] and t['revision'] == payload['timeline_revision'] for t in bundle['timelines']):
                raise KeyError('Timeline revision unavailable')
            job = dict(id='export-' + uuid4().hex, project_id=project_id, timeline_id=payload['timeline_id'],
                       timeline_revision=payload['timeline_revision'], state='queued', output_asset_id=None,
                       profile=dict(width=1280, height=704, frame_rate=dict(numerator=24, denominator=1),
                                    container='mp4', video_codec='h264', audio_codec='aac'))
            bundle['exports'].append(job)
            self.control._save(db, bundle)
            db.execute('INSERT INTO export_jobs VALUES (?,?,?,?,?,NULL)', (job['id'], project_id, owner, canonical(bundle), 'queued'))
            self.commands._remember(db, project_id, 'export', payload, job['id'])
            return dict(export=deepcopy(job), workspace=self.studio._get(db, owner))
