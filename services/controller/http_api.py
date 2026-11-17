"""Same-origin Studio development host; server-provisioned identities, no paid dispatch."""
import argparse
from collections import defaultdict, deque
from dataclasses import dataclass, field
from hashlib import sha256
from http import cookies
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
import os
from pathlib import Path
import secrets
import re
import threading
import time
from urllib.parse import urlsplit

from jsonschema.exceptions import ValidationError
from services.controller.service import ControlService
from services.controller.studio import StudioWorkspace, StudioConflict
from workers.gpu.common import scoped
from services.controller.commands import RenderCommands
from services.controller.runner import FixtureRunner
from services.controller.media_commands import MediaCommands
from services.controller.export_runner import ExportRunner
from services.controller.uploads import ResumableUploads, CHUNK_SIZE
from services.controller.worker_transport import WorkerTransport, MAX_ARTIFACT_BYTES, IDENTIFIER

COOKIE = 'wan_studio_session'
MAX_BODY = 2 * 1024 * 1024
MAX_UPLOAD_BODY = 6 * 1024 * 1024


def body_limit(path):
    if re.fullmatch(rf'/v1/worker/attempts/({IDENTIFIER})/artifact', path):
        return MAX_ARTIFACT_BYTES
    if re.fullmatch(r"/v1/studio/projects/[A-Za-z0-9_-]+/uploads/[a-f0-9]{32}/chunks/[0-9]+", path):
        return CHUNK_SIZE
    return MAX_UPLOAD_BODY if re.fullmatch(r"/v1/studio/projects/[A-Za-z0-9_-]+/assets", path) else MAX_BODY


class HTTPError(Exception):
    def __init__(self, status):
        self.status = status


@dataclass
class Reply:
    status: int
    data: object = None
    headers: dict = field(default_factory=dict)
    file: Path | None = None
    offset: int = 0
    length: int = 0


