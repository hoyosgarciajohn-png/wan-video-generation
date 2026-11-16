import copy
import io
import json
import unittest
from urllib.error import HTTPError

from services.controller.runpod import (RunpodProvider, validate_launch_profile, https_transport, NoRedirect,
                                       ProviderCreateRejected, ProviderCreateUncertain, MAX_ERROR_RESPONSE)

PROFILE = {'image': 'example/wan@sha256:' + 'a' * 64,
           'gpu': {'id': 'fictional-gpu', 'count': 1}, 'cloud': 'SECURE',
           'disk': 50, 'dataCenterIds': ['fictional-dc'], 'mounts': {}, 'ports': [], 'env': {}}


def page(pods, cursor=None):
    return {'pods': pods, 'pagination': {'hasNextPage': cursor is not None, 'nextCursor': cursor}}


class Response(io.BytesIO):
    def __init__(self, status, payload):
        super().__init__(json.dumps(payload).encode())
        self.status = status


class RunpodTests(unittest.TestCase):
    def setUp(self):
        self.calls = []
        self.replies = iter(())
        self.provider = RunpodProvider('fictional-key', launch_profile=PROFILE,
                                       scope='owner/project', transport=self.transport,
                                       expected_names=lambda pod: self.provider._name('batch', 'key') if pod == 'pod' else None)

    def transport(self, request, timeout):
        self.calls.append((request, timeout))
        status, payload = next(self.replies)
        if status >= 400:
            raise HTTPError(request.full_url, status, 'fictional-secret-diagnostic', {}, None)
        return Response(status, payload)

    def test_create_and_paginated_inventory_match_exact_scoped_name(self):
        name = self.provider._name('batch', 'key')
        self.replies = iter([(201, {'id': 'pod', 'name': name}),
                             (200, page([{'id': 'other', 'name': name + '-other'}], 'a+b/c')),
                             (200, page([{'id': 'pod', 'name': name}]))])
        pod = self.provider.create('batch', 'key')
        self.assertEqual(self.provider.find('batch', 'key'), [pod])
        req, timeout = self.calls[0]
        self.assertEqual(req.full_url, 'https://api.runpod.io/v2/pods')
        self.assertEqual(req.get_method(), 'POST')
        self.assertEqual(req.get_header('Authorization'), 'Bearer fictional-key')
        self.assertEqual(json.loads(req.data)['gpu']['count'], 1)
        self.assertEqual(self.calls[-1][0].full_url, 'https://api.runpod.io/v2/pods?cursor=a%2Bb%2Fc')
        other = RunpodProvider('key', scope='other/project')
        self.assertNotEqual(other._name('batch', 'key'), name)

    def test_delete_is_only_acknowledgment_then_get_confirms_absence(self):
        name = self.provider._name('batch', 'key')
        self.replies = iter([(200, {'id': 'pod', 'name': name}), (204, None), (404, None)])
        self.provider.delete('pod')
        self.assertIsNone(self.provider.get('pod'))
        self.assertEqual([r.get_method() for r, _ in self.calls], ['GET', 'DELETE', 'GET'])

    def test_unknown_or_foreign_identity_cannot_delete(self):
        with self.assertRaises(ConnectionError):
            self.provider.delete('unbound')
        self.assertEqual(self.calls, [])
        self.replies = iter([(200, {'id': 'pod', 'name': 'foreign'})])
        with self.assertRaises(ConnectionError):
            self.provider.delete('pod')
        self.assertEqual(len(self.calls), 1)

    def test_failures_never_establish_absence_or_leak_body(self):
        self.replies = iter([(403, None), (200, None), (200, {'pods': []}), (500, None)])
        for call in (lambda: self.provider.get('pod'), lambda: self.provider.get('pod'),
                     lambda: self.provider.find('batch', 'key'), lambda: self.provider.delete('pod')):
            with self.assertRaises(ConnectionError) as caught:
                call()
            self.assertNotIn('fictional-secret', str(caught.exception))

    def test_create_error_retains_safe_status_without_retry_or_secret(self):
        for status in (400, 403, 429, 500):
            with self.subTest(status=status):
                self.replies = iter([(status, None)])
                before = len(self.calls)
                with self.assertLogs('services.controller.runpod', level='WARNING') as logs:
                    with self.assertRaises(ConnectionError):
                        self.provider.create('batch', 'key')
                self.assertEqual(len(self.calls), before + 1)
                event = json.loads(logs.output[0].split('WAN_PROVIDER_CREATE_RESULT ', 1)[1])
                self.assertEqual(event, {'kind': 'http_error', 'http_status': status,
                    'request_id': None, 'outcome': 'unknown' if status == 500 else 'rejected'})
                self.assertNotIn('fictional-key', logs.output[0])
                self.assertNotIn('fictional-secret-diagnostic', logs.output[0])
                self.assertEqual(self.provider._known, {})

    def test_rejection_keeps_detail_and_request_id_redacts_secrets_and_input(self):
        self.provider._profile['env'] = {'WAN_WORKER_TOKEN': 'fictional-worker-secret'}
        payload = dict(title='Bad Request', detail='No capacity. fictional-key fictional-worker-secret '
                       'https://private.invalid?token=hidden Bearer other-secret\nnext line',
                       errors=[{'msg':'Invalid configuration', 'input':'private-input', 'ctx':{'secret':'hidden'}}],
                       ignored='private-extra')
        def reject(request, timeout):
            raise HTTPError(request.full_url, 400, 'private-exception', {'x-request-id':'req-fictional-123'},
                            io.BytesIO(json.dumps(payload).encode()))
        self.provider._transport = reject
        with self.assertRaises(ProviderCreateRejected) as caught:
            self.provider.create('batch','key')
        diagnostic = caught.exception.diagnostic
        self.assertIn('No capacity', diagnostic['detail'])
        self.assertEqual(diagnostic['request_id'], 'req-fictional-123')
        self.assertEqual(diagnostic['validation_messages'], ['Invalid configuration'])
        raw = json.dumps(diagnostic)
        for secret in ('fictional-key','fictional-worker-secret','private.invalid','other-secret',
                       'private-input','private-extra','private-exception'):
            self.assertNotIn(secret, raw)

    def test_oversized_or_non_json_error_is_bounded_without_changing_rejection(self):
        for raw in (b'private-html', b'x' * (MAX_ERROR_RESPONSE + 1)):
            def reject(request, timeout):
                raise HTTPError(request.full_url, 422, 'secret', {}, io.BytesIO(raw))
            self.provider._transport = reject
            with self.assertRaises(ProviderCreateRejected) as caught:
                self.provider.create('batch','key')
            self.assertNotIn('detail', caught.exception.diagnostic)

    def test_timeout_408_5xx_and_invalid_success_stay_unknown(self):
        for status in (408, 500, 503):
            self.replies = iter([(status,None)])
            with self.assertRaises(ProviderCreateUncertain) as caught:
                self.provider.create('batch','key')
            self.assertNotIsInstance(caught.exception, ProviderCreateRejected)
            self.assertEqual(caught.exception.diagnostic['outcome'], 'unknown')
        def timeout(*args, **kwargs): raise TimeoutError('secret transport text')
        self.provider._transport = timeout
        with self.assertRaises(ProviderCreateUncertain) as caught:
            self.provider.create('batch','key')
        self.assertEqual(caught.exception.diagnostic['kind'], 'transport_or_response')

    def test_multiple_data_centers_are_explicit_unique_and_bounded(self):
        profile = copy.deepcopy(PROFILE)
        profile['dataCenterIds'] = ['fictional-a','fictional-b']
        self.assertEqual(validate_launch_profile(profile)['dataCenterIds'], profile['dataCenterIds'])
        for regions in ([], ['duplicate','duplicate'], list(map(str,range(9))), ['ok',None], 'anywhere'):
            profile['dataCenterIds'] = regions
            with self.assertRaises(ValueError): validate_launch_profile(profile)

    def test_bad_or_repeated_pagination_never_returns_partial_matches(self):
        name = self.provider._name('batch', 'key')
        self.replies = iter([(200, page([{'id': 'pod', 'name': name}], 'repeat')),
                             (200, page([], 'repeat'))])
        with self.assertRaises(ConnectionError):
            self.provider.find('batch', 'key')
        self.assertEqual(self.provider._known, {})

    def test_create_wrong_identity_and_unexpected_status_are_uncertain(self):
        for status, payload in [(201, {'id': 'pod', 'name': 'wrong'}), (200, {'id': 'pod'})]:
            self.replies = iter([(status, payload)])
            before = len(self.calls)
            with self.assertRaises(ConnectionError):
                self.provider.create('batch', 'key')
            self.assertEqual(len(self.calls), before + 1)

    def test_default_network_disabled_and_profile_copied(self):
        provider = RunpodProvider('key', scope='scope', launch_profile=PROFILE)
        with self.assertRaises(ConnectionError):
            provider.create('batch', 'key')
        profile = copy.deepcopy(PROFILE)
        provider = RunpodProvider('key', scope='scope', launch_profile=profile)
        profile['gpu']['count'] = 20
        self.assertEqual(provider._profile['gpu']['count'], 1)

    def test_network_profile_and_rejected_mounts_queue_legacy(self):
        profile = copy.deepcopy(PROFILE)
        profile['mounts'] = {'network': [{'volumeId': 'volume', 'path': '/models'}]}
        self.assertEqual(validate_launch_profile(profile), profile)
        for mutate in (lambda p: p.update(queue={}), lambda p: p.update(imageName='legacy'),
                       lambda p: p['gpu'].update(count=True),
                       lambda p: p['mounts']['network'].append({'volumeId': 'other', 'path': '/models/sub'}),
                       lambda p: p['mounts']['network'].append({'volumeId': 'volume', 'path': '/other'})):
            changed = copy.deepcopy(profile)
            mutate(changed)
            with self.assertRaises(ValueError):
                validate_launch_profile(changed)

    def test_oversized_invalid_json_and_redirect_rejected(self):
        for status in (301, 202):
            self.replies = iter([(status, None)])
            with self.assertRaises(ConnectionError):
                self.provider.find('batch', 'key')
        for data in (b'{', b'x' * (8 * 1024 * 1024 + 1)):
            response = io.BytesIO(data)
            response.status = 200
            self.provider._transport = lambda *a, **k: response
            with self.assertRaises(ConnectionError):
                self.provider.find('batch', 'key')

    def test_wrong_id_does_not_bind_and_opener_refuses_redirect(self):
        name = self.provider._name('batch', 'key')
        self.replies = iter([(200, {'id': 'unexpected', 'name': name})])
        with self.assertRaises(ConnectionError):
            self.provider.get('pod')
        self.assertNotIn('unexpected', self.provider._known)
        opener = https_transport().__self__
        handlers = [h for h in opener.handlers if isinstance(h, NoRedirect)]
        self.assertEqual(len(handlers), 1)
        self.assertIsNone(handlers[0].redirect_request(None, None, 302, '', {}, 'https://other.invalid'))
