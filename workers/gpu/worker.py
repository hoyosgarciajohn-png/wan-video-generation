"""Run one leased attempt with persistent output and a replayable completion journal."""
import fcntl
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import threading
import time

from .common import (ROOT, atomic_json, digest, frame_count, probe, record, require,
                     scoped, sync_dir, timestamp, utcnow, validate_claim)


class LeaseLost(RuntimeError):
    pass


class Lease:
    def __init__(self, client, claim, interval):
        require(0 < interval <= 10, 'Heartbeat interval must be at most ten seconds')
        self.client = client
        self.attempt = claim['attempt']
        self.deadline = timestamp(claim['batch']['deadline_at'])
        self.expiry = timestamp(self.attempt['lease_expires_at'])
        self.interval = interval
        self.progress = 0.0
        self.error = None
        self.stop = threading.Event()

    def check(self):
        if self.error or utcnow() >= min(self.expiry, self.deadline):
            raise LeaseLost('Lease lost or deadline reached')

    def renew(self):
        self.check()
        reply = self.client.heartbeat(self.attempt, self.progress)
        expiry = timestamp(reply['lease_expires_at'])
        if expiry <= utcnow():
            raise LeaseLost('Expired heartbeat reply')
        self.expiry = expiry

    def __enter__(self):
        self.renew()
        self.thread = threading.Thread(target=self.pulse, daemon=True)
        self.thread.start()
        return self

    def pulse(self):
        while not self.stop.wait(self.interval):
            try:
                self.renew()
            except Exception:
                self.error = True
                return

    def __exit__(self, *args):
        self.stop.set()
        self.thread.join(timeout=15)


def execute(command, lease):
    # Pipe contents can contain private prompts. Keep subprocess output out of API errors.
    with tempfile.TemporaryFile() as log:
        process = subprocess.Popen(command, cwd=ROOT, stdout=log, stderr=log)
        try:
            while process.poll() is None:
                lease.check()
                time.sleep(0.1)
            require(process.returncode == 0, 'Render process failed')
            lease.check()
        finally:
            if process.poll() is None:
                process.terminate()
                try:
                    process.wait(timeout=5)
                except subprocess.TimeoutExpired:
                    process.kill()
                    process.wait()


def render(claim, destination, lease, input_root, weights):
    snapshot = claim['shot_snapshot']
    frames = frame_count(snapshot, claim['batch']['execution_mode'])
    if claim['batch']['execution_mode'] == 'fixture':
        execute(['ffmpeg', '-v', 'error', '-nostdin', '-y', '-f', 'lavfi', '-i',
                 'color=c=blue:s=320x180:r=24', '-frames:v', str(frames), '-an',
                 '-c:v', 'libx264', '-threads', '1', '-pix_fmt', 'yuv420p',
                 '-map_metadata', '-1', '-movflags', '+faststart', str(destination)], lease)
        return {'mode': 'fixture', 'gpu_peak_allocated_bytes': None, 'cost_cents': 0}
    require(weights is not None, 'Model directory required')
    image = None
    if claim['input_assets']:
        asset = claim['input_assets'][0]
        image = scoped(input_root, asset['object_key'])
        require(image.stat().st_size == asset['bytes'] and digest(image) == asset['sha256'],
                'Reference checksum mismatch')
    spec = {'snapshot': snapshot, 'frames': frames, 'weights': str(Path(weights).resolve()),
            'image': str(image) if image else None, 'output': str(destination)}
    spec_path = destination.with_suffix('.json')
    atomic_json(spec_path, spec)
    execute([sys.executable, '-m', 'workers.gpu.inference', str(spec_path)], lease)
    return json.loads(destination.with_suffix('.metrics.json').read_text())


def identity(claim):
    a = claim['attempt']
    data = [claim['project'], a['id'], a['lease_id'], a['batch_id'], a['model_profile'],
            claim['shot_snapshot'], claim['input_assets']]
    return hashlib.sha256(json.dumps(data, sort_keys=True).encode()).hexdigest()


def verify_manifest(claim, manifest, path):
    asset, media = manifest['asset'], manifest['media']
    record('asset', asset)
    require(path.stat().st_size == asset['bytes'] and digest(path) == asset['sha256'],
            'Durable output checksum mismatch')
    require(probe(path, claim['attempt']['settings'],
                  frame_count(claim['shot_snapshot'], claim['batch']['execution_mode'])) == media,
            'Durable output metadata mismatch')


def complete(client, claim, manifest):
    # An ambiguous response leaves the journal for identical completion replay.
    take = client.complete(claim['attempt'], manifest)
    record('take', take)
    require(take['project_id'] == claim['project']['id'] and
            take['attempt_id'] == claim['attempt']['id'] and
            take['shot_id'] == claim['attempt']['shot_id'] and
            take['asset_id'] == manifest['asset']['id'], 'Completion response mismatch')
    require(all(take[k] == v for k, v in manifest['media'].items()), 'Take media mismatch')
    return take


def run_once(claim, client, output_root, *, input_root=None, weights=None, interval=5):
    validate_claim(claim)
    a, p = claim['attempt'], claim['project']
    key = f"projects/{p['id']}/attempts/{a['id']}/output.mp4"
    destination = scoped(output_root, key)
    destination.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
    journal = destination.with_name('completion.json')
    with destination.with_name('attempt.lock').open('a') as lock:
        fcntl.flock(lock, fcntl.LOCK_EX)
        if journal.exists():
            saved = json.loads(journal.read_text())
            require(saved['identity'] == identity(claim), 'Attempt replay conflict')
            if destination.exists():
                verify_manifest(claim, saved['manifest'], destination)
                take = complete(client, claim, saved['manifest'])
                return {'contract_version': '0.1.0', **saved['manifest'], 'take': take,
                        'metrics': saved['metrics']}
        with Lease(client, claim, interval) as lease:
            start = time.monotonic()
            try:
                with tempfile.TemporaryDirectory(prefix='render-', dir=destination.parent) as work:
                    local = Path(work) / 'output.mp4'
                    lease.progress = 0.1
                    metrics = render(claim, local, lease, input_root, weights)
                    lease.progress = 0.8
                    media = probe(local, a['settings'], frame_count(claim['shot_snapshot'],
                                                                  claim['batch']['execution_mode']))
                    asset = dict(id='output-' + a['id'], project_id=p['id'], owner_id=p['owner_id'],
                                 kind='video', object_key=key, mime_type='video/mp4',
                                 bytes=local.stat().st_size, sha256=digest(local),
                                 duration_ms=media['duration_ms'])
                    record('asset', asset)
                    metrics['render_and_verify_seconds'] = time.monotonic() - start
                    manifest = {'asset': asset, 'media': media}
                    lease.check()
                    # Journal first, then atomically publish on the same durable filesystem.
                    atomic_json(journal, {'identity': identity(claim), 'manifest': manifest,
                                          'metrics': metrics})
                    with local.open('rb') as source:
                        os.fsync(source.fileno())
                    try:
                        os.link(local, destination)
                    except FileExistsError:
                        require(digest(destination) == asset['sha256'], 'Output conflict')
                    sync_dir(destination.parent)
                    verify_manifest(claim, manifest, destination)
                    lease.check()
            except Exception:
                try:
                    client.fail(a, 'render_failed')
                except Exception:
                    pass
                raise
            # Keep completion outside render failure handling to preserve ambiguous success.
            lease.check()
            lease.progress = 0.95
            take = complete(client, claim, manifest)
            return {'contract_version': '0.1.0', **manifest, 'take': take, 'metrics': metrics}
