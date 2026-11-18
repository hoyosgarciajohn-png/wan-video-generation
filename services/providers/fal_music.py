"""Explicit fal mappings. Server-only transport; never performs automatic retries.

No paid route is exposed in the Director foundation release. A durable admission
worker must own submit() and persist its response before paid UI dispatch ships.
"""
import json
import os
from pathlib import Path
from urllib.parse import urlsplit
from urllib.request import Request, build_opener, HTTPRedirectHandler

MODELS = json.loads(Path(__file__).with_name('music_models.json').read_text())
BY_ID = {m['id']: m for m in MODELS}


def payload(model_id, *, prompt, image_urls, audio_url, duration_ms, resolution, aspect_ratio):
    model = BY_ID[model_id]
    if not isinstance(prompt, str) or not 1 <= len(prompt.strip()) <= 8000:
        raise ValueError('A shot prompt is required')
    if type(duration_ms) is not int or duration_ms % 1000 or not model['min_seconds'] <= duration_ms // 1000 <= model['max_seconds']:
        raise ValueError('Unsupported clip length')
    if resolution not in model['resolutions'] or aspect_ratio not in ('16:9', '9:16'):
        raise ValueError('Unsupported output format')
    if not image_urls or len(image_urls) > (30 if model_id == 'seedance-reference' else 10 if model_id == 'wan-reference' else 1):
        raise ValueError('Reference count exceeds endpoint capability')
    for url in [*image_urls, *([audio_url] if audio_url else [])]:
        if not isinstance(url, str) or not (url.startswith('https://') or url.startswith('data:')):
            raise ValueError('Provider requires accessible HTTPS or data URI assets')
    if model_id == 'ltx-fast':
        if not audio_url:
            raise ValueError('LTX audio endpoint requires a trimmed song clip')
        return dict(prompt=prompt, image_url=image_urls[0], audio_url=audio_url,
                    aspect_ratio=aspect_ratio, enable_safety_checker=True)
    if model_id == 'wan-reference':
        return dict(prompt=prompt, reference_image_urls=image_urls,
                    reference_audio_urls=[audio_url] if audio_url else [], duration=duration_ms // 1000,
                    resolution=resolution, aspect_ratio=aspect_ratio, audio=True,
                    enable_prompt_expansion=False, enable_safety_checker=True)
    if model_id == 'seedance-reference':
        return dict(prompt=prompt, task='reference', image_urls=image_urls,
                    audio_urls=[audio_url] if audio_url else [], duration=str(duration_ms // 1000),
                    resolution=resolution, aspect_ratio=aspect_ratio, generate_audio=True, codec='H264')
    if audio_url:
        raise ValueError('Kling image endpoint cannot accept a supplied song')
    return dict(prompt=prompt, start_image_url=image_urls[0], duration=duration_ms // 1000,
                resolution=resolution)


class NoRedirect(HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        raise ValueError('Provider redirects are not allowed')


class FalMusicClient:
    def __init__(self, key=None, opener=None):
        self.key = key or os.environ.get('FAL_KEY')
        self.opener = opener or build_opener(NoRedirect())

    def _request(self, url, body=None):
        parsed = urlsplit(url)
        if parsed.scheme != 'https' or parsed.netloc != 'queue.fal.run' or parsed.fragment:
            raise ValueError('Untrusted provider URL')
        if not self.key:
            raise ValueError('FAL_KEY is not configured on the server')
        request = Request(url, data=None if body is None else json.dumps(body).encode(),
                          headers={'Authorization': 'Key ' + self.key, 'Content-Type': 'application/json'})
        # A failed POST can still have created a chargeable job. Never retry here.
        with self.opener.open(request, timeout=30) as response:
            raw = response.read(2 * 1024 * 1024 + 1)
            if len(raw) > 2 * 1024 * 1024:
                raise ValueError('Oversized provider response')
            return json.loads(raw)

    def submit(self, model_id, **shot):
        body = payload(model_id, **shot)
        return self._request('https://queue.fal.run/' + BY_ID[model_id]['endpoint'], body)

    def status(self, receipt):
        return self._request(receipt['status_url'])

    def result(self, receipt):
        return self._request(receipt['response_url'])
