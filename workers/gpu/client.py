"""Scoped worker HTTP transport. No provider operations or shared storage assumption."""
import hashlib
import json
import os
from pathlib import Path
import tempfile
from urllib.error import HTTPError, URLError
from urllib.parse import quote, urlsplit
from urllib.request import Request, build_opener, HTTPRedirectHandler

from .common import digest, scoped, sync_dir

MAX_ARTIFACT_BYTES = 32 * 1024 * 1024
MAX_REPLY_BYTES = 2_000_000


class WorkerAPIError(RuntimeError):
    def __init__(self, status):
        self.status = status
        super().__init__(f'Worker API status {status}')


class NoRedirect(HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        return None


class WorkerClient:
    def __init__(self, base_url, token, *, timeout=10, allow_local_http=False):
        url = urlsplit(base_url)
        local = allow_local_http and url.scheme == 'http' and url.hostname in ('127.0.0.1', 'localhost')
        if ((url.scheme != 'https' and not local) or not url.hostname or url.username or url.password
                or url.path not in ('', '/') or url.query or url.fragment):
            raise ValueError('Worker API requires an HTTPS origin; HTTP requires explicit loopback development mode')
        if not token or '\n' in token or '\r' in token:
            raise ValueError('Worker token required')
        self.base = base_url.rstrip('/')
        self.token = token
        self.timeout = timeout
        self.opener = build_opener(NoRedirect())

    @property
    def binding(self):
        # Identifies a durable local claim journal without persisting credentials.
        return hashlib.sha256((self.base + '\0' + self.token).encode()).hexdigest()

    def request(self, route, *, method='POST', data=None, headers=None):
        return Request(self.base + '/v1/worker/' + route, data=data, method=method,
                       headers={'Authorization': 'Bearer ' + self.token, **(headers or {})})

    def json_request(self, request):
        try:
            with self.opener.open(request, timeout=self.timeout) as response:
                if response.status == 204:
                    return None
                raw = response.read(MAX_REPLY_BYTES + 1)
                if len(raw) > MAX_REPLY_BYTES:
                    raise WorkerAPIError(502)
                result = json.loads(raw)
                if not isinstance(result, dict):
                    raise WorkerAPIError(502)
                return result
        except HTTPError as error:
            status = error.code
            error.close()
            raise WorkerAPIError(status) from None
        except (URLError, TimeoutError, OSError):
            raise WorkerAPIError(503) from None
        except (ValueError, UnicodeDecodeError):
            raise WorkerAPIError(502) from None

    def post(self, route, body):
        return self.json_request(self.request(route, data=json.dumps(body).encode(),
                                 headers={'Content-Type': 'application/json'}))

    def claim(self):
        # Never retry automatically; an explicit retry is reconciled by the server.
        return self.post('claim', {})

    def heartbeat(self, attempt, progress):
        return self.post(f"attempts/{quote(attempt['id'], safe='')}/heartbeat",
                         {'lease_id': attempt['lease_id'], 'progress': progress})

    def telemetry(self, attempt, metrics):
        return self.post(f"attempts/{quote(attempt['id'], safe='')}/telemetry",
                         {'lease_id': attempt['lease_id'], 'metrics': metrics})

    def complete(self, attempt, manifest):
        return self.post(f"attempts/{quote(attempt['id'], safe='')}/complete",
                         {'lease_id': attempt['lease_id'], 'output_asset_manifest': manifest})

    def fail(self, attempt, code):
        return self.post(f"attempts/{quote(attempt['id'], safe='')}/fail",
                         {'lease_id': attempt['lease_id'], 'code': code})

    def upload(self, attempt, manifest, path):
        asset = manifest['asset']
        path = Path(path)
        if (not 0 < asset['bytes'] <= MAX_ARTIFACT_BYTES or path.stat().st_size != asset['bytes']
                or digest(path) != asset['sha256']):
            raise ValueError('Worker artifact size/checksum mismatch')
        with path.open('rb') as source:
            receipt = self.json_request(self.request(f"attempts/{quote(attempt['id'], safe='')}/artifact",
                method='PUT', data=source, headers={'Content-Type': 'video/mp4', 'Content-Length': str(asset['bytes']),
                'X-WAN-Lease-ID': attempt['lease_id'], 'X-WAN-SHA256': asset['sha256']}))
        if receipt != {key: asset[key] for key in ('bytes', 'sha256', 'object_key')}:
            raise WorkerAPIError(502)
        return receipt

    def download_inputs(self, claim, root):
        attempt = claim['attempt']
        for asset in claim['input_assets']:
            if not 0 < asset['bytes'] <= MAX_ARTIFACT_BYTES:
                raise ValueError('Worker input exceeds transfer limit')
            destination = scoped(root, asset['object_key'])
            if destination.exists() and destination.stat().st_size == asset['bytes'] and digest(destination) == asset['sha256']:
                continue
            destination.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
            temporary = None
            request = self.request(f"attempts/{quote(attempt['id'], safe='')}/inputs/{quote(asset['id'], safe='')}", method='GET',
                                   headers={'X-WAN-Lease-ID': attempt['lease_id']})
            try:
                with self.opener.open(request, timeout=self.timeout) as response, tempfile.NamedTemporaryFile(dir=destination.parent, delete=False) as output:
                    temporary = Path(output.name)
                    count, checksum = 0, hashlib.sha256()
                    while chunk := response.read(65536):
                        count += len(chunk)
                        if count > asset['bytes']:
                            raise ValueError('Worker input length mismatch')
                        checksum.update(chunk)
                        output.write(chunk)
                    if count != asset['bytes'] or checksum.hexdigest() != asset['sha256']:
                        raise ValueError('Worker input checksum mismatch')
                    output.flush()
                    os.fsync(output.fileno())
                os.replace(temporary, destination)
                sync_dir(destination.parent)
            except HTTPError as error:
                status = error.code
                error.close()
                raise WorkerAPIError(status) from None
            except (URLError, TimeoutError, OSError):
                raise WorkerAPIError(503) from None
            finally:
                if temporary is not None:
                    temporary.unlink(missing_ok=True)
