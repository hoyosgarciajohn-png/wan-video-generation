import io
import json
import unittest
from contextlib import redirect_stdout
from unittest.mock import patch
from deployment.check_cleanup_credential import check, main


class Response(io.BytesIO):
    status = 200


class CredentialCheckTests(unittest.TestCase):
    def test_single_get_and_no_provider_data_disclosed(self):
        calls = []
        def transport(request, **kwargs):
            calls.append(request)
            return Response(json.dumps({'pods': [{'env': {'TOKEN': 'private-fixture'}}],
                                        'pagination': {'hasNextPage': True}}).encode())
        result = check('fictional-token', transport=transport)
        self.assertEqual(len(calls), 1)
        self.assertEqual(calls[0].method, 'GET')
        self.assertEqual(calls[0].full_url, 'https://api.runpod.io/v2/pods?limit=1&includeClusterPods=true')
        self.assertIsNone(calls[0].data)
        self.assertNotIn('private-fixture', json.dumps(result))
        self.assertFalse(result['shutdown_verified'])

    def test_failure_is_redacted(self):
        out = io.StringIO()
        with patch.dict('os.environ', {'RUNPOD_CLEANUP_TOKEN': 'fictional-token'}), \
                patch('deployment.check_cleanup_credential.check', side_effect=ValueError('private-fixture')), \
                redirect_stdout(out), self.assertRaises(SystemExit):
            main()
        self.assertEqual(json.loads(out.getvalue()), {'status': 'CREDENTIAL_CHECK_FAILED'})


if __name__ == '__main__': unittest.main()
