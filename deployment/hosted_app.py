"""Production WSGI adapter, served only behind a local HTTPS reverse proxy.

One Waitress process preserves the existing in-memory login sessions. Durable
jobs and media remain on the host disk. This entry point does not install live
spending authority or expose a provider-create route.
"""
from email.message import Message
from http import HTTPStatus
import json
import logging
import mimetypes
import os
from pathlib import Path
import re
import threading

from deployment.local_stage import CSP
from services.controller.http_api import StudioAPI, Reply, body_limit
from services.controller.accounts import Accounts, smtp_sender
from services.controller.preflight import _origin
from services.controller.service import ControlService
from services.controller.studio import StudioWorkspace
from services.controller.runner import FixtureRunner
from services.controller.export_runner import ExportRunner
from services.controller.worker_transport import IDENTIFIER, MAX_ARTIFACT_BYTES


class Application:
    def __init__(self, api, static_root, *, healthy=lambda: True):
        self.api, self.static = api, Path(static_root).resolve(strict=True)
        self.healthy = healthy
        if not (self.static / 'index.html').is_file():
            raise ValueError('Built Studio assets are required')

    def reply(self, env):
        headers = Message()
        for key, value in env.items():
            if key.startswith('HTTP_'):
                headers[key[5:].replace('_', '-')] = value
        headers['Content-Type'] = env.get('CONTENT_TYPE', '')
        if headers.get('Host') not in self.api.allowed_hosts:
            return Reply(403, {'error': 403})
        method, path = env['REQUEST_METHOD'], env.get('PATH_INFO', '/')
        if env.get('QUERY_STRING'):
            return Reply(400, {'error': 400})
        if path == '/v1' or path.startswith('/v1/'):
            if method == 'HEAD':
                return Reply(405, {'error': 405})
            try:
                length = int(env.get('CONTENT_LENGTH') or '0')
                if not 0 <= length <= body_limit(path):
                    raise ValueError()
                if re.fullmatch(rf'/v1/(?:worker/attempts|longcat/shots)/({IDENTIFIER})/artifact', path):
                    return self.api.worker_upload(method, path, headers, env['wsgi.input'], length)
                body = env['wsgi.input'].read(length)
                if len(body) != length:
                    raise ValueError()
            except (ValueError, OSError):
                return Reply(413, {'error': 413})
            return self.api.dispatch(method, path, headers, body, env.get('REMOTE_ADDR', 'unknown'))
        if method not in ('GET', 'HEAD'):
            return Reply(405, {'error': 405})
        if path == '/healthz':
            try:
                with self.api.studio.control.transaction() as db:
                    db.execute('SELECT 1').fetchone()
                ready = bool(self.healthy())
            except Exception:
                ready = False
            return Reply(200 if ready else 503, {'ready': ready, 'paid_dispatch': False})
        try:
            relative = 'index.html' if path == '/' else path.lstrip('/')
            candidate = (self.static / relative).resolve(strict=True)
            parts = candidate.relative_to(self.static).parts
            if not candidate.is_file() or any(part.startswith('.') for part in parts):
                raise ValueError()
        except (ValueError, OSError):
            return Reply(404, {'error': 404})
        return Reply(200, file=candidate, length=candidate.stat().st_size,
                     headers={'Content-Type': mimetypes.guess_type(candidate.name)[0] or 'application/octet-stream'})

    def __call__(self, env, start_response):
        try:
            reply = self.reply(env)
        except Exception:
            reply = Reply(503, {'error': 503})
        if reply.status == 403 and env.get('PATH_INFO') == '/v1/studio/session':
            # Only fixed categories/booleans: no cookie, token, IP, URL or header text.
            fetch_site = env.get('HTTP_SEC_FETCH_SITE')
            logging.warning('WAN_SESSION_REJECT %s', json.dumps({
                'host_matches': env.get('HTTP_HOST') in self.api.allowed_hosts,
                'origin_matches': env.get('HTTP_ORIGIN') == self.api.origin,
                'origin_present': bool(env.get('HTTP_ORIGIN')),
                'fetch_site': fetch_site if fetch_site in ('same-origin', 'same-site', 'cross-site', 'none') else 'absent-or-other',
                'studio_header_matches': env.get('HTTP_X_WAN_REQUEST') == 'studio',
                'method': env.get('REQUEST_METHOD') if env.get('REQUEST_METHOD') in ('GET','POST','DELETE') else 'other',
            }, sort_keys=True))
        body = b'' if reply.status == 204 else json.dumps(reply.data, separators=(',', ':'), allow_nan=False).encode()
        headers = {'Content-Type': 'application/json', 'Cache-Control': 'no-store',
                   'Content-Security-Policy': CSP, 'Referrer-Policy': 'no-referrer',
                   'X-Content-Type-Options': 'nosniff', **reply.headers,
                   'Content-Length': str(reply.length if reply.file else len(body))}
        start_response(f'{reply.status} {HTTPStatus(reply.status).phrase}', list(headers.items()))
        if env['REQUEST_METHOD'] == 'HEAD':
            return []
        if not reply.file:
            return [body]
        def stream():
            with reply.file.open('rb') as source:
                source.seek(reply.offset)
                remaining = reply.length
                while remaining:
                    chunk = source.read(min(65536, remaining))
                    if not chunk:
                        break
                    remaining -= len(chunk)
                    yield chunk
        return stream()


