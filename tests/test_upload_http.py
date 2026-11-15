"""Real TCP durable chunk upload checks; synthetic WAV exceeds the old 4 MiB cap."""
import hashlib
from http.client import HTTPConnection
import io
import json
import threading
import unittest
import wave

import test_render_http as harness
from services.controller.http_api import StudioAPI, make_server
from services.controller.service import ControlService
from services.controller.studio import StudioWorkspace

CHUNK = 1024 * 1024


class UploadHTTPTests(unittest.TestCase):
    setUp = harness.RenderHTTPTests.setUp
    stop_server = harness.RenderHTTPTests.stop_server
    login = harness.RenderHTTPTests.login
    workspace = harness.RenderHTTPTests.workspace

    def request(self, method, path, payload=None, cookie=None, raw=None):
        headers = {'Origin': self.api.origin, 'X-WAN-Request': 'studio',
                   'Content-Type': 'application/json' if raw is None else 'application/octet-stream'}
        if cookie:
            headers['Cookie'] = cookie
        connection = HTTPConnection(*self.server.server_address, timeout=30)
        try:
            connection.request(method, path, body=json.dumps(payload or {}).encode() if raw is None else raw,
                               headers=headers)
            response = connection.getresponse()
            data = response.read()
            if response.getheader('Content-Type') == 'application/json':
                data = json.loads(data)
            return response.status, data, dict(response.getheaders())
        finally:
            connection.close()

    def start_upload(self, data, key='large-audio'):
        path = f'/v1/studio/projects/{self.project}/uploads'
        payload = {'name': 'Synthetic original.wav', 'mime_type': 'audio/wav', 'bytes': len(data),
                   'expected_revision': self.workspace()['revision'], 'idempotency_key': key}
        status, result, _ = self.request('POST', path, payload, self.cookie)
        self.assertIn(status, (200, 201), result)
        return path + '/' + result['upload']['id'], payload, result['upload']

    def send_chunk(self, path, index, data, expected=200):
        status, result, _ = self.request('PUT', f'{path}/chunks/{index}', cookie=self.cookie, raw=data)
        self.assertEqual(status, expected, result)
        return result

    def test_large_wav_restart_prefix_retry_and_single_commit(self):
        buffer = io.BytesIO()
        with wave.open(buffer, 'wb') as wav:
            wav.setnchannels(1)
            wav.setsampwidth(2)
            wav.setframerate(48000)
            wav.writeframes(b'\0\0' * (48000 * 55))
        data = buffer.getvalue()
        self.assertGreater(len(data), 4 * CHUNK)
        path, payload, upload = self.start_upload(data)
        first = self.send_chunk(path, 0, data[:CHUNK])['upload']
        self.assertEqual(first['received_bytes'], CHUNK)
        self.assertEqual(first['chunk_sha256'], [hashlib.sha256(data[:CHUNK]).hexdigest()])
        self.assertEqual(self.send_chunk(path, 0, data[:CHUNK])['upload'], first)
        self.send_chunk(path, 0, b'x' * CHUNK, expected=409)
        self.send_chunk(path, 3, data[3 * CHUNK:4 * CHUNK], expected=409)
        # New API and database connections; sessions require fresh authentication.
        self.stop_server()
        self.control = ControlService(self.root / 'db.sqlite', self.root / 'assets')
        self.studio = StudioWorkspace(self.control)
        self.api = StudioAPI(self.studio, {'a' * 40: self.owner, 'b' * 40: 'other-owner'})
        self.server = make_server(self.api, ('127.0.0.1', 0))
        self.thread = threading.Thread(target=self.server.serve_forever, daemon=True)
        self.thread.start()
        self.cookie = self.login('a' * 40)
        self.foreign_cookie = self.login('b' * 40)
        self.assertEqual(self.request('GET', path, cookie=self.cookie)[1]['upload'], first)
        hashes = []
        for index, offset in enumerate(range(0, len(data), CHUNK)):
            chunk = data[offset:offset + CHUNK]
            hashes.append(hashlib.sha256(chunk).hexdigest())
            if index:
                self.send_chunk(path, index, chunk)
        bad = {'chunk_sha256': ['0' * 64] + hashes[1:]}
        self.assertEqual(self.request('POST', path + '/finish', bad, self.cookie)[0], 409)
        status, completed, _ = self.request('POST', path + '/finish', {'chunk_sha256': hashes}, self.cookie)
        self.assertEqual(status, 200, completed)
        asset = completed['asset']
        self.assertEqual(asset['bytes'], len(data))
        self.assertEqual(asset['duration_ms'], 55000)
        self.assertEqual(asset['sha256'], hashlib.sha256(data).hexdigest())
        self.assertEqual(self.request('POST', path + '/finish', {'chunk_sha256': hashes}, self.cookie)[1]['asset'], asset)
        replay = self.request('POST', path.rsplit('/', 1)[0], payload, self.cookie)
        self.assertEqual(replay[1]['upload']['id'], upload['id'])
        self.assertEqual(len([a for a in self.workspace()['projects'][0]['bundle']['assets'] if a['id'] == asset['id']]), 1)
        download = f"/v1/studio/projects/{self.project}/assets/{asset['id']}/content"
        self.assertEqual(self.request('GET', download, cookie=self.cookie)[1], data)
        self.assertEqual(self.request('GET', download, cookie=self.foreign_cookie)[0], 404)

    def test_owner_scope_order_limits_and_abort(self):
        data = b'not media' * 100
        path, payload, _ = self.start_upload(data)
        for method, target, value in [('GET', path, None), ('POST', path + '/finish', {'chunk_sha256': ['0' * 64]}),
                                      ('DELETE', path, {})]:
            self.assertEqual(self.request(method, target, value, self.foreign_cookie)[0], 404)
        self.assertEqual(self.request('PUT', path + '/chunks/0', cookie=self.foreign_cookie, raw=data)[0], 404)
        self.send_chunk(path, 1, data, expected=422)
        self.send_chunk(path, 0, data)
        status, _, _ = self.request('POST', path + '/finish',
                                    {'chunk_sha256': [hashlib.sha256(data).hexdigest()]}, self.cookie)
        self.assertEqual(status, 422)
        self.assertEqual(self.workspace()['revision'], 0)
        self.assertEqual(self.request('DELETE', path, {}, self.cookie)[0], 200)
        self.assertIn(self.request('PUT', path + '/chunks/0', cookie=self.cookie, raw=data)[0], (409, 410))
        self.assertEqual(self.request('POST', path.rsplit('/', 1)[0], dict(payload, bytes=128 * CHUNK + 1), self.cookie)[0], 422)


if __name__ == '__main__':
    unittest.main()
