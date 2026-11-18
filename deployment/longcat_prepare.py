"""Build immutable private image/audio inputs without renting or signing a scope."""
import argparse
import json
from pathlib import Path
import shutil
import zipfile

from workers.gpu.common import atomic_json, digest, require, scoped
from workers.gpu.longcat_batch import (PROTOCOL, fingerprint, validate_manifest,
                                      validate_reference_images)


def prepare(plan, scenes, scene_root, audio_zip, destination, *, project_id, batch_id):
    destination=Path(destination)
    require(not destination.exists(), 'Destination exists; never overwrite a frozen input bundle')
    require(plan['fps']==25 and plan['timeline_frames']==9072 and len(plan['shots'])==110,
            'Complete approved 362.88-second / 110-shot plan required')
    lookup={s['id']:s for s in scenes}
    require(len(scenes)==len(lookup)==18, 'Exactly 18 distinct scene anchors required')
    for shot in plan['shots']:
        require(shot['concept_panel'] in lookup and shot['headwear_required'] is True,
                'Unmapped scene or missing headwear requirement')
    # Validate all sources before creating the destination. The ZIP is not
    # extracted generically: only the exact 110 named conditioning files are read.
    for scene in scenes:
        source=scoped(scene_root,scene['path'])
        require(source.is_file() and digest(source)==scene['sha256'],'Scene source changed')
    with zipfile.ZipFile(audio_zip) as archive:
        names=archive.namelist()
        require(len(names)==len(set(names)), 'Duplicate ZIP members refused')
        for shot in plan['shots']:
            info=archive.getinfo('conditioning/'+shot['shot_id']+'.wav')
            require(151000<=info.file_size<=160000,'Unexpected conditioning size')
        destination.mkdir(parents=True)
        (destination/'images').mkdir();(destination/'audio').mkdir()
        images={}
        for scene in scenes:
            relative='images/scene_'+str(scene['id']).zfill(2)+'.png'
            shutil.copyfile(scoped(scene_root,scene['path']),destination/relative)
            images[scene['id']]=dict(path=relative,sha256=digest(destination/relative))
        shots=[]
        for shot in plan['shots']:
            relative='audio/'+shot['shot_id']+'.wav'
            (destination/relative).write_bytes(archive.read('conditioning/'+shot['shot_id']+'.wav'))
            # Retain the already approved audio offset and existing edit trims.
            trim=shot['source_trim_in_frames']
            shots.append(dict(id=shot['shot_id'],frames=shot['frames'],in_frame=shot['in_frame'],
                trim_in_frames=trim,audio_start_frame=shot['in_frame']-trim,
                seed=20261117+len(shots),prompt=shot['prompt'],headwear_required=True,
                image=images[shot['concept_panel']],audio=dict(path=relative,sha256=digest(destination/relative))))
    manifest=dict(protocol=PROTOCOL,project_id=project_id,batch_id=batch_id,fps=25,
                  duration_frames=9072,shots=shots)
    validate_manifest(manifest,destination);validate_reference_images(manifest,destination)
    atomic_json(destination/'manifest.json',manifest)
    atomic_json(destination/'preparation.json',dict(status='INPUTS_VALIDATED_NO_GPU',
        manifest_sha256=fingerprint(manifest),scene_count=18,shot_count=110,
        duration_seconds=362.88,source_audio_zip_sha256=digest(audio_zip),
        master_wav_sha256=plan['audio']['master_wav_sha256'],
        creative_status='Individual frames ready for review; musical cut alignment pending',
        render_status='No execution grant or provider allocation created')))
    return manifest


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--plan',type=Path,required=True);p.add_argument('--scenes',type=Path,required=True)
    p.add_argument('--audio-zip',type=Path,required=True);p.add_argument('--output',type=Path,required=True)
    p.add_argument('--project-id',required=True);p.add_argument('--batch-id',required=True)
    a=p.parse_args()
    manifest=prepare(json.loads(a.plan.read_text()),json.loads(a.scenes.read_text()),a.scenes.parent,
        a.audio_zip,a.output,project_id=a.project_id,batch_id=a.batch_id)
    print(json.dumps(dict(status='INPUTS_VALIDATED_NO_GPU',manifest_sha256=fingerprint(manifest),
                         shots=len(manifest['shots']),duration_seconds=362.88)))


if __name__=='__main__':main()
