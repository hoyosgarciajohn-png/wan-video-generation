"""Fictional CPU checks for conditioning, warm reuse and queue recovery."""
from copy import deepcopy
from datetime import timedelta
import contextlib
import io
import json
from pathlib import Path
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import Mock, patch
import wave

from PIL import Image
from workers.gpu.cli import fixture_claim
from workers.gpu.common import atomic_json, frame_count, utcnow, validate_claim
from workers.gpu.continuous import run_queue
from workers.gpu.inference import ModelSession, reference_audio, serve
from workers.gpu.production import PROTOCOL, snapshot_hash
from workers.gpu.profiles import singing_profile


def policy(shots):
    return dict(protocol=PROTOCOL,shot_ids=[x['shot_id'] for x in shots],snapshots_sha256=snapshot_hash(shots),
        max_attempts_per_shot=2,max_runtime_seconds=14400,gpu_cap_cents=1800,total_cap_cents=2000,
        storage_reserve_cents=200,max_hourly_cents=450,image_ref='registry.example/wan@sha256:'+'a'*64)


class SingingTests(unittest.TestCase):
    def setUp(self):
        t = tempfile.TemporaryDirectory(); self.addCleanup(t.cleanup); self.root = Path(t.name)
        self.claim = fixture_claim(); c=self.claim
        c['batch']['execution_mode']='runpod'; c['batch']['budget']['approved_cents']=1800
        c['batch']['deadline_at']=(utcnow()+timedelta(hours=4)).isoformat()
        c['batch']['model_profile']=c['attempt']['model_profile']=singing_profile()
        c['shot_snapshot']['target_duration_ms']=5000
        c['attempt']['settings']=c['shot_snapshot']['settings']=dict(width=832,height=448,steps=40,
            seed=42,frame_rate=dict(numerator=16,denominator=1))
        c['shot_snapshot']['reference_asset_ids']=['image','audio']
        c['input_assets']=[dict(id=k,project_id=c['project']['id'],owner_id=c['project']['owner_id'],
            kind=k,mime_type=m,bytes=160044 if k=='audio' else 100,sha256='a'*64,
            duration_ms=5000 if k=='audio' else None,object_key='projects/'+c['project']['id']+'/'+k)
            for k,m in [('image','image/png'),('audio','audio/wav')]]
        c['continuous_queue']=policy(c['batch']['shot_snapshots'])

    def test_frozen_singing_inputs_and_native_frame_rounding(self):
        validate_claim(self.claim)
        self.assertEqual(frame_count(self.claim['shot_snapshot'],'runpod'),80)
        for change in ('missing_scope','foreign_audio','wrong_duration','changed_prompt'):
            c=deepcopy(self.claim)
            if change=='missing_scope': del c['continuous_queue']
            if change=='foreign_audio': c['input_assets'][1]['owner_id']='foreign'
            if change=='wrong_duration': c['input_assets'][1]['duration_ms']=4000
            if change=='changed_prompt': c['shot_snapshot']['prompt']='changed'
            with self.assertRaises(ValueError): validate_claim(c)

    def test_one_model_two_distinct_audio_clips_and_no_frame_drop(self):
        image=self.root/'image.png'; Image.new('RGB',(832,448)).save(image)
        (self.root/'REVISION').write_text(singing_profile()['code_revision'])
        audios=[]
        for i in range(2):
            path=self.root/f'audio-{i}.wav'
            with wave.open(str(path),'wb') as w:
                w.setparams((1,2,16000,0,'NONE','not compressed')); w.writeframes(bytes(160000))
            audios.append(path)
        gpu=SimpleNamespace(is_available=lambda:True,is_bf16_supported=lambda:True,
            synchronize=Mock(),reset_peak_memory_stats=Mock(),memory_reserved=lambda:1,
            get_device_properties=lambda _:SimpleNamespace(total_memory=80*1024**3),
            get_device_name=lambda _:'fictional',max_memory_allocated=lambda:1,max_memory_reserved=lambda:2)
        torch=SimpleNamespace(cuda=gpu,bfloat16='bf16',__version__='2.8.0',version=SimpleNamespace(cuda='12.8'),
                              inference_mode=contextlib.nullcontext)
        video=Mock(shape=(3,80,448,832));video.__getitem__=Mock(return_value='fictional tensor')
        model=Mock();model.generate.return_value=video
        constructor=Mock(return_value=model)
        modules={'torch':torch,'wan':SimpleNamespace(WanS2V=constructor),
            'wan.configs':SimpleNamespace(WAN_CONFIGS={'s2v-14B':'config'}),
            'wan.utils.utils':SimpleNamespace(save_video=Mock())}
        with patch.dict('sys.modules',modules),patch.dict('os.environ',{'WAN_SINGING_SOURCE':str(self.root)}), \
             patch('workers.gpu.inference.verify') as verified,patch('workers.gpu.inference.subprocess.check_output',return_value='fictional'):
            session=ModelSession()
            for i,audio in enumerate(audios):
                session.run(dict(snapshot=self.claim['shot_snapshot'],frames=80,model_profile=singing_profile(),
                    weights=str(self.root/'models'),image=str(image),audio=str(audio),output=str(self.root/f'out-{i}.mp4')))
            constructor.assert_called_once();verified.assert_called_once()
            self.assertEqual([x.kwargs['audio_path'] for x in model.generate.call_args_list],list(map(str,audios)))
            self.assertTrue(all(x.kwargs['init_first_frame'] for x in model.generate.call_args_list))
            self.assertTrue(all(x.kwargs['enable_tts'] is False for x in model.generate.call_args_list))
            self.assertEqual(json.loads((self.root/'out-1.metrics.json').read_text())['process_start'],'warm')
            self.assertEqual(json.loads((self.root/'out-1.metrics.json').read_text())['model_load_seconds'],0)
        with wave.open(str(audios[0]),'rb') as a: self.assertEqual(a.getnframes(),80000)
        with self.assertRaises(ValueError): reference_audio(audios[0],84)

    def test_queue_reuses_renderer_and_retains_ambiguous_completion(self):
        c=deepcopy(self.claim);second=deepcopy(c['shot_snapshot']);second['shot_id']='second'
        c['batch']['shot_snapshots'].append(second);c['continuous_queue']=policy(c['batch']['shot_snapshots'])
        other=deepcopy(c);other['shot_snapshot']=other['batch']['shot_snapshots'][1]
        other['attempt'].update(id='second-attempt',shot_id='second')
        client=SimpleNamespace(binding='fictional',claim=Mock(side_effect=[other,None]))
        journal=self.root/'worker-claim.json';atomic_json(journal,{'claim':c,'binding':client.binding})
        renderer=Mock();renderer.__enter__=Mock(return_value=renderer);renderer.__exit__=Mock(return_value=False)
        execute=Mock(return_value={'fictional':True})
        run_queue(c,client,self.root,self.root/'result.json',journal,input_root=self.root,weights='fictional',
            renderer_factory=lambda:renderer,execute=execute)
        self.assertEqual(execute.call_count,2)
        self.assertTrue(all(x.kwargs['resident'] is renderer for x in execute.call_args_list))
        self.assertEqual(json.loads((self.root/'result.json').read_text())['status'],'succeeded')
        self.assertFalse(journal.exists())
        atomic_json(journal,{'claim':c,'binding':client.binding})
        client.claim.reset_mock()
        with self.assertRaises(ConnectionError):
            run_queue(c,client,self.root,self.root/'result.json',journal,input_root=self.root,weights='fictional',
                renderer_factory=lambda:renderer,execute=Mock(side_effect=ConnectionError('fictional lost completion')))
        self.assertTrue(journal.exists());client.claim.assert_not_called()

    def test_server_protocol_constructs_session_once(self):
        session=Mock();factory=Mock(return_value=session);requests=[]
        for i in range(2):
            p=self.root/f'spec-{i}.json';atomic_json(p,{'output':str(self.root/f'{i}.mp4')})
            requests.append(json.dumps({'spec':str(p)})+'\n')
        serve(io.StringIO(''.join(requests)),factory=factory)
        factory.assert_called_once();self.assertEqual(session.run.call_count,2)
        self.assertTrue((self.root/'spec-1.done.json').is_file())

    def test_lost_lease_terminates_resident_process(self):
        from workers.gpu.resident import ResidentRenderer
        child=Mock();child.poll.return_value=None
        lease=Mock();lease.check.side_effect=[None,RuntimeError('fictional expired lease')]
        renderer=ResidentRenderer()
        with patch('workers.gpu.resident.subprocess.Popen',return_value=child):
            with self.assertRaisesRegex(RuntimeError,'expired lease'):
                renderer.render(dict(weights='fictional',model_profile=singing_profile(),
                                     output=str(self.root/'canceled.mp4')),lease)
        child.terminate.assert_called_once();child.wait.assert_called_once()
        self.assertIsNone(renderer.process)
