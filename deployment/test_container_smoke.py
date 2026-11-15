from pathlib import Path
import tempfile
import unittest

from deployment.container_smoke import source_syntax


class SourceSyntaxTests(unittest.TestCase):
    def test_source_check_never_executes_import_time_gpu_code(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / '__init__.py').write_text("raise RuntimeError('Import requires an actual GPU')\n")
            (root / 'module.py').write_text('import torch\ndevice = torch.cuda.current_device()\n')
            self.assertEqual(source_syntax(root), 2)
            self.assertFalse((root / '__pycache__').exists())

    def test_invalid_or_missing_source_fails(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            with self.assertRaises(ValueError):
                source_syntax(root)
            (root / 'module.py').write_text('def broken(\n')
            with self.assertRaises(SyntaxError):
                source_syntax(root)


if __name__ == '__main__':
    unittest.main()
