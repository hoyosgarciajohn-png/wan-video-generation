import json
from pathlib import Path
import tempfile
import unittest
from deployment.publish_image import verified_manifest, validate_remote


class PublicationTests(unittest.TestCase):
    def test_publication_requires_complete_clean_build(self):
        value = {'target': 'gpu', 'source_dirty': False, 'source_commit': 'a' * 40,
                 'image_id': 'sha256:' + 'b' * 64,
                 'gates': {key: 'PASS' for key in ('image_build', 'image_identity', 'runtime_smoke', 'fixture_smoke')}}
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / 'manifest.json'
            path.write_text(json.dumps(value))
            self.assertEqual(verified_manifest(path), value)
            for gate in value['gates']:
                changed = json.loads(json.dumps(value))
                changed['gates'][gate] = 'UNVERIFIED'
                path.write_text(json.dumps(changed))
                with self.assertRaises(ValueError): verified_manifest(path)
            value['source_dirty'] = True
            path.write_text(json.dumps(value))
            with self.assertRaises(ValueError): verified_manifest(path)

    def test_remote_digest_must_identify_the_tested_image(self):
        body = json.dumps({'schemaVersion': 2, 'config': {'digest': 'sha256:' + 'b' * 64}}).encode()
        self.assertTrue(validate_remote(body, 'sha256:' + 'b' * 64).startswith('sha256:'))
        with self.assertRaises(ValueError): validate_remote(body, 'sha256:' + 'c' * 64)


if __name__ == '__main__': unittest.main()
