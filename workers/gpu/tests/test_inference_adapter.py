"""CPU-only invocation checks; mocks do not establish upstream/CUDA compatibility."""
import copy
import contextlib
import io
import json
import os
from pathlib import Path
import sys
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import Mock, patch

from PIL import Image
from workers.gpu.cli import fixture_claim
from workers.gpu.common import LOCK, validate_claim
from workers.gpu.inference import main, reference_image, configure_memory


class InferenceAdapterTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        (self.root / 'REVISION').write_text(LOCK['profile']['code_revision'])
        claim = fixture_claim()
        claim['batch']['execution_mode'] = 'runpod'
        claim['batch']['budget']['approved_cents'] = 100
        claim['attempt']['model_profile'] = claim['batch']['model_profile'] = copy.deepcopy(LOCK['profile'])
        claim['attempt']['settings'] = claim['shot_snapshot']['settings'] = dict(
            width=1280, height=704, steps=50, seed=42, frame_rate={'numerator':24,'denominator':1})
        self.claim = claim
        self.spec = dict(snapshot=claim['shot_snapshot'], frames=49, weights=str(self.root/'models'),
                         image=None, output=str(self.root/'output.mp4'))
        self.spec_path = self.root/'spec.json'

    def invoke(self, *, cuda=True, bf16=True):
        self.spec_path.write_text(json.dumps(self.spec))
        gpu = SimpleNamespace(is_available=lambda:cuda, is_bf16_supported=lambda:bf16,
                              reset_peak_memory_stats=Mock(), synchronize=Mock(),
                              get_device_name=lambda _: 'mock device', memory_reserved=lambda:1,
                              get_device_properties=lambda _:SimpleNamespace(total_memory=80*1024**3), max_memory_allocated=lambda:1,
                              max_memory_reserved=lambda:2)
        torch = SimpleNamespace(cuda=gpu, bfloat16='mock-bf16', __version__='2.8.0+cu128',
                                version=SimpleNamespace(cuda='12.8'))
        video = Mock(); video.__getitem__ = Mock(return_value='mock tensor')
        model = Mock(); model.generate.return_value = video
        constructor, saver = Mock(return_value=model), Mock()
        modules = {'torch':torch, 'wan':SimpleNamespace(WanTI2V=constructor),
                   'wan.configs':SimpleNamespace(WAN_CONFIGS={'ti2v-5B':'mock config'}),
                   'wan.utils.utils':SimpleNamespace(save_video=saver)}
        with patch.dict(sys.modules, modules), patch.dict(os.environ, {'WAN_SOURCE':str(self.root)}), \
             patch('workers.gpu.inference.verify') as verify, patch('workers.gpu.inference.subprocess.check_output',return_value='570.0'), patch.object(sys, 'path', list(sys.path)):
            if not cuda:
                with self.assertRaisesRegex(ValueError, 'CUDA GPU required'):
                    main(self.spec_path)
                constructor.assert_not_called()
            elif not bf16:
                with self.assertRaisesRegex(ValueError, 'BF16 CUDA GPU required'):
                    main(self.spec_path)
                constructor.assert_not_called()
            else:
                main(self.spec_path)
                verify.assert_called_once_with(self.spec['weights'])
        return constructor, model, saver

    def test_real_profile_text_invocation_and_unbilled_metrics(self):
        validate_claim(self.claim)
        constructor, model, saver = self.invoke()
        self.assertFalse(constructor.call_args.kwargs['t5_cpu'])
        self.assertTrue(constructor.call_args.kwargs['init_on_cpu'])
        self.assertTrue(constructor.call_args.kwargs['convert_model_dtype'])
        model.vae.model.to.assert_called_once_with(dtype='mock-bf16')
        self.assertEqual(model.vae.dtype, 'mock-bf16')
        args = model.generate.call_args.kwargs
        self.assertEqual(args['frame_num'],49)
        self.assertEqual(args['size'],(1280,704))
        self.assertEqual(args['sampling_steps'],50)
        self.assertEqual(args['seed'],42)
        self.assertEqual(args['sample_solver'],'unipc')
        self.assertIsNone(args['img'])
        self.assertEqual(saver.call_args.kwargs['fps'],24)
        metrics=json.loads((self.root/'output.metrics.json').read_text())
        self.assertIsNone(metrics['cost_cents'])
        self.assertEqual(metrics['model_profile'],LOCK['profile'])
        self.assertEqual(metrics['memory_policy'], 'sequential-gpu-text-bf16-vae-v1')
        self.assertTrue(args['offload_model'])

    def test_reference_is_detached_rgb_before_model_invocation(self):
        path=self.root/'reference.png'
        Image.new('RGBA',(1280,704),(1,2,3,255)).save(path)
        self.spec['image']=str(path)
        _, model, _=self.invoke()
        image=model.generate.call_args.kwargs['img']
        path.unlink()
        self.assertEqual(image.mode,'RGB')
        self.assertEqual(image.getpixel((0,0)),(1,2,3))

    def test_bad_reference_rejected_before_weight_read_or_model_import(self):
        path=self.root/'wrong.png'; Image.new('RGB',(20,20)).save(path)
        self.spec['image']=str(path);self.spec_path.write_text(json.dumps(self.spec))
        with patch('workers.gpu.inference.verify') as verify:
            with self.assertRaisesRegex(ValueError,'frozen dimensions'):
                main(self.spec_path)
            verify.assert_not_called()
        path.write_bytes(b'not an image')
        with self.assertRaises(OSError):reference_image(path,(1280,704))

    def test_animation_and_unsupported_mime_refused(self):
        path=self.root/'animated.png'
        frames=[Image.new('RGB',(10,10),color) for color in ('blue','red')]
        frames[0].save(path,save_all=True,append_images=frames[1:],duration=100)
        with self.assertRaisesRegex(ValueError,'Animated'):
            reference_image(path,(10,10))
        self.claim['shot_snapshot']['reference_asset_ids']=['image-1']
        self.claim['input_assets']=[dict(id='image-1',project_id=self.claim['project']['id'],
            owner_id=self.claim['project']['owner_id'],kind='image',mime_type='image/svg+xml',
            bytes=100,sha256='a'*64,duration_ms=None,object_key='projects/'+self.claim['project']['id']+'/x.svg')]
        with self.assertRaisesRegex(ValueError,'Invalid reference'):validate_claim(self.claim)

    def test_cuda_absence_blocks_constructor(self):
        self.invoke(cuda=False)

    def test_bf16_absence_blocks_constructor(self):
        self.invoke(bf16=False)

    def test_phase_hooks_preserve_calls_and_identify_decode_failure(self):
        encoder = Mock(return_value=['fictional context'])
        decoder = Mock(side_effect=RuntimeError('private tensor diagnostics'))
        model = SimpleNamespace(text_encoder=encoder,
            vae=SimpleNamespace(model=Mock(), decode=decoder))
        configure_memory(model, SimpleNamespace(bfloat16='mock-bf16'))
        log = io.StringIO()
        with contextlib.redirect_stdout(log):
            self.assertIs(model.text_encoder.model, encoder.model)
            self.assertEqual(model.text_encoder(['fictional prompt'], 'gpu'), ['fictional context'])
            with self.assertRaises(RuntimeError):
                model.vae.decode(['fictional latent'])
        encoder.assert_called_once_with(['fictional prompt'], 'gpu')
        decoder.assert_called_once_with(['fictional latent'])
        self.assertEqual(log.getvalue().splitlines(),
                         ['WAN_STAGE:text_encode','WAN_STAGE:generation','WAN_STAGE:video_decode'])
