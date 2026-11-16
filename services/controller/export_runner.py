"""Durable single-job CPU export scheduler with immutable captured input bundles."""
import fcntl
from fractions import Fraction
import json
import os
from pathlib import Path
import sqlite3
import subprocess

from workers.media.export import export_bundle
from workers.gpu.common import digest, scoped, sync_dir


class ExportRunner:
    def __init__(self, control, *, renderer=export_bundle):
        self.control, self.renderer = control, renderer
        self.lock_path = Path(str(Path(control.db_path).resolve()) + '.exports.lock')
        self.job_root = control.asset_root / '.export-work'
        self.last_error = None

    @staticmethod
    def verify(path, timeline, profile):
        # The immutable queued profile also covers legacy 320x180 exports.
        fps = Fraction(profile['frame_rate']['numerator'], profile['frame_rate']['denominator'])
        if (profile['container'], profile['video_codec'], profile['audio_codec']) != ('mp4','h264','aac') or fps <= 0:
            raise ValueError('Unsupported frozen export profile')
        info = json.loads(subprocess.check_output(['ffprobe', '-v', 'error', '-protocol_whitelist', 'file,pipe',
                          '-f', 'mov', '-i', str(path), '-show_streams', '-show_format', '-of', 'json'],
                         stderr=subprocess.DEVNULL, timeout=20))
        streams = info['streams']
        video = [s for s in streams if s['codec_type'] == 'video']
        audio = [s for s in streams if s['codec_type'] == 'audio']
        if (len(video) != 1 or len(audio) != bool(timeline['audio']) or len(streams) != len(video) + len(audio) or
                video[0]['codec_name'] != profile['video_codec'] or
                (video[0]['width'], video[0]['height']) != (profile['width'],profile['height']) or
                Fraction(video[0]['avg_frame_rate']) != fps or
                abs(float(video[0]['duration']) * 1000 - timeline['duration_ms']) > 1000 / fps + 1 or
                (audio and (audio[0]['codec_name'] != 'aac' or
                            abs(float(audio[0]['duration']) * 1000 - timeline['duration_ms']) > 25))):
            raise ValueError('Export output verification failed')

    def tick(self):
        with self.lock_path.open('a') as lock:
            try:
                fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
            except BlockingIOError:
                return False
            with self.control.transaction() as db:
                row = db.execute("SELECT id,project,owner,snapshot FROM export_jobs WHERE state IN ('queued','rendering') ORDER BY rowid LIMIT 1").fetchone()
                if row is None:
                    return False
                export_id, project_id, owner, raw = row
                bundle = self.control._load(db, owner, project_id)
                job = next(j for j in bundle['exports'] if j['id'] == export_id)
                job['state'] = 'rendering'
                self.control._save(db, bundle)
                db.execute("UPDATE export_jobs SET state='rendering',error=NULL WHERE id=?", (export_id,))
            snapshot = json.loads(raw)
            frozen_job = next(j for j in snapshot['exports'] if j['id'] == export_id)
            timeline = next(t for t in snapshot['timelines'] if t['id'] == frozen_job['timeline_id'] and t['revision'] == frozen_job['timeline_revision'])
            try:
                rendered = Path(self.renderer(snapshot, export_id, project_id, self.control.asset_root, self.job_root))
                self.verify(rendered, timeline, frozen_job['profile'])
                checksum = digest(rendered)
                key = f'projects/{project_id}/exports/{export_id}/output.mp4'
                output = scoped(self.control.asset_root, key)
                output.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
                with rendered.open('rb') as source:
                    os.fsync(source.fileno())
                try:
                    os.link(rendered, output)
                except FileExistsError:
                    if digest(output) != checksum:
                        raise ValueError('Immutable export output conflict')
                sync_dir(output.parent)
                self.verify(output, timeline, frozen_job['profile'])
                if digest(output) != checksum:
                    raise ValueError('Export upload changed')
                asset = dict(id='asset-' + export_id, project_id=project_id, owner_id=owner, kind='video',
                             object_key=key, mime_type='video/mp4', bytes=output.stat().st_size,
                             sha256=checksum, duration_ms=timeline['duration_ms'])
                with self.control.transaction() as db:
                    bundle = self.control._load(db, owner, project_id)
                    job = next(j for j in bundle['exports'] if j['id'] == export_id)
                    existing = next((a for a in bundle['assets'] if a['id'] == asset['id']), None)
                    if existing is not None and existing != asset:
                        raise ValueError('Output asset conflict')
                    if existing is None:
                        bundle['assets'].append(asset)
                    job.update(state='succeeded', output_asset_id=asset['id'])
                    self.control._save(db, bundle)
                    db.execute("UPDATE export_jobs SET state='succeeded',error=NULL WHERE id=?", (export_id,))
                self.last_error = None
            except Exception:
                self.last_error = 'export_failed'
                with self.control.transaction() as db:
                    bundle = self.control._load(db, owner, project_id)
                    job = next(j for j in bundle['exports'] if j['id'] == export_id)
                    if job['state'] != 'succeeded':
                        job['state'] = 'failed'
                        self.control._save(db, bundle)
                        db.execute("UPDATE export_jobs SET state='failed',error='export_failed' WHERE id=?", (export_id,))
            return True

    def serve(self, stop_event, *, poll_interval=1):
        if not isinstance(poll_interval, (int,float)) or not 0 < poll_interval <= 60:
            raise ValueError('Invalid scheduler interval')
        while not stop_event.is_set():
            try:
                worked = self.tick()
            except (OSError, sqlite3.Error):
                self.last_error = 'export_scheduler_unavailable'
                worked = False
            if not worked:
                stop_event.wait(poll_interval)