class StudioAPI:
    def __init__(self, studio, tokens, origin='http://127.0.0.1:5173', *, clock=time.monotonic, real_jobs=None, live_admission=None):
        parsed = urlsplit(origin)
        if (parsed.scheme not in ('http', 'https') or not parsed.netloc or
                parsed.path or parsed.query or parsed.fragment or parsed.username or
                (parsed.scheme == 'http' and parsed.hostname not in ('localhost', '127.0.0.1'))):
            raise ValueError('Use an HTTPS origin or explicit loopback HTTP origin')
        if not tokens or any(not isinstance(t, str) or len(t) < 32 or not isinstance(o, str) or not o
                             for t, o in tokens.items()):
            raise ValueError('Provision at least one 32-character token and owner identity')
        self.studio, self.origin, self.clock = studio, origin, clock
        if live_admission is not None:
            from services.controller.live_admission import LiveAdmission
            if type(live_admission) is not LiveAdmission or live_admission.control is not studio.control:
                raise ValueError('Live admission requires a trusted service on this controller')
        self.live_admission = live_admission
        self.commands = RenderCommands(studio)
        self.media_commands = MediaCommands(studio)
        self.uploads = ResumableUploads(studio)
        self.workers = WorkerTransport(studio.control, real_jobs=real_jobs)
        self.tokens = {sha256(t.encode()).digest(): owner for t, owner in tokens.items()}
        self.sessions = {}
        self.failures = defaultdict(deque)
        self.lock = threading.Lock()
        self.secure = parsed.scheme == 'https'
        self.allowed_hosts = {parsed.netloc}

    def cookie(self, value, expired=False):
        return (f'{COOKIE}={value}; Path=/; HttpOnly; SameSite=Strict; Max-Age={0 if expired else 1800}'
                + ('; Secure' if self.secure else ''))

    def owner(self, headers):
        jar = cookies.SimpleCookie()
        try:
            jar.load(headers.get('Cookie', ''))
            token = jar[COOKIE].value
        except (KeyError, cookies.CookieError):
            raise HTTPError(401)
        now = self.clock()
        with self.lock:
            value = self.sessions.get(token)
            if not value or now - value[1] >= 1800 or now - value[2] >= 43200:
                self.sessions.pop(token, None)
                raise HTTPError(401)
            self.sessions[token] = (value[0], now, value[2])
            return value[0]

    def _worker_headers(self, headers):
        if headers.get('Host') not in self.allowed_hosts or headers.get('Origin') or headers.get('Sec-Fetch-Site') == 'cross-site':
            raise HTTPError(403)

    def _worker_dispatch(self, method, path, headers, body):
        self._worker_headers(headers)
        authorization = headers.get('Authorization')
        download = re.fullmatch(rf'/v1/worker/attempts/({IDENTIFIER})/inputs/({IDENTIFIER})', path)
        if download:
            if method != 'GET':
                raise HTTPError(405)
            file, asset = self.workers.download(authorization, download[1], headers.get('X-WAN-Lease-ID'), download[2])
            return Reply(200, headers={'Content-Type': asset['mime_type'], 'X-WAN-SHA256': asset['sha256'],
                         'Content-Security-Policy': "default-src 'none'; sandbox"}, file=file, length=asset['bytes'])
        if method != 'POST':
            raise HTTPError(405)
        if headers.get('Content-Type', '').split(';')[0] != 'application/json':
            raise HTTPError(415)
        payload = json.loads(body) if body else {}
        result = self.workers.call(authorization, path[len('/v1/worker/'):], payload)
        return Reply(204 if result is None else 200, result)

    def worker_upload(self, method, path, headers, stream, length):
        try:
            self._worker_headers(headers)
            match = re.fullmatch(rf'/v1/worker/attempts/({IDENTIFIER})/artifact', path)
            if not match or method != 'PUT':
                raise HTTPError(405)
            if headers.get('Content-Type', '').split(';')[0] != 'video/mp4':
                raise HTTPError(415)
            result = self.workers.upload(headers.get('Authorization'), match[1], headers.get('X-WAN-Lease-ID'),
                                         headers.get('X-WAN-SHA256'), length, stream)
            return Reply(200, result)
        except (HTTPError, ValueError) as error:
            status = getattr(error, 'status', 422)
            return Reply(status, {'error': status})
        except (KeyError, PermissionError):
            return Reply(404, {'error': 404})
        except Exception:
            return Reply(503, {'error': 503})

    def dispatch(self, method, path, headers, body=b'', peer='local'):
        try:
            if headers.get('Host') not in self.allowed_hosts:
                raise HTTPError(403)
            if headers.get('Sec-Fetch-Site') == 'cross-site':
                raise HTTPError(403)
            if len(body) > body_limit(path):
                raise HTTPError(413)
            if path.startswith('/v1/worker/'):
                return self._worker_dispatch(method, path, headers, body)
            chunk_match = re.fullmatch(r'/v1/studio/projects/([A-Za-z0-9_-]+)/uploads/([a-f0-9]{32})/chunks/([0-9]+)', path)
            raw_chunk = method == 'PUT' and chunk_match is not None
            # No cross-origin requests, even on session establishment. Custom header
            # + JSON content type excludes form posts; no CORS preflight is granted.
            if method not in ('GET', 'HEAD'):
                if headers.get('Origin') != self.origin or headers.get('X-WAN-Request') != 'studio':
                    raise HTTPError(403)
                if headers.get('Content-Type', '').split(';')[0] != ('application/octet-stream' if raw_chunk else 'application/json'):
                    raise HTTPError(415)
            value = {} if raw_chunk else (json.loads(body) if body else {})
            if not isinstance(value, dict):
                raise HTTPError(422)
            if path == '/v1/studio/session':
                if method == 'POST':
                    now = self.clock()
                    with self.lock:
                        # Bound session state and clean expired sessions at login.
                        self.sessions = {k: v for k, v in self.sessions.items()
                                         if now-v[1] < 1800 and now-v[2] < 43200}
                        attempts = self.failures[peer]
                        while attempts and now-attempts[0] >= 60:
                            attempts.popleft()
                        if len(attempts) >= 10 or len(self.sessions) >= 1000:
                            raise HTTPError(429)
                        supplied = value.get('token')
                        owner = self.tokens.get(sha256(supplied.encode()).digest()) if isinstance(supplied, str) else None
                        if not owner:
                            attempts.append(now)
                            raise HTTPError(401)
                        token = secrets.token_urlsafe(32)
                        self.sessions[token] = (owner, now, now)
                    return Reply(200, {'owner_id': owner}, {'Set-Cookie': self.cookie(token)})
                owner = self.owner(headers)
                if method == 'GET':
                    return Reply(200, {'owner_id': owner})
                if method == 'DELETE':
                    jar = cookies.SimpleCookie(headers.get('Cookie', ''))
                    with self.lock:
                        self.sessions.pop(jar[COOKIE].value, None)
                    return Reply(200, {}, {'Set-Cookie': self.cookie('', True)})
                raise HTTPError(405)
            owner = self.owner(headers)
            live_match = re.fullmatch(r'/v1/studio/projects/([A-Za-z0-9_-]+)/live/(approvals|batches)(?:/([A-Za-z0-9_-]+)(?:/(revoke|cancel))?)?', path)
            if live_match:
                if self.live_admission is None:
                    raise HTTPError(404)
                project_id, collection, record_id, action = live_match.groups()
                try:
                    if method == 'POST' and record_id is None:
                        operation = self.live_admission.approve if collection == 'approvals' else self.live_admission.submit
                        return Reply(200, operation(owner, project_id, value))
                    if method == 'POST' and collection == 'approvals' and action == 'revoke' and value == {}:
                        return Reply(200, self.live_admission.revoke(owner, project_id, record_id))
                    if method == 'POST' and collection == 'batches' and action == 'cancel' and value == {}:
                        from services.controller.live_execution import LiveExecution
                        executor = self.workers.real_jobs
                        operation = executor.cancel if type(executor) is LiveExecution else self.live_admission.cancel
                        return Reply(200, operation(owner, project_id, record_id))
                    if method == 'GET' and collection == 'batches' and record_id and action is None:
                        from services.controller.live_execution import LiveExecution
                        executor = self.workers.real_jobs
                        operation = executor.status if type(executor) is LiveExecution else self.live_admission.status
                        return Reply(200, operation(owner, project_id, record_id))
                except KeyError:
                    raise HTTPError(404)
                raise HTTPError(405)
            upload_match = re.fullmatch(r'/v1/studio/projects/([A-Za-z0-9_-]+)/uploads(?:/([a-f0-9]{32})(?:/(finish))?)?', path)
            if chunk_match or upload_match:
                try:
                    if chunk_match:
                        if method != 'PUT':
                            raise HTTPError(405)
                        return Reply(200, self.uploads.chunk(owner, chunk_match[1], chunk_match[2], int(chunk_match[3]), body))
                    project_id, upload_id, action = upload_match.groups()
                    if upload_id is None and method == 'POST':
                        return Reply(200, self.uploads.begin(owner, project_id, value))
                    if upload_id and action == 'finish' and method == 'POST':
                        return Reply(200, self.uploads.finish(owner, project_id, upload_id, value))
                    if upload_id and action is None and method == 'GET':
                        return Reply(200, self.uploads.get(owner, project_id, upload_id))
                    if upload_id and action is None and method == 'DELETE':
                        return Reply(200, self.uploads.abort(owner, project_id, upload_id))
                    raise HTTPError(405)
                except KeyError:
                    raise HTTPError(404)
            media_match = re.fullmatch(r'/v1/studio/projects/([A-Za-z0-9_-]+)/(assets|timelines|exports)', path)
            if media_match:
                if method != 'POST':
                    raise HTTPError(405)
                operation = {'assets': self.media_commands.upload, 'timelines': self.media_commands.assemble,
                             'exports': self.media_commands.export}[media_match[2]]
                try:
                    return Reply(200, operation(owner, media_match[1], value))
                except KeyError:
                    raise HTTPError(404)
            command_match = re.fullmatch(r'/v1/studio/projects/([A-Za-z0-9_-]+)/(batches|takes)(?:/([A-Za-z0-9_-]+)/(cancel|review))?', path)
            if command_match:
                if method != 'POST':
                    raise HTTPError(405)
                project_id, collection, record_id, action = command_match.groups()
                try:
                    if collection == 'batches' and record_id is None:
                        return Reply(200, self.commands.submit(owner, project_id, value))
                    if collection == 'batches' and action == 'cancel':
                        return Reply(200, self.commands.cancel(owner, project_id, record_id))
                    if collection == 'takes' and action == 'review':
                        return Reply(200, self.commands.review(owner, project_id, record_id, value))
                except KeyError:
                    raise HTTPError(404)
                raise HTTPError(404)
            asset_match = re.fullmatch(r'/v1/studio/projects/([A-Za-z0-9_-]+)/assets/([A-Za-z0-9_-]+)/content', path)
            if asset_match and method == 'GET':
                try:
                    project = self.studio.get_project(owner, asset_match[1])
                    asset = next(a for a in project['bundle']['assets'] if a['id'] == asset_match[2])
                    file = scoped(self.studio.control.asset_root, asset['object_key'])
                    size = file.stat().st_size
                except (KeyError, StopIteration, OSError, ValueError):
                    raise HTTPError(404)
                allowed = {'video/mp4', 'audio/wav', 'audio/mpeg', 'audio/mp4', 'image/png', 'image/jpeg', 'image/webp'}
                if asset['mime_type'] not in allowed or size != asset['bytes']:
                    raise HTTPError(404)
                start, end, status = 0, size - 1, 200
                output_headers = {'Content-Type': asset['mime_type'], 'Accept-Ranges': 'bytes',
                                  'Content-Security-Policy': "default-src 'none'; sandbox"}
                if headers.get('Range'):
                    match = re.fullmatch(r'bytes=(\d*)-(\d*)', headers['Range'])
                    if not match or not any(match.groups()):
                        raise HTTPError(416)
                    if match[1]:
                        start = int(match[1]); end = min(int(match[2]), size-1) if match[2] else size-1
                    else:
                        start = max(0, size-int(match[2]))
                    if start > end or start >= size or start < 0:
                        raise HTTPError(416)
                    status = 206
                    output_headers['Content-Range'] = f'bytes {start}-{end}/{size}'
                return Reply(status, headers=output_headers, file=file, offset=start, length=end-start+1)
            if path == '/v1/studio/workspaces' and method == 'GET':
                workspace = self.studio.get(owner)
                return Reply(200, {'workspaces': [{'id': 'default', 'title': 'My studio',
                                                  'revision': workspace['revision']}]})
            if path == '/v1/studio/workspaces' and method == 'POST':
                workspace = self.studio.create(owner, value['title'], value['kind'], value['expected_revision'])
                return Reply(201, {'id': 'default', 'workspace': workspace})
            if path == '/v1/studio/workspaces/default':
                if method == 'GET':
                    return Reply(200, {'id': 'default', 'workspace': self.studio.get(owner)})
                if method == 'PUT':
                    workspace = self.studio.save(owner, value['workspace'], value['expected_revision'])
                    return Reply(200, {'id': 'default', 'workspace': workspace})
                raise HTTPError(405)
            raise HTTPError(404)
        except StudioConflict:
            return Reply(409, {'error': 409})
        except HTTPError as error:
            return Reply(error.status, {'error': error.status})
        except (json.JSONDecodeError, UnicodeDecodeError, ValidationError, ValueError, TypeError, KeyError) as error:
            # Service errors carry only a numeric public status; no tokens, paths or
            # submitted content are returned to clients or request logs.
            status = getattr(error, 'status', getattr(error, 'code', 422))
            return Reply(status, {'error': status})
        except PermissionError:
            return Reply(404, {'error': 404})
        except Exception:
            return Reply(503, {'error': 503})


