import json
import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from deployment.longcat_publish import publish, validate_build
from deployment.publish_image import IMAGE, REPOSITORY, validate_remote


class LongCatPublicationBoundaryTests(unittest.TestCase):
    def setUp(self):
        self.commit='a'*40
        self.build=dict(source_commit=self.commit,protocol='longcat-song-batch-v1',
                        offline_import='PASS',image_id='sha256:'+'b'*64)

    def test_bad_source_or_missing_import_evidence_cannot_publish(self):
        validate_build(self.build,self.commit)
        for value,commit in [(self.build,'c'*40),({**self.build,'offline_import':'FAIL'},self.commit),
                             ({**self.build,'protocol':'wan'},self.commit)]:
            with self.assertRaises(ValueError):validate_build(value,commit)

    def test_non_main_cannot_reach_docker(self):
        with patch.dict(os.environ,{'GITHUB_REPOSITORY':REPOSITORY,'GITHUB_REF':'refs/heads/other'},clear=True), \
             patch('deployment.longcat_publish.subprocess.check_output') as docker:
            with self.assertRaises(ValueError):publish(Path('/fictional'))
            docker.assert_not_called()

    def test_retagged_image_is_rejected_before_registry_or_push(self):
        with tempfile.TemporaryDirectory() as directory:
            root=Path(directory);(root/'build.json').write_text(json.dumps(self.build))
            env=dict(GITHUB_REPOSITORY=REPOSITORY,GITHUB_REF='refs/heads/main',GITHUB_SHA=self.commit)
            for local in [dict(Id='sha256:'+'c'*64,Config={'Labels':{'org.opencontainers.image.revision':self.commit}}),
                          dict(Id=self.build['image_id'],Config={'Labels':{'org.opencontainers.image.revision':'d'*40}})]:
                with patch.dict(os.environ,env,clear=True), \
                     patch('deployment.longcat_publish.subprocess.check_output',return_value=json.dumps([local])), \
                     patch('deployment.longcat_publish.subprocess.run') as push, \
                     patch('deployment.longcat_publish.package_visibility') as registry:
                    with self.assertRaises(ValueError):publish(root)
                    push.assert_not_called();registry.assert_not_called()

    def test_remote_manifest_must_bind_checked_local_image(self):
        valid=json.dumps({'schemaVersion':2,'config':{'digest':self.build['image_id']}}).encode()
        self.assertTrue(validate_remote(valid,self.build['image_id']).startswith('sha256:'))
        with self.assertRaises(ValueError):validate_remote(valid,'sha256:'+'d'*64)


if __name__=='__main__':unittest.main()
