"""Read existing owner assets on the controller; write isolated benchmark copies."""
import hashlib
import json
from pathlib import Path
import shutil
import subprocess
import sys


def main():
    sys.path.insert(0,'/opt/wan/current')
    from deployment.first_trial import control
    from workers.gpu.common import scoped, digest
    from services.controller.studio import StudioWorkspace
    c=control()
    saved=json.loads(Path('/var/lib/wan/singing-recovery-20261117/prepared.json').read_text())
    project=saved['project']
    bundle=c.bundle('john-hoyos',project)
    workspace=StudioWorkspace(c).get('john-hoyos')
    item=next(p for p in workspace['projects'] if p['bundle']['project']['id']==project)
    by_name={item['assetNames'].get(a['id']):a for a in bundle['assets']}
    assets={a['id']:a for a in bundle['assets']}
    song=assets[saved['original_song_asset_id']]
    song_path=scoped(c.asset_root,song['object_key'])
    assert digest(song_path)==saved['original_song_sha256']
    out=Path('/var/lib/wan/longcat-benchmark-20261117/inputs')
    out.mkdir(parents=True,exist_ok=True,mode=0o700)
    cases=[]; evidence=[]
    choices=[('miami',10,'miami.png','Miami Beach during daylight','Stable close-medium shot with a gentle push-in.'),
             ('new-york',35,'new-york.png','Times Square at night','Medium performance shot with gentle lateral camera movement.'),
             ('giza',75,'giza.png','the Pyramids of Giza during daylight','Medium-wide street-concert view with the singer clearly visible.')]
    for name,start,image_name,scene,camera in choices:
        asset=by_name[image_name];source=scoped(c.asset_root,asset['object_key'])
        assert digest(source)==asset['sha256'] and source.stat().st_size==asset['bytes']
        image=out/(name+'.png');shutil.copyfile(source,image)
        audio=out/(name+'.wav')
        subprocess.run(['ffmpeg','-nostdin','-v','error','-y','-ss',str(start),'-i',str(song_path),
                        '-t','4.72','-vn','-ac','1','-ar','16000','-c:a','pcm_s16le',str(audio)],check=True)
        data={'prompt':f'The man in the reference image sings the provided song into a handheld microphone at {scene}. His face remains recognizable, his lips follow the vocals, and his free hand moves naturally. A lively crowd dances behind him. {camera} Natural anatomy, consistent wardrobe, photorealistic lighting, no subtitles.',
              'cond_image':'/work/inputs/'+image.name,'cond_audio':{'person1':'/work/inputs/'+audio.name}}
        (out/(name+'.json')).write_text(json.dumps(data))
        cases.append({'id':name,'input_json':'/work/inputs/'+name+'.json'})
        evidence.append({'case':name,'source_start_seconds':start,'conditioning_seconds':4.72,
                         'output_seconds':3.72,'reference_sha256':asset['sha256'],
                         'audio_sha256':hashlib.sha256(audio.read_bytes()).hexdigest()})
    (out/'cases.json').write_text(json.dumps(cases))
    (out/'input-evidence.json').write_text(json.dumps({'project':project,'original_song_sha256':saved['original_song_sha256'],'cases':evidence},indent=2))
    (out/'READY').write_text('Input hashes checked; creative review pending.\n')
    print('LONGCAT_INPUTS_PREPARED',len(cases))


if __name__=='__main__':main()
