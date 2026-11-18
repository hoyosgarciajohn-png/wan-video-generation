"""Fictional missing-suffix plans preserve original conditioning and edit timing."""
from copy import deepcopy
import unittest

from workers.gpu.longcat_batch import fingerprint
from workers.media.longcat_continuation import prepare_missing_suffix


class ContinuationPreparationTests(unittest.TestCase):
    def setUp(self):
        self.manifest = dict(protocol='longcat-song-batch-v1', project_id='fictional-project',
                             batch_id='fictional-original', fps=25, duration_frames=246, shots=[])
        for i in range(3):
            trim = 0 if i == 0 else 3
            self.manifest['shots'].append(dict(id=f'S{i+1}', frames=82, in_frame=i*82,
                trim_in_frames=trim, audio_start_frame=i*82-trim, prompt='Fictional capped performer',
                seed=i, headwear_required=True, image={'path':'image.png','sha256':'a'*64},
                audio={'path':f'S{i+1}.wav','sha256':'b'*64}))
        shot = self.manifest['shots'][0]; binding = fingerprint(self.manifest)
        self.journal = dict(binding=binding, scope_id='original-scope', shots={'S1':dict(
            status='published', input_sha256=fingerprint(shot), receipt=dict(binding=binding,
            shot_id='S1', scope_id='original-scope', sha256='c'*64, bytes=123))})

    def prepare(self, journal=None):
        return prepare_missing_suffix(self.manifest, journal or self.journal,
                                      project_id='fictional-continuation', batch_id='fictional-new')

    def test_rebase_preserves_audio_lookbehind_and_every_generation_input(self):
        original = deepcopy(self.manifest); result, provenance = self.prepare()
        self.assertEqual([s['id'] for s in result['shots']], ['S2','S3'])
        self.assertEqual(result['duration_frames'], 167)
        self.assertEqual((result['shots'][0]['frames'],result['shots'][0]['trim_in_frames']), (85,0))
        self.assertEqual((result['shots'][1]['in_frame'],result['shots'][1]['audio_start_frame']), (85,82))
        self.assertEqual(provenance['source_offset_frames'],79)
        self.assertEqual(provenance['first_original_frame'],82)
        self.assertEqual(provenance['original_first_trim_frames'],3)
        self.assertEqual(provenance['preserve_completed_shots'],['S1'])
        self.assertEqual(self.manifest,original)

    def test_unpublished_inference_cannot_be_silently_rerendered(self):
        j=deepcopy(self.journal);j['shots']['S2']={'status':'rendering'}
        with self.assertRaisesRegex(ValueError,'needs recovery'):self.prepare(j)

    def test_foreign_receipt_and_consumed_batch_are_refused(self):
        j=deepcopy(self.journal);j['shots']['S1']['receipt']['scope_id']='foreign'
        with self.assertRaisesRegex(ValueError,'Foreign receipt'):self.prepare(j)
        with self.assertRaisesRegex(ValueError,'consumed batch'):
            prepare_missing_suffix(self.manifest,self.journal,project_id='new',batch_id='fictional-original')


if __name__ == '__main__': unittest.main()
