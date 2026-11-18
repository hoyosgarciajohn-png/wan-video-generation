"""Fictional media validates honest partial delivery; no provider/network calls."""
from copy import deepcopy
import json
from pathlib import Path
import subprocess
import tempfile
import unittest
import wave

from workers.gpu.common import digest
from workers.gpu.longcat_batch import fingerprint
from workers.media.longcat_partial import assemble_partial_review
from workers.media.export import probe


class PartialReviewTests(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory(); self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name)
        subprocess.run(['ffmpeg', '-v', 'error', '-f', 'lavfi', '-i', 'color=c=blue:s=864x448:r=25',
                        '-frames:v', '93', '-c:v', 'libx264', '-pix_fmt', 'yuv420p', str(self.root/'S1.mp4')], check=True)
        (self.root/'S2.mp4').write_bytes((self.root/'S1.mp4').read_bytes())
        self.master = self.root/'master.wav'
        with wave.open(str(self.master), 'wb') as audio:
            audio.setparams((2, 2, 48000, 0, 'NONE', 'not compressed')); audio.writeframes(b'\0'*(246*1920*4))
        self.master_hash = digest(self.master)
        self.manifest = dict(fps=25, duration_frames=246, shots=[
            dict(id=f'S{i+1}', in_frame=i*82, frames=82, trim_in_frames=0) for i in range(3)])
        self.binding = fingerprint(self.manifest)
        self.journal = dict(binding=self.binding, scope_id='fictional-scope', shots={})
        for shot in self.manifest['shots'][:2]:
            path = self.root/(shot['id']+'.mp4')
            self.journal['shots'][shot['id']] = dict(status='published', input_sha256=fingerprint(shot),
                receipt=dict(binding=self.binding, scope_id='fictional-scope', shot_id=shot['id'],
                             sha256=digest(path), bytes=path.stat().st_size))
        self.output = self.root/'incomplete.mp4'

    def export(self, journal=None):
        return assemble_partial_review(self.manifest, journal or self.journal, self.root,
                                       self.master, self.master_hash, self.output)

    def test_prefix_has_exact_duration_clear_status_and_untouched_master(self):
        result = self.export()
        self.assertEqual(result['status'], 'INCOMPLETE_RENDERED_PREFIX_NOT_FINAL_VIDEO')
        self.assertEqual(result['included_shots'], ['S1', 'S2'])
        self.assertEqual(result['missing_shots'], ['S3'])
        self.assertEqual(int(probe(self.output, 'v:0')['nb_frames']), 164)
        self.assertAlmostEqual(float(probe(self.output, 'a:0')['duration']), 6.56, places=2)
        self.assertEqual(digest(self.master), self.master_hash)
        self.assertEqual(json.loads(self.output.with_suffix('.json').read_text()), result)
        with self.assertRaises(ValueError): self.export()

    def test_gaps_foreign_receipts_and_changed_footage_are_refused(self):
        gap = deepcopy(self.journal); del gap['shots']['S1']
        with self.assertRaisesRegex(ValueError, 'contiguous'): self.export(gap)
        changed = deepcopy(self.journal); changed['shots']['S2']['receipt']['scope_id'] = 'foreign'
        with self.assertRaisesRegex(ValueError, 'Foreign receipt'): self.export(changed)
        changed = deepcopy(self.journal); changed['shots']['S2']['receipt']['sha256'] = '0'*64
        with self.assertRaisesRegex(ValueError, 'differs'): self.export(changed)
        self.assertFalse(self.output.exists())

    def test_wrong_manifest_and_changed_inputs_are_refused(self):
        changed = deepcopy(self.journal); changed['binding'] = '0'*64
        with self.assertRaisesRegex(ValueError, 'another manifest'): self.export(changed)
        changed = deepcopy(self.journal); changed['shots']['S2']['input_sha256'] = '0'*64
        with self.assertRaisesRegex(ValueError, 'input changed'): self.export(changed)


if __name__ == '__main__': unittest.main()
