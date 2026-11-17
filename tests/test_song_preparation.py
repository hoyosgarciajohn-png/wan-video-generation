"""Full-duration fictional input preparation, no network or GPU."""
from copy import deepcopy
import base64
import hashlib
import json
from pathlib import Path
import subprocess
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import Mock
import wave

from deployment.song_trial import prepare, export
from deployment.deadline_guard import validate
from services.controller.service import ControlService
from services.controller.studio import StudioWorkspace
from services.controller.media_commands import MediaCommands,inspect_upload
from workers.gpu.common import digest

ROOT=Path(__file__).resolve().parents[1]

class SongPreparationTests(unittest.TestCase):
    def test_full_export_and_missing_coverage_are_distinct(self):
        with tempfile.TemporaryDirectory() as directory:
            root=Path(directory);proposal=json.loads((ROOT/'deployment/song-production.json').read_text())
            song=root/'original.m4a';video=root/'native.mp4'
            subprocess.run(['ffmpeg','-v','error','-f','lavfi','-i','sine=frequency=330:duration=340.126','-c:a','aac','-b:a','32k',str(song)],check=True)
            subprocess.run(['ffmpeg','-v','error','-f','lavfi','-i','color=c=blue:s=832x448:r=16:d=5.25','-an','-c:v','libx264','-threads','1',str(video)],check=True)
            assets=[dict(id='song',object_key=song.name,sha256=digest(song),bytes=song.stat().st_size),
                    dict(id='video',object_key=video.name,sha256=digest(video),bytes=video.stat().st_size)]
            bundle=dict(assets=assets,takes=[dict(shot_id=f'song-{i:03d}',asset_id='video') for i in range(67)])
            saved=dict(original_song_asset_id='song',original_song_sha256=digest(song))
            op=SimpleNamespace(ROOT=ROOT,TRIAL=root,OWNER='fictional-owner',
                control=lambda:SimpleNamespace(asset_root=root,bundle=lambda *_:bundle),
                observe=lambda:dict(batch=dict(cleanup_state='confirmed',project_id='project'),billing=dict(status='fixture')),
                read=lambda p:proposal if p.name=='song-production.json' else saved)
            export(op)
            out=root/'song-output';report=json.loads((out/'coverage.json').read_text())
            self.assertEqual(report['status'],'PARTIAL_COVERAGE');self.assertEqual(report['coverage_ms'],335000)
            self.assertFalse((out/'Busca-adentro-de-ti-world-concert-draft.mp4').exists())
            bundle['takes'].append(dict(shot_id='song-067',asset_id='video'))
            export(op)
            report=json.loads((out/'coverage.json').read_text());final=out/report['video']['file']
            self.assertEqual(report['completed_shots'],68);self.assertEqual(report['coverage_ms'],340126)
            self.assertEqual(report['owner_creative_acceptance'],'PENDING')
            probe=json.loads(subprocess.check_output(['ffprobe','-v','error','-show_streams','-show_format','-of','json',str(final)]))
            v=next(x for x in probe['streams'] if x['codec_type']=='video');a=next(x for x in probe['streams'] if x['codec_type']=='audio')
            self.assertEqual((v['width'],v['height'],v['r_frame_rate']),(1280,720,'24/1'))
            self.assertAlmostEqual(float(probe['format']['duration']),340.126,delta=1/24)
            self.assertAlmostEqual(float(a['start_time']),0,delta=0.03)
            self.assertEqual(digest(out/'original-song.m4a'),digest(song))

    def test_full_audio_windows_and_last_frame_padding(self):
        with tempfile.TemporaryDirectory() as directory:
            root=Path(directory);control=ControlService(root/'state.sqlite',root/'assets',max_attempts=1)
            studio=StudioWorkspace(control);proposal=json.loads((ROOT/'deployment/song-production.json').read_text())
            state=studio.create('fictional-owner',proposal['title'],'music_video',0)
            project=state['projects'][0]['bundle']['project']['id'];media=MediaCommands(studio)
            image=root/'anchor.png'
            subprocess.run(['ffmpeg','-v','error','-f','lavfi','-i','color=c=blue:s=832x448','-frames:v','1','-threads','1',str(image)],check=True)
            song=root/'original.m4a'
            subprocess.run(['ffmpeg','-v','error','-f','lavfi','-i','sine=frequency=330:duration=340.126','-c:a','aac','-b:a','32k',str(song)],check=True)
            proposal['assets']={}
            for name,path,mime in [('Busca-adentro-de-ti-original.m4a',song,'audio/mp4')]+[(x['image'],image,'image/png') for x in proposal['cities']]:
                data=path.read_bytes();proposal['assets'][name]=hashlib.sha256(data).hexdigest()
                media.upload('fictional-owner',project,dict(name=name,mime_type=mime,data_base64=base64.b64encode(data).decode(),
                    expected_revision=studio.get('fictional-owner')['revision'],idempotency_key=name))
            op=SimpleNamespace(ROOT=ROOT,TRIAL=root/'trial',AUTH=root/'authority.json',OWNER='fictional-owner',TITLE=proposal['title'],
                IMAGE=proposal['image'],GPU='NVIDIA H100 80GB HBM3',ORIGIN='https://fixture.example',REGISTRY='fixture-registry',APPROVAL_ID='fictional-song',
                control=lambda:control,primary_ready=Mock(),prior_history_closed=Mock(),
                read=lambda _:deepcopy(proposal),checked_quote=lambda:dict(region='fictional',data_center_ids=['fictional'],usd_per_hour='4.39'),
                materialize_build=lambda _:dict(manifest_sha256='a'*64),sign=lambda p,k,d:dict(payload=p,key_id=k,signature='fictional'))
            prepare(op)
            bundle=control.bundle('fictional-owner',project)
            self.assertEqual(len(bundle['shots']),68);self.assertEqual(sum(s['target_duration_ms'] for s in bundle['shots']),340126)
            last=bundle['shots'][-1];self.assertEqual(last['target_duration_ms'],5126)
            audio=next(a for a in bundle['assets'] if a['id']==last['reference_asset_ids'][1])
            self.assertEqual(audio['duration_ms'],5250)
            with wave.open(str(control.asset_root/audio['object_key']),'rb') as f:
                self.assertEqual(f.getnframes(),84000);self.assertEqual(f.getframerate(),16000)
            original=next(a for a in bundle['assets'] if a['mime_type']=='audio/mp4')
            self.assertEqual(original['sha256'],digest(song))
            with self.assertRaises(AssertionError):prepare(op)

    def test_four_hour_guard_only_in_signed_song_scope(self):
        scope='["fictional-owner","fictional-project"]'
        self.assertEqual(validate(scope,'batch',14400,0,trial='singing'),scope)
        for trial in ('comparison','first',None):
            with self.assertRaises(ValueError):validate(scope,'batch',14400,0,trial=trial)
        with self.assertRaises(ValueError):validate(scope,'batch',14401,0,trial='singing')
