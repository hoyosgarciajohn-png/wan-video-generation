"""Versioned, owner-scoped creative briefs. No paid dispatch in this release."""
import json
import math
import os
from services.controller.studio import StudioConflict, require
from services.providers.fal_music import MODELS, BY_ID


class Director:
    def __init__(self, studio):
        self.studio = studio
        with studio.control.transaction() as db:
            db.execute('CREATE TABLE IF NOT EXISTS director_briefs (project TEXT PRIMARY KEY, revision INTEGER NOT NULL, body TEXT NOT NULL)')

    def catalog(self):
        return dict(models=MODELS, provider='fal', configured=bool(os.environ.get('FAL_KEY')),
                    verified=False, paid_dispatch=False, pricing_checked='2026-11-18')

    def get(self, owner, project):
        with self.studio.control.transaction() as db:
            self.studio.control._load(db, owner, project)
            row = db.execute('SELECT revision,body FROM director_briefs WHERE project=?', (project,)).fetchone()
            return dict(revision=row[0], brief=json.loads(row[1])) if row else dict(revision=0, brief=None)

    def save(self, owner, project, request):
        with self.studio.control.transaction() as db:
            bundle = self.studio.control._load(db, owner, project)
            row = db.execute('SELECT revision FROM director_briefs WHERE project=?', (project,)).fetchone()
            revision = row[0] if row else 0
            if type(request.get('expected_revision')) is not int or request['expected_revision'] != revision:
                raise StudioConflict('Director revision conflict')
            b = request['brief']
            require(isinstance(b, dict), 'Invalid brief')
            fields = {'song_id','reference_ids','primary_id','start_ms','end_ms','direction','identity','lyrics','location','performance','model_id','resolution','aspect_ratio','budget_cents','target_minutes','shots'}
            require(set(b) == fields, 'Unknown or missing fields')
            for key in ('direction','identity','lyrics','location','performance'):
                require(isinstance(b[key], str) and len(b[key]) <= 16000, 'Invalid text')
            require(b['model_id'] in BY_ID, 'Unknown model')
            model = BY_ID[b['model_id']]
            require(b['resolution'] in model['resolutions'] and b['aspect_ratio'] in ('16:9','9:16'), 'Invalid output')
            require(type(b['budget_cents']) is int and 0 <= b['budget_cents'] <= 100000, 'Invalid budget')
            require(type(b['target_minutes']) is int and 1 <= b['target_minutes'] <= 120, 'Invalid target')
            require(type(b['start_ms']) is int and type(b['end_ms']) is int and 0 <= b['start_ms'] < b['end_ms'] <= 363000, 'Invalid song range')
            assets = {a['id']: a for a in bundle['assets']}
            require(isinstance(b['reference_ids'], list) and len(b['reference_ids']) <= 10 and all(isinstance(x,str) for x in b['reference_ids']), 'Invalid references')
            require(len(set(b['reference_ids'])) == len(b['reference_ids']), 'Duplicate references')
            for ref in b['reference_ids']:
                require(ref in assets and assets[ref]['mime_type'].startswith('image/'), 'Image must belong to project')
            require(b['primary_id'] is None or b['primary_id'] in b['reference_ids'], 'Primary reference missing')
            if b['song_id'] is not None:
                a = assets.get(b['song_id'])
                require(a is not None and a['mime_type'].startswith('audio/') and b['end_ms'] <= a['duration_ms'], 'Song range exceeds uploaded audio')
            require(isinstance(b['shots'],list) and len(b['shots']) <= 150, 'Invalid shots')
            cursor = b['start_ms']
            for shot in b['shots']:
                require(isinstance(shot,dict) and set(shot) == {'start_ms','end_ms','action','camera','singing'}, 'Invalid shot')
                require(type(shot['start_ms']) is int and type(shot['end_ms']) is int and shot['start_ms'] == cursor and shot['start_ms'] < shot['end_ms'] <= b['end_ms'], 'Shot timing gap or overlap')
                require(all(isinstance(shot[k],str) and len(shot[k]) <= 4000 for k in ('action','camera')) and type(shot['singing']) is bool, 'Invalid shot direction')
                cursor = shot['end_ms']
            require(not b['shots'] or cursor == b['end_ms'], 'Storyboard must cover selected audio')
            db.execute('INSERT INTO director_briefs VALUES (?,?,?) ON CONFLICT(project) DO UPDATE SET revision=excluded.revision,body=excluded.body', (project, revision+1, json.dumps(b, allow_nan=False)))
        return dict(revision=revision+1, brief=b)

    def review(self, owner, project):
        saved = self.get(owner, project)
        b = saved['brief']
        require(b is not None, 'Save a brief first')
        m = BY_ID[b['model_id']]
        issues = []
        if not b['song_id']: issues.append('Upload and select the song.')
        if not b['primary_id']: issues.append('Select the primary character photo.')
        if not b['shots']: issues.append('Build and review the shot plan.')
        for i,s in enumerate(b['shots']):
            seconds = (s['end_ms']-s['start_ms'])/1000
            if seconds % 1 or not m['min_seconds'] <= seconds <= m['max_seconds']:
                issues.append(f'Shot {i+1}: duration is outside this endpoint’s supported range.')
            if s['singing'] and not m['accepts_audio']:
                issues.append(f'Shot {i+1}: selected endpoint cannot accept the song for singing.')
        rate = m['cents_per_second'][b['resolution']]
        estimate = None if rate is None else sum(math.ceil((s['end_ms']-s['start_ms']) / 1000 * m['cents_per_second'][b['resolution']]) for s in b['shots'])
        if estimate is None: issues.append('Current provider quote required for this endpoint.')
        if estimate is not None and estimate > b['budget_cents']: issues.append('Estimated video cost exceeds the project budget.')
        return dict(revision=saved['revision'], issues=issues, estimate_cents=estimate,
                    estimate_note='Video generation estimate only; retries, reference images, editing and taxes excluded. Not a spending authorization.',
                    endpoint=m['endpoint'], provider=m['provider'], paid_dispatch=False)
