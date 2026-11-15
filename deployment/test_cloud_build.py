import json
import os
from pathlib import Path
import tarfile
import tempfile
import unittest
from unittest.mock import patch

from deployment.cloud_build import archive, GIB, preflight, require_capacity


class CloudBuildTests(unittest.TestCase):
    def test_capacity_distinguishes_large_worker_image(self):
        require_capacity('cpu', 14 * GIB, 8 * GIB)
        with self.assertRaises(ValueError):
            require_capacity('gpu', 14 * GIB, 8 * GIB)
        require_capacity('gpu', 40 * GIB, 8 * GIB)
        with self.assertRaises(ValueError):
            require_capacity('gpu', 40 * GIB, 4 * GIB)

    def test_personal_machine_never_runs_cleanup_or_docker(self):
        with tempfile.TemporaryDirectory() as directory, patch.dict(os.environ, {}, clear=True), \
                patch('deployment.cloud_build.local_daemon') as daemon, \
                patch('deployment.cloud_build.subprocess.run') as command:
            with self.assertRaises(ValueError):
                preflight('gpu', Path(directory) / 'evidence')
            daemon.assert_not_called()
            command.assert_not_called()

    def test_archive_preserves_failed_gate_without_promoting_it(self):
        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory) / 'evidence'
            (output / 'build').mkdir(parents=True)
            manifest = {'image_id': None, 'gates': {'image_build': 'FAIL', 'cuda_inference': 'UNVERIFIED'}}
            (output / 'build/manifest.json').write_text(json.dumps(manifest))
            with patch.dict(os.environ, {'VERIFICATION_OUTCOME': 'failure'}):
                result = archive(output)
            with tarfile.open(result) as bundle:
                self.assertEqual(json.load(bundle.extractfile('build/manifest.json')), manifest)
                self.assertEqual(json.load(bundle.extractfile('workflow-result.json'))['job_status_before_archive'], 'failure')

    def test_archive_refuses_links_and_oversized_evidence(self):
        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory) / 'evidence'
            output.mkdir()
            (output / 'secret-link').symlink_to('/etc/passwd')
            with self.assertRaises(ValueError):
                archive(output)
            (output / 'secret-link').unlink()
            with patch('deployment.cloud_build.MAX_EVIDENCE', 1):
                with self.assertRaises(ValueError):
                    archive(output)
            self.assertFalse(output.with_name('evidence-evidence.tar.gz').exists())


if __name__ == '__main__':
    unittest.main()
