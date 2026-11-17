"""Fictional inputs only; CPU checks are not GPU/creative acceptance."""
import copy
import hashlib
import json
from pathlib import Path
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import patch
import wave

from workers.gpu import longcat_batch as batch, longcat_resident as resident


class LongCatBatchTests(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name)
        (self.root/'fixture.png').write_bytes(b'fictional-image-fixture')
        with wave.open(str(self.root/'fixture.wav'), 'wb') as w:
            w.setparams((1,2,16000,0,'NONE','not compressed'))
            w.writeframes(b'\0' * 75520 * 2)
        self.plan = dict(protocol=batch.PROTOCOL, project_id='fiction', batch_id='batch',
            fps=25, duration_frames=110*82, shots=[])
        for i in range(110):
            self.plan['shots'].append(dict(id=f'shot-{i}', frames=82, in_frame=i*82,
                trim_in_frames=0, audio_start_frame=i*82, seed=42+i,
                prompt='Fictional singer wearing a cap', headwear_required=True,
                image=dict(path='fixture.png',sha256=batch.digest(self.root/'fixture.png')),
                audio=dict(path='fixture.wav',sha256=batch.digest(self.root/'fixture.wav'))))
        self.execution=dict(protocol=batch.PROTOCOL, admitted_at=1000, deadline=5800,
            gpu_count=2,max_hourly_cents=878,compute_cap_cents=1171,
            scope_id='fictional-scope',guard_run_id='fictional-guard',
            manifest_sha256=batch.fingerprint(self.plan))
        self.rendered=[];self.loads=[];self.closed=[];self.published=[]

    def adapter(self):
        self.loads.append(True)
        def render(shot, root, output):
            output.parent.mkdir(parents=True, exist_ok=True)
            output.write_bytes(shot['id'].encode())
            self.rendered.append(shot['id'])
        return SimpleNamespace(render=render,close=lambda:self.closed.append(True))

    def verify(self,path):
        return dict(bytes=path.stat().st_size,sha256=batch.digest(path))

    def publish(self,shot,path,binding,metadata):
        self.published.append(shot)
        return dict(binding=binding,shot_id=shot,bytes=metadata['bytes'],sha256=metadata['sha256'])

    def run_batch(self, publisher=None, clock=lambda:1001):
        return batch.run_queue(self.plan,self.execution,self.root,self.root/'output',
            self.adapter,publisher or self.publish,clock=clock,verify=self.verify)

    def test_110_shots_one_model_and_no_rerender_after_receipts(self):
        state=self.run_batch()
        self.assertEqual(len(self.loads),1)
        self.assertEqual(len(self.rendered),110)
        self.assertEqual(len(self.published),110)
        self.assertTrue(all(r['status']=='published' for r in state['shots'].values()))
        self.run_batch()
        self.assertEqual(len(self.loads),1)
        self.assertEqual(len(self.rendered),110)
        self.assertEqual(len(self.closed),1)

    def test_ambiguous_publish_reuses_render_instead_of_generating_again(self):
        def lost(*args):raise TimeoutError('fictional lost reply')
        with self.assertRaises(TimeoutError):self.run_batch(publisher=lost)
        self.assertEqual(self.rendered,['shot-0'])
        self.run_batch()
        self.assertEqual(self.rendered.count('shot-0'),1)
        self.assertEqual(len(self.rendered),110)

    def test_failed_render_is_not_blindly_retried(self):
        def fail(*args):raise RuntimeError('fictional inference failure')
        original=self.adapter
        self.adapter=lambda:SimpleNamespace(render=fail,close=lambda:None)
        with self.assertRaises(RuntimeError):self.run_batch()
        self.adapter=original
        with self.assertRaisesRegex(ValueError,'explicit recovery'):self.run_batch()
        self.assertEqual(self.loads,[])

    def test_foreign_receipt_stops_before_next_render(self):
        def wrong(*args):return {'binding':'another-project'}
        with self.assertRaisesRegex(ValueError,'receipt'):self.run_batch(publisher=wrong)
        self.assertEqual(self.rendered,['shot-0'])

    def test_deadline_gate_stops_before_initialization(self):
        state=self.run_batch(clock=lambda:5700)
        self.assertEqual(self.loads,[])
        self.assertEqual(state['shots'],{})

    def test_no_input_or_scope_mutation_on_resume(self):
        self.run_batch()
        self.execution['deadline']-=1
        with self.assertRaisesRegex(ValueError,'scope changed'):self.run_batch()
        self.execution['deadline']+=1
        self.plan['shots'][0]['prompt']='different content'
        with self.assertRaisesRegex(ValueError,'manifest changed'):self.run_batch()

    def test_input_integrity_offsets_headwear_and_continuity_fail_before_load(self):
        for mutate in (
            lambda p:p['shots'][1].update(in_frame=0),
            lambda p:p['shots'][0].update(audio_start_frame=1),
            lambda p:p['shots'][0].update(headwear_required=False),
            lambda p:p['shots'][0]['image'].update(path='../outside'),
            lambda p:p['shots'][0]['audio'].update(sha256='0'*64),
        ):
            value=copy.deepcopy(self.plan);mutate(value)
            with self.assertRaises(ValueError):batch.validate_manifest(value,self.root)
        self.assertEqual(self.loads,[])

    def test_old_or_larger_execution_is_refused(self):
        for change in (dict(deadline=6000),dict(compute_cap_cents=1200),dict(gpu_count=8),
                       dict(admitted_at=5800),dict(scope_id=''),dict(protocol='wan-song-queue-v1')):
            with self.assertRaises(ValueError):batch.validate_execution({**self.execution,**change},1001)

    def test_real_pinned_source_transform_is_hash_guarded(self):
        with self.assertRaises(ValueError):resident.resident_source('def generate(args): pass')

    def test_transformed_model_loads_once_and_changes_all_inputs_and_seeds(self):
        source='''
def generate(args):
    initialize()
    global_rank = 0
    os.makedirs(output_dir, exist_ok=True)
    global_seed = 42
    draws.append((prompt, raw_speech_path, input_data['cond_image'], global_seed, output_dir))
'''
        loads=[];draws=[];committed=[];published=[]
        cuda=SimpleNamespace(synchronize=lambda:None,reset_peak_memory_stats=lambda:None)
        ns=dict(initialize=lambda:loads.append(True),draws=draws,
            os=SimpleNamespace(makedirs=lambda *a,**k:None),
            dist=SimpleNamespace(barrier=lambda:None),torch=SimpleNamespace(cuda=cuda),
            time=SimpleNamespace(monotonic=lambda:10),LONGCAT_MANIFEST=self.plan,
            LONGCAT_INPUT_ROOT=self.root,LONGCAT_OUTPUT_ROOT=self.root/'output',
            longcat_decision=lambda case:'render',
            longcat_rendered=lambda case,elapsed:committed.append(case['id']),
            longcat_publish=lambda case:published.append(case['id']))
        with patch.object(resident,'SOURCE_SHA256',hashlib.sha256(source.encode()).hexdigest()):
            exec(resident.resident_source(source),ns)
        ns['generate'](None)
        self.assertEqual(len(loads),1)
        self.assertEqual(len(draws),110)
        self.assertEqual([r[3] for r in draws],list(range(42,152)))
        self.assertEqual(committed,published)
        self.assertEqual(len({r[4] for r in draws}),110)


if __name__=='__main__':unittest.main()
