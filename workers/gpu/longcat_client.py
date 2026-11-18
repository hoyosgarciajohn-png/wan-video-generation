"""HTTPS-only LongCat inputs and synchronous durable output acknowledgements."""
import hashlib
import json
import os
from pathlib import Path
import tempfile
from urllib.parse import quote
from urllib.request import Request

from .client import WorkerClient, WorkerAPIError, MAX_ARTIFACT_BYTES
from .common import digest, require, scoped, sync_dir


class LongCatClient(WorkerClient):
    def request(self, route, *, method='GET', data=None, headers=None):
        return Request(self.base + '/v1/longcat/' + route, data=data, method=method,
                       headers={'Authorization': 'Bearer ' + self.token, **(headers or {})})

    def post(self, route, body):
        return self.json_request(self.request(route, method='POST', data=json.dumps(body).encode(),
                                 headers={'Content-Type': 'application/json'}))

    def configuration(self):
        return self.json_request(self.request('configuration'))

    def receipt(self, shot_id):
        return self.json_request(self.request('shots/' + quote(shot_id, safe='') + '/receipt'))

    def start(self, shot_id):
        return self.post('shots/' + quote(shot_id, safe='') + '/start', {})

    def download(self, manifest, root):
        root = Path(root); root.mkdir(parents=True, exist_ok=True)
        done = set()
        for shot in manifest['shots']:
            for kind in ('image', 'audio'):
                asset = shot[kind]; path = scoped(root, asset['path'])
                if path in done: continue
                if path.is_file() and digest(path) == asset['sha256']:
                    done.add(path); continue
                path.parent.mkdir(parents=True, exist_ok=True)
                request = self.request('shots/' + quote(shot['id'], safe='') + '/inputs/' + kind)
                temp = None
                try:
                    with self.opener.open(request, timeout=self.timeout) as response:
                        length = int(response.headers['Content-Length'])
                        require(0 < length <= 16*1024*1024 and response.headers.get('X-WAN-SHA256') == asset['sha256'],
                                'Input response mismatch')
                        with tempfile.NamedTemporaryFile(dir=path.parent, delete=False) as out:
                            temp = Path(out.name); remaining = length
                            while remaining:
                                chunk = response.read(min(65536, remaining))
                                require(chunk, 'Incomplete input'); out.write(chunk); remaining -= len(chunk)
                            out.flush(); os.fsync(out.fileno())
                    require(digest(temp) == asset['sha256'], 'Input checksum mismatch')
                    os.replace(temp, path); sync_dir(path.parent); done.add(path)
                finally:
                    if temp is not None: temp.unlink(missing_ok=True)

    def publish(self, shot_id, path, binding, metadata):
        def checked(receipt):
            require(isinstance(receipt, dict) and all(receipt.get(k) == v for k,v in
                    dict(binding=binding, shot_id=shot_id, sha256=metadata['sha256'], bytes=metadata['bytes']).items()),
                    'Durable receipt mismatch')
            return receipt
        existing = self.receipt(shot_id)
        if existing is not None: return checked(existing)
        path = Path(path)
        require(0 < metadata['bytes'] <= MAX_ARTIFACT_BYTES and path.stat().st_size == metadata['bytes']
                and digest(path) == metadata['sha256'], 'Output changed before upload')
        try:
            with path.open('rb') as stream:
                receipt = self.json_request(self.request('shots/' + quote(shot_id,safe='') + '/artifact',
                    method='PUT', data=stream, headers={'Content-Type': 'video/mp4',
                    'Content-Length': str(metadata['bytes']), 'X-WAN-SHA256': metadata['sha256']}))
        except WorkerAPIError:
            # A lost reply is reconciled without another render or another upload.
            receipt = self.receipt(shot_id)
            if receipt is None: raise
        return checked(receipt)
