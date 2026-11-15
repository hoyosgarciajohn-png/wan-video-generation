"""Bounded Runpod REST v2 adapter; no implicit network or create retries.

This transport is not spending authorization. Production admission remains disarmed.
"""
import copy
import hashlib
import json
import re
from urllib.error import HTTPError, URLError
from urllib.parse import quote
from urllib.request import HTTPRedirectHandler, Request, build_opener

from src.wan_platform.fake_provider import Pod

_ABSENT = object()
MAX_RESPONSE = 8 * 1024 * 1024


class NoRedirect(HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        return None


def https_transport():
    """Construct an opener only; future trusted host wiring must authorize its use."""
    return build_opener(NoRedirect()).open


def _text(value, limit=256):
    return isinstance(value, str) and 0 < len(value) <= limit and not any(ord(c) < 32 or ord(c) == 127 for c in value)


def validate_launch_profile(profile):
    """Validate our deliberately narrow v2 subset, not availability or approval."""
    required = {'image', 'gpu', 'cloud', 'disk', 'dataCenterIds', 'mounts', 'ports', 'env'}
    if not isinstance(profile, dict) or not required <= profile.keys() or profile.keys() - required - {'cmd', 'entrypoint', 'registry'}:
        raise ValueError('Unsupported Runpod launch profile fields')
    if not isinstance(profile['image'], str) or not re.fullmatch(r'[A-Za-z0-9._:/-]+@sha256:[a-f0-9]{64}', profile['image']):
        raise ValueError('A digest-pinned image is required')
    gpu = profile['gpu']
    if not isinstance(gpu, dict) or set(gpu) != {'id', 'count'} or not _text(gpu['id']) or type(gpu['count']) is not int or gpu['count'] != 1:
        raise ValueError('Exactly one explicit GPU is required')
    if profile['cloud'] != 'SECURE' or type(profile['disk']) is not int or not 1 <= profile['disk'] <= 1000:
        raise ValueError('Secure cloud and bounded disk are required')
    dc = profile['dataCenterIds']
    if not isinstance(dc, list) or len(dc) != 1 or not _text(dc[0]):
        raise ValueError('Exactly one data center is required')
    if profile['ports'] != []:
        raise ValueError('Inbound ports are disabled for outbound workers')
    env = profile['env']
    if not isinstance(env, dict) or 'RUNPOD_API_KEY' in env or len(env) > 64 or any(not isinstance(k, str) or not re.fullmatch(r'[A-Za-z_][A-Za-z0-9_]*', k) or not isinstance(v, str) or len(v) > 8192 or '\x00' in v for k, v in env.items()):
        raise ValueError('Invalid environment mapping')
    for key in ('cmd', 'entrypoint'):
        if key in profile and (not isinstance(profile[key], list) or len(profile[key]) > 64 or any(not _text(v, 8192) for v in profile[key])):
            raise ValueError('Invalid container command')
    if 'registry' in profile and not _text(profile['registry']):
        raise ValueError('Invalid registry credential ID')
    mounts = profile['mounts']
    if not isinstance(mounts, dict) or set(mounts) not in (set(), {'persistent'}, {'network'}):
        raise ValueError('Unsupported mount combination')
    paths, volumes = [], set()
    if 'persistent' in mounts:
        mount = mounts['persistent']
        if not isinstance(mount, dict) or set(mount) != {'size', 'path'} or type(mount['size']) is not int or not 1 <= mount['size'] <= 1000:
            raise ValueError('Invalid persistent mount')
        paths.append(mount['path'])
    if 'network' in mounts:
        entries = mounts['network']
        if not isinstance(entries, list) or not 1 <= len(entries) <= 4:
            raise ValueError('Invalid network mounts')
        for mount in entries:
            if not isinstance(mount, dict) or set(mount) != {'volumeId', 'path'} or not _text(mount['volumeId']) or mount['volumeId'] in volumes:
                raise ValueError('Invalid or duplicate network volume')
            volumes.add(mount['volumeId'])
            paths.append(mount['path'])
    for path in paths:
        if not _text(path) or not path.startswith('/') or path == '/' or any(p in ('', '.', '..') for p in path[1:].split('/')):
            raise ValueError('Invalid mount path')
    if any(a == b or a.startswith(b + '/') or b.startswith(a + '/') for i, a in enumerate(paths) for b in paths[i + 1:]):
        raise ValueError('Overlapping mount paths')
    return copy.deepcopy(profile)


class RunpodProvider:
    def __init__(self, token, *, launch_profile=None, scope=None, transport=None, expected_names=None):
        if not _text(token, 4096):
            raise ValueError('Runpod token is required')
        if scope is not None and not _text(scope):
            raise ValueError('Invalid provider scope')
        self._token = token
        self._scope = scope
        self._profile = None if launch_profile is None else validate_launch_profile(launch_profile)
        self._transport = transport
        self._expected_names = expected_names
        self._known = {}

    def _request(self, method, path, data=None):
        if self._transport is None or self._scope is None:
            raise ConnectionError('Runpod transport is not configured')
        request = Request('https://api.runpod.io/v2' + path,
                          data=None if data is None else json.dumps(data).encode(),
                          headers={'Authorization': 'Bearer ' + self._token, 'Content-Type': 'application/json',
                                   'User-Agent': 'wan-command-center/0.1'}, method=method)
        try:
            with self._transport(request, timeout=15) as response:
                expected = {'GET': 200, 'POST': 201, 'DELETE': 204}[method]
                if response.status != expected:
                    raise ValueError('Unexpected status')
                if method == 'DELETE':
                    return None
                body = response.read(MAX_RESPONSE + 1)
                if len(body) > MAX_RESPONSE:
                    raise ValueError('Oversized response')
                return json.loads(body)
        except HTTPError as error:
            error.close()
            if error.code == 404 and path.startswith('/pods/') and method in ('GET', 'DELETE'):
                return _ABSENT
            raise ConnectionError(f'Runpod request failed with HTTP {error.code}') from None
        except (URLError, OSError, ValueError, RecursionError):
            raise ConnectionError('Runpod transport or response failure') from None

    def _name(self, batch_id, request_key):
        if self._scope is None or not _text(batch_id) or not _text(request_key):
            raise ConnectionError('Runpod identity is not configured')
        key = json.dumps([self._scope, batch_id, request_key]).encode()
        return 'wan-' + hashlib.sha256(key).hexdigest()

    @staticmethod
    def _id(record):
        if isinstance(record, dict) and isinstance(record.get('id'), str) and re.fullmatch(r'[A-Za-z0-9_-]{1,191}', record['id']):
            return record['id']
        raise ConnectionError('Runpod response is missing a valid Pod ID')

    def _bind(self, record, name):
        pod_id = self._id(record)
        if record.get('name') != name or self._known.get(pod_id, name) != name:
            raise ConnectionError('Runpod Pod identity mismatch')
        self._known[pod_id] = name
        return pod_id

    def create(self, batch_id, request_key):
        if self._profile is None:
            raise ConnectionError('Runpod launch profile is unavailable')
        name = self._name(batch_id, request_key)
        record = self._request('POST', '/pods', {**self._profile, 'name': name})
        return Pod(self._bind(record, name), batch_id, request_key)

    def find(self, batch_id, request_key):
        name = self._name(batch_id, request_key)
        matches, seen_ids, cursors = [], set(), set()
        path = '/pods'
        for _ in range(100):
            inventory = self._request('GET', path)
            if not isinstance(inventory, dict) or not isinstance(inventory.get('pods'), list) or not isinstance(inventory.get('pagination'), dict):
                raise ConnectionError('Unexpected Runpod inventory response')
            for record in inventory['pods']:
                pod_id = self._id(record)
                if not _text(record.get('name')) or pod_id in seen_ids:
                    raise ConnectionError('Invalid or repeated Runpod inventory record')
                seen_ids.add(pod_id)
                if record['name'] == name:
                    matches.append(record)
            page = inventory['pagination']
            more, cursor = page.get('hasNextPage'), page.get('nextCursor')
            if type(more) is not bool or (not more and cursor is not None):
                raise ConnectionError('Invalid Runpod pagination')
            if not more:
                return [Pod(self._bind(record, name), batch_id, request_key) for record in matches]
            if not _text(cursor, 4096) or cursor in cursors:
                raise ConnectionError('Invalid or repeated Runpod cursor')
            cursors.add(cursor)
            path = '/pods?cursor=' + quote(cursor, safe='')
        raise ConnectionError('Runpod inventory page limit exceeded')

    def _expected(self, pod_id):
        self._id({'id': pod_id})
        name = self._known.get(pod_id)
        if name is None and self._expected_names is not None:
            name = self._expected_names(pod_id)
        if not isinstance(name, str) or not re.fullmatch(r'wan-[a-f0-9]{64}', name):
            raise ConnectionError('Pod identity is not bound to this controller scope')
        return name

    def get(self, pod_id):
        name = self._expected(pod_id)
        record = self._request('GET', '/pods/' + quote(pod_id, safe=''))
        if record is _ABSENT:
            return None
        if self._id(record) != pod_id:
            raise ConnectionError('Runpod response returned a different Pod ID')
        self._bind(record, name)
        # Never leak environment variables or provider diagnostics to lifecycle callers.
        return {'id': pod_id, 'name': name}

    def delete(self, pod_id):
        if self.get(pod_id) is not None:
            self._request('DELETE', '/pods/' + quote(pod_id, safe=''))
        # Acknowledgment only. Lifecycle requires subsequent GET + full inventory.