def make_server(api, address=('127.0.0.1', 8787)):
    class Handler(BaseHTTPRequestHandler):
        server_version = 'WANStudio'

        def setup(self):
            super().setup()
            self.connection.settimeout(15)

        def log_message(self, *_):
            pass  # Neither submitted tokens nor project text belongs in access logs.

        def respond(self):
            if self.headers.get('Transfer-Encoding'):
                reply = Reply(400, {'error': 400})
                self.close_connection = True
            else:
                try:
                    lengths = self.headers.get_all('Content-Length', [])
                    if len(lengths) > 1:
                        raise ValueError()
                    size = int(lengths[0]) if lengths else 0
                    if not 0 <= size <= body_limit(self.path):
                        raise ValueError()
                    if re.fullmatch(rf'/v1/worker/attempts/({IDENTIFIER})/artifact', self.path):
                        # Worker outputs stream to a bounded stage, never into one HTTP body allocation.
                        self.close_connection = True
                        reply = api.worker_upload(self.command, self.path, self.headers, self.rfile, size)
                    else:
                        body = self.rfile.read(size)
                        if len(body) != size:
                            raise ValueError()
                        reply = api.dispatch(self.command, self.path, self.headers, body, self.client_address[0])
                except (ValueError, TimeoutError):
                    reply = Reply(413, {'error': 413})
                    self.close_connection = True
            data = b'' if reply.status == 204 else json.dumps(reply.data, separators=(',', ':'), allow_nan=False).encode()
            self.send_response(reply.status)
            for key, value in {'Content-Type': 'application/json', 'Cache-Control': 'no-store',
                               'X-Content-Type-Options': 'nosniff', **reply.headers}.items():
                self.send_header(key, value)
            self.send_header('Content-Length', str(reply.length if reply.file else len(data)))
            self.end_headers()
            if reply.file:
                with reply.file.open('rb') as source:
                    source.seek(reply.offset)
                    remaining = reply.length
                    while remaining:
                        chunk = source.read(min(65536, remaining))
                        if not chunk:
                            break
                        self.wfile.write(chunk)
                        remaining -= len(chunk)
            else:
                self.wfile.write(data)

        do_GET = do_POST = do_PUT = do_DELETE = do_OPTIONS = respond

    server = ThreadingHTTPServer(address, Handler)
    api.allowed_hosts.add(f'{server.server_address[0]}:{server.server_address[1]}')
    return server


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--database', type=Path, default=Path('studio.sqlite'))
    parser.add_argument('--assets', type=Path, default=Path('studio-assets'))
    parser.add_argument('--port', type=int, default=8787)
    args = parser.parse_args()
    tokens = json.loads(os.environ['WAN_STUDIO_TOKENS'])
    control = ControlService(args.database, args.assets)
    api = StudioAPI(StudioWorkspace(control), tokens, os.environ.get('WAN_STUDIO_ORIGIN', 'http://127.0.0.1:5173'))
    server = make_server(api, ('127.0.0.1', args.port))
    stop = threading.Event()
    worker = threading.Thread(target=FixtureRunner(control).serve, args=(stop,), daemon=True)
    worker.start()
    exporter = threading.Thread(target=ExportRunner(control).serve, args=(stop,), daemon=True)
    exporter.start()
    print(f'WAN Studio local API on 127.0.0.1:{server.server_port}; paid dispatch disabled', flush=True)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        stop.set()
        server.server_close()
        worker.join(timeout=30)
        exporter.join(timeout=30)


if __name__ == '__main__':
    main()
