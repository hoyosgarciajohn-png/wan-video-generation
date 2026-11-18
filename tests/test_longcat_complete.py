"""Two fictional executions join through original edits without rewriting receipts."""
from copy import deepcopy
from pathlib import Path
import subprocess
import tempfile
import unittest
import wave

from workers.gpu.common import digest
from workers.gpu.longcat_batch import fingerprint
from workers.media.longcat_continuation import rebase_suffix
from workers.media.longcat_complete import assemble_completed_runs
from workers.media.export import probe


class CompletedRunsTests(unittest.TestCase):
    def setUp(self):
        temp=tempfile.TemporaryDirectory();self.addCleanup(temp.cleanup);self.root=Path(temp.name)
        subprocess.run(['ffmpeg','-v','error','-f','lavfi','-i','color=c=blue:s=864x448:r=25',
                        '-frames:v','93','-c:v','libx264','-pix_fmt','yuv420p',str(self.root/'S1.mp4')],check=True)
        for name in ('S2','S3'):(self.root/(name+'.mp4')).write_bytes((self.root/'S1.mp4').read_bytes())
        self.master=self.root/'master.wav'
        with wave.open(str(self.master),'wb') as a:
            a.setparams((2,2,48000,0,'NONE','not compressed'));a.writeframes(b'\0'*(246*1920*4))
        self.checksum=digest(self.master);self.output=self.root/'complete.mp4'
        self.manifest=dict(protocol='longcat-song-batch-v1',project_id='original',batch_id='original',
                           fps=25,duration_frames=246,shots=[])
        for i in range(3):
            trim=0 if i==0 else 3
            self.manifest['shots'].append(dict(id=f'S{i+1}',in_frame=i*82,frames=82,trim_in_frames=trim,
                audio_start_frame=i*82-trim,prompt='Fictional cap',seed=i,image={'sha256':'a'*64},audio={'sha256':'b'*64}))
        suffix,_=rebase_suffix(self.manifest,self.manifest['shots'][1:],project_id='second',batch_id='second')
        self.runs=[self.run_record(self.manifest,'first-scope',['S1']),self.run_record(suffix,'second-scope',['S2','S3'])]

    def run_record(self,manifest,scope,ids):
        binding=fingerprint(manifest);journal=dict(binding=binding,scope_id=scope,shots={})
        for shot in manifest['shots']:
            if shot['id'] not in ids:continue
            p=self.root/(shot['id']+'.mp4')
            journal['shots'][shot['id']]=dict(status='published',input_sha256=fingerprint(shot),receipt=dict(
                binding=binding,scope_id=scope,shot_id=shot['id'],sha256=digest(p),bytes=p.stat().st_size))
        return dict(manifest=manifest,journal=journal,takes=self.root)

    def export(self,runs=None):
        return assemble_completed_runs(self.manifest,runs or self.runs,self.master,self.checksum,self.output)

    def test_complete_original_timing_and_both_scope_receipts_are_preserved(self):
        before=deepcopy(self.runs);result=self.export()
        self.assertEqual(result['status'],'FULL_SONG_REVIEW_ASSEMBLED_NOT_CREATIVE_APPROVAL')
        self.assertEqual(int(probe(self.output,'v:0')['nb_frames']),246)
        self.assertAlmostEqual(float(probe(self.output,'a:0')['duration']),9.84,places=2)
        self.assertEqual({p['scope_id'] for p in result['sources'].values()},{'first-scope','second-scope'})
        self.assertEqual(self.runs,before);self.assertEqual(digest(self.master),self.checksum)

    def test_missing_duplicate_and_changed_generation_are_refused(self):
        with self.assertRaisesRegex(ValueError,'Every original'):self.export(self.runs[:1])
        with self.assertRaisesRegex(ValueError,'Duplicate coverage'):self.export(self.runs+[self.runs[0]])
        changed=deepcopy(self.runs);changed[1]['manifest']['shots'][0]['seed']=999
        changed[1]['journal']['binding']=fingerprint(changed[1]['manifest'])
        with self.assertRaisesRegex(ValueError,'changed original generation'):self.export(changed)
        self.assertFalse(self.output.exists())


if __name__ == '__main__':unittest.main()
