"""Fictional-only director persistence and exact hosted endpoint mappings."""
import copy
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import Mock
from services.controller.http_api import StudioAPI
from services.controller.service import ControlService
from services.controller.studio import StudioWorkspace, StudioConflict
from services.providers.fal_music import payload, FalMusicClient


class DirectorTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory(); self.addCleanup(self.temp.cleanup)
        root=Path(self.temp.name)
        self.studio=StudioWorkspace(ControlService(root/'db',root/'assets'))
        self.pid=self.studio.create('alice','Fictional concert','music_video',0)['projects'][0]['bundle']['project']['id']
        self.api=StudioAPI(self.studio,{'a'*40:'alice','b'*40:'bob'})
        self.director=self.api.director
        self.brief=dict(song_id=None,reference_ids=[],primary_id=None,start_ms=0,end_ms=60000,direction='Fictional concert',identity='Blue cap',lyrics='',location='Beach',performance='Dance and sing',model_id='ltx-fast',resolution='1080p',aspect_ratio='16:9',budget_cents=2000,target_minutes=10,shots=[dict(start_ms=i*5000,end_ms=(i+1)*5000,action='Dance',camera='Track',singing=True) for i in range(12)])

    def save(self,b=None,revision=0):
        return self.director.save('alice',self.pid,dict(expected_revision=revision,brief=b or self.brief))

    def test_backup_restore_preserves_brief(self):
        from services.controller.backup import create_backup, restore_backup
        from services.controller.director import Director
        self.save()
        root=Path(self.temp.name)
        create_backup(self.studio.control.db_path,self.studio.control.asset_root,root/'backup')
        restored=restore_backup(root/'backup',root/'restored')
        service=ControlService(restored['database'],restored['assets'])
        self.assertEqual(Director(StudioWorkspace(service)).get('alice',self.pid)['brief'],self.brief)

    def test_save_reload_revision_and_tenant(self):
        self.assertEqual(self.save()['revision'],1)
        self.assertEqual(self.director.get('alice',self.pid)['brief'],self.brief)
        with self.assertRaises(StudioConflict): self.save()
        with self.assertRaises((PermissionError,KeyError)): self.director.get('bob',self.pid)
        with self.assertRaises((PermissionError,KeyError)): self.director.save('bob',self.pid,dict(expected_revision=1,brief=self.brief))

    def test_foreign_assets_timing_and_budget_rejected(self):
        for field,value in [('song_id','foreign-audio'),('reference_ids',['foreign-image']),('primary_id','missing'),('budget_cents',True),('start_ms',-1),('end_ms',0)]:
            b=copy.deepcopy(self.brief);b[field]=value
            with self.subTest(field=field),self.assertRaises(ValueError):self.save(b)
        b=copy.deepcopy(self.brief);b['shots'][1]['start_ms']=5100
        with self.assertRaises(ValueError):self.save(b)
        b=copy.deepcopy(self.brief);b['shots'].pop()
        with self.assertRaises(ValueError):self.save(b)

    def test_review_flags_singing_incompatible_model_and_missing_inputs(self):
        b=copy.deepcopy(self.brief);b.update(model_id='kling-image',resolution='720p',budget_cents=1)
        self.save(b);r=self.director.review('alice',self.pid)
        self.assertTrue(any('cannot accept' in x for x in r['issues']))
        self.assertTrue(any('exceeds' in x for x in r['issues']))
        self.assertEqual(r['estimate_cents'],948)
        self.assertFalse(r['paid_dispatch'])

    def test_unknown_quote_and_config_do_not_claim_verified(self):
        b=copy.deepcopy(self.brief);b.update(model_id='seedance-reference',resolution='720p')
        self.save(b);self.assertIsNone(self.director.review('alice',self.pid)['estimate_cents'])
        self.assertFalse(self.director.catalog()['verified'])
        self.assertFalse(self.director.catalog()['paid_dispatch'])

    def test_authenticated_http_routes_and_no_paid_route(self):
        h={'Host':'127.0.0.1:5173','Origin':'http://127.0.0.1:5173','X-WAN-Request':'studio','Content-Type':'application/json'}
        url=f'/v1/studio/projects/{self.pid}/director'
        self.assertEqual(self.api.dispatch('GET',url,h).status,401)
        r=self.api.dispatch('POST','/v1/studio/session',h,json.dumps({'token':'a'*40}).encode())
        h['Cookie']=r.headers['Set-Cookie'].split(';')[0]
        self.assertEqual(self.api.dispatch('PUT',url,h,json.dumps(dict(expected_revision=0,brief=self.brief)).encode()).status,200)
        self.assertEqual(self.api.dispatch('GET',url,h).data['revision'],1)
        self.assertEqual(self.api.dispatch('POST',url+'/render',h,b'{}').status,404)
        h['Origin']='https://evil.example'
        self.assertEqual(self.api.dispatch('PUT',url,h,b'{}').status,403)


class ProviderTests(unittest.TestCase):
    def setUp(self):
        self.shot=dict(prompt='Fictional concert',image_urls=['https://example.com/reference.png'],audio_url='https://example.com/clip.wav',duration_ms=5000,resolution='1080p',aspect_ratio='16:9')

    def test_ltx_wan_and_seedance_exact_fields(self):
        ltx=payload('ltx-fast',**self.shot)
        self.assertIn('audio_url',ltx);self.assertNotIn('duration',ltx);self.assertNotIn('resolution',ltx)
        wan=payload('wan-reference',**self.shot)
        self.assertEqual(wan['reference_audio_urls'],[self.shot['audio_url']]);self.assertFalse(wan['enable_prompt_expansion'])
        sd=payload('seedance-reference',**self.shot)
        self.assertEqual(sd['duration'],'5');self.assertEqual(sd['audio_urls'],[self.shot['audio_url']])

    def test_kling_rejects_song_and_unsupported_reference_count(self):
        with self.assertRaises(ValueError):payload('kling-image',**self.shot)
        self.shot['audio_url']=None
        self.assertEqual(payload('kling-image',**self.shot)['start_image_url'],self.shot['image_urls'][0])
        self.shot['image_urls']*=2
        with self.assertRaises(ValueError):payload('kling-image',**self.shot)

    def test_transport_never_retries_or_leaks_key_to_other_host(self):
        opener=Mock();opener.open.side_effect=TimeoutError('uncertain submit')
        client=FalMusicClient('fictional-key',opener)
        with self.assertRaises(TimeoutError):client.submit('ltx-fast',**self.shot)
        self.assertEqual(opener.open.call_count,1)
        with self.assertRaises(ValueError):client.status({'status_url':'https://evil.example/status'})
        self.assertEqual(opener.open.call_count,1)
        self.assertEqual(opener.open.call_args.args[0].full_url,'https://queue.fal.run/lightricks/ltx-2.5/audio-to-video/fast')
