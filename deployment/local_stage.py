"""Single-origin, loopback-only staging host. Not a production HTTP server."""
import argparse
import json
import mimetypes
import os
from pathlib import Path
import signal
import threading
from urllib.parse import unquote, urlsplit

from services.controller.http_api import StudioAPI, make_server
from services.controller.service import ControlService
from services.controller.studio import StudioWorkspace
from services.controller.runner import FixtureRunner
from services.controller.export_runner import ExportRunner

CSP = ("default-src 'self'; script-src 'self'; style-src 'self'; "
       "img-src 'self' data: blob:; media-src 'self' data: blob:; "
       "font-src 'self'; connect-src 'self'; object-src 'none'; "
       "base-uri 'self'; frame-ancestors 'none'; form-action 'self'")


def validate_origin(origin):
    parsed = urlsplit(origin)
    if (parsed.scheme != 'http' or parsed.hostname not in ('127.0.0.1', 'localhost')
            or parsed.username or parsed.password or parsed.path or parsed.query or parsed.fragment):
        raise ValueError('Staging requires an exact loopback HTTP origin without a path')
    return origin


def create_server(control, tokens, static_root, origin, address=('127.0.0.1', 8080)):
    validate_origin(origin)
    static_root = Path(static_root).resolve(strict=True)
    if not (static_root / 'index.html').is_file():
        raise ValueError('Build apps/studio/dist before starting staging')
    api = StudioAPI(StudioWorkspace(control), tokens, origin)
    server = make_server(api, address)
    base = server.RequestHandlerClass
    server.worker_threads = []

    class Handler(base):
        def static_reply(self, status, data=b'', mime='text/plain; charset=utf-8', head=False):
            self.send_response(status)
            for key, value in {'Content-Type': mime, 'Content-Length': str(len(data)),
                               'Cache-Control': 'no-store', 'X-Content-Type-Options': 'nosniff',
                               'Content-Security-Policy': CSP, 'Referrer-Policy': 'no-referrer'}.items():
                self.send_header(key, value)
            self.end_headers()
            if not head:
                self.wfile.write(data)

        def serve_static(self, head=False):
            if self.headers.get('Host') not in api.allowed_hosts:
                return self.static_reply(403, head=head)
            path = unquote(urlsplit(self.path).path)
            if path == '/v1' or path.startswith('/v1/'):
                if head:
                    return self.static_reply(405, head=True)
                return self.respond()  # Never fall back to the SPA for API paths.
            if path == '/healthz':
                try:
                    with control.transaction() as db:
                        db.execute('SELECT 1').fetchone()
                    healthy = all(worker.is_alive() for worker in server.worker_threads)
                except Exception:
                    healthy = False
                return self.static_reply(200 if healthy else 503,
                                         json.dumps({'ready': healthy, 'mode': 'local-fixture'}).encode(),
                                         'application/json', head)
            try:
                candidate = (static_root / ('index.html' if path == '/' else path.lstrip('/'))).resolve()
                candidate.relative_to(static_root)
                if not candidate.is_file() or any(part.startswith('.') for part in candidate.relative_to(static_root).parts):
                    raise ValueError()
                data = candidate.read_bytes()
            except (ValueError, OSError):
                return self.static_reply(404, head=head)
            return self.static_reply(200, data, mimetypes.guess_type(candidate.name)[0] or 'application/octet-stream', head)

        def do_GET(self):
            return self.serve_static()

        def do_HEAD(self):
            return self.serve_static(head=True)

    server.RequestHandlerClass = Handler
    return server


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--state', type=Path, required=True)
    parser.add_argument('--database', type=Path, default=os.environ.get('WAN_STUDIO_DATABASE') or None, help='Existing restored database; must already exist')
    parser.add_argument('--assets', type=Path, default=os.environ.get('WAN_STUDIO_ASSETS') or None, help='Existing restored asset directory; must already exist')
    parser.add_argument('--static', type=Path, default=Path('apps/studio/dist'))
    parser.add_argument('--port', type=int, default=8080)
    parser.add_argument('--container', action='store_true', help='Container only: publish host port on 127.0.0.1')
    args = parser.parse_args()
    origin = validate_origin(os.environ.get('WAN_STUDIO_ORIGIN', f'http://127.0.0.1:{args.port}'))
    tokens = json.loads(Path(os.environ['WAN_STUDIO_TOKEN_FILE']).read_text())
    if (args.state / 'RESTORED.json').exists() and args.database is None:
        raise ValueError('Restored state requires explicit --database and --assets paths')
    args.state.mkdir(parents=True, exist_ok=True)
    database = args.database or args.state / 'studio.sqlite'
    assets = args.assets or args.state / 'assets'
    if args.database and (not database.is_file() or not assets.is_dir()):
        raise ValueError('Restored database and assets must already exist; verify the restore paths')
    if args.assets and not assets.is_dir():
        raise ValueError('Restored asset directory must already exist')
    control = ControlService(database, assets)
    server = create_server(control, tokens, args.static, origin,
                           ('0.0.0.0' if args.container else '127.0.0.1', args.port))
    stop = threading.Event()
    workers = [threading.Thread(target=runner.serve, args=(stop,), daemon=True)
               for runner in (FixtureRunner(control), ExportRunner(control))]
    for worker in workers:
        worker.start()
    server.worker_threads = workers

    def shutdown(*_):
        stop.set()
        threading.Thread(target=server.shutdown, daemon=True).start()

    signal.signal(signal.SIGTERM, shutdown)
    signal.signal(signal.SIGINT, shutdown)
    print(f'Local fixture staging at {origin}; no GPU or paid dispatch', flush=True)
    try:
        server.serve_forever()
    finally:
        stop.set()
        server.server_close()
        for worker in workers:
            worker.join(timeout=60)


if __name__ == '__main__':
    main()
