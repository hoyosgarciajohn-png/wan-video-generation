"""B01 client for the private B02 worker routes. No provider operations."""
import json
from urllib.error import HTTPError, URLError
from urllib.parse import urlsplit
from urllib.request import Request, build_opener, HTTPRedirectHandler


class WorkerAPIError(RuntimeError):
    def __init__(self, status):
        self.status = status
        super().__init__(f'Worker API status {status}')


class NoRedirect(HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        return None


class WorkerClient:
    def __init__(self, base_url, token, *, timeout=10):
        url = urlsplit(base_url)
        if url.scheme != 'https' or not url.hostname or url.username or url.password or url.query or url.fragment:
            raise ValueError('Worker API requires an HTTPS origin without credentials or query')
        if not token or '\n' in token or '\r' in token:
            raise ValueError('Worker token required')
        self.base = base_url.rstrip('/')
        self.token = token
        self.timeout = timeout
        self.opener = build_opener(NoRedirect())

    def post(self, route, body):
        request = Request(self.base + '/v1/worker/' + route,
                          data=json.dumps(body).encode(), method='POST',
                          headers={'Authorization': 'Bearer ' + self.token,
                                   'Content-Type': 'application/json'})
        try:
            with self.opener.open(request, timeout=self.timeout) as response:
                if response.status == 204:
                    return None
                return json.loads(response.read(2_000_001))
        except HTTPError as error:
            raise WorkerAPIError(error.code) from None
        except (URLError, TimeoutError, OSError):
            raise WorkerAPIError(503) from None

    def claim(self):
        # Ambiguous claims are reconciled by B02. Never blindly retry a claim.
        return self.post('claim', {})

    def heartbeat(self, attempt, progress):
        return self.post(f"attempts/{attempt['id']}/heartbeat",
                         {'lease_id': attempt['lease_id'], 'progress': progress})

    def complete(self, attempt, manifest):
        return self.post(f"attempts/{attempt['id']}/complete",
                         {'lease_id': attempt['lease_id'], 'output_asset_manifest': manifest})

    def fail(self, attempt, code):
        return self.post(f"attempts/{attempt['id']}/fail",
                         {'lease_id': attempt['lease_id'], 'code': code})