def open_control(environment):
    state = Path(environment['WAN_STATE']).resolve(strict=True)
    database_value, assets_value = environment.get('WAN_STUDIO_DATABASE'), environment.get('WAN_STUDIO_ASSETS')
    if bool(database_value) != bool(assets_value):
        raise ValueError('Restored database and asset paths must be supplied together')
    if (state / 'RESTORED.json').exists() and not database_value:
        raise ValueError('Restored state requires explicit database and asset paths')
    database = Path(database_value) if database_value else state / 'studio.sqlite'
    assets = Path(assets_value) if assets_value else state / 'assets'
    if database_value and (not database.is_file() or not assets.is_dir()):
        raise ValueError('Restored database and assets must already exist')
    return ControlService(database, assets, max_attempts=1)


def main():
    from waitress import serve
    origin = _origin(os.environ['WAN_STUDIO_ORIGIN'])
    tokens = json.loads(Path(os.environ['WAN_STUDIO_TOKEN_FILE']).read_text())
    control = open_control(os.environ)
    studio = StudioWorkspace(control)
    execution = None
    if os.environ.get('WAN_WORKER_EXECUTION') == '1':
        # Receive already-authorized worker claims/results, without provider
        # credentials, approval keys, admission or a public provisioning route.
        from services.controller.live_admission import LiveAdmission
        from services.controller.live_execution import LiveExecution
        execution = LiveExecution(LiveAdmission(studio))
    accounts = Accounts(control, origin, send=smtp_sender(os.environ))
    account_file = os.environ.get('WAN_STUDIO_ACCOUNT_FILE')
    if account_file:
        for email, owner in json.loads(Path(account_file).read_text()).items():
            if owner not in tokens.values():
                raise ValueError('Account owner must already be provisioned')
            accounts.provision(email, owner)
    api = StudioAPI(studio, tokens, origin, real_jobs=execution, accounts=accounts)
    stop = threading.Event()
    threads = [threading.Thread(target=runner.serve, args=(stop,), daemon=True)
               for runner in (FixtureRunner(control), ExportRunner(control))]
    for thread in threads:
        thread.start()
    app = Application(api, os.environ['WAN_STATIC_ROOT'], healthy=lambda: all(t.is_alive() for t in threads))
    try:
        serve(app, host='127.0.0.1', port=8080, threads=8, connection_limit=64,
              channel_timeout=30, max_request_body_size=MAX_ARTIFACT_BYTES,
              max_request_header_size=16384, expose_tracebacks=False,
              trusted_proxy='127.0.0.1', trusted_proxy_count=1,
              trusted_proxy_headers={'x-forwarded-for', 'x-forwarded-proto'},
              clear_untrusted_proxy_headers=True)
    finally:
        stop.set()


if __name__ == '__main__':
    main()
