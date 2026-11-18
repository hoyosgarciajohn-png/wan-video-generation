"""Private preflight/admission CLI; consumes signatures but cannot sign or rent GPUs."""
import argparse
import json
import os
from pathlib import Path

from services.controller.longcat import LongCatTransport, source_digest
from services.controller.service import ControlService
from workers.gpu.common import atomic_json
from workers.gpu.longcat_batch import fingerprint, validate_manifest, validate_reference_images


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('operation',choices=['preflight','admit','assemble-review'])
    p.add_argument('--inputs',type=Path,required=True)
    p.add_argument('--database',type=Path)
    p.add_argument('--assets',type=Path)
    p.add_argument('--owner')
    p.add_argument('--owner-envelope',type=Path)
    p.add_argument('--host-envelope',type=Path)
    p.add_argument('--keys',type=Path)
    p.add_argument('--credential-output',type=Path)
    p.add_argument('--scope-id')
    p.add_argument('--master',type=Path)
    p.add_argument('--master-sha256')
    p.add_argument('--review-output',type=Path)
    a=p.parse_args()
    manifest=validate_manifest(json.loads((a.inputs/'manifest.json').read_text()),a.inputs)
    validate_reference_images(manifest,a.inputs)
    if a.operation=='preflight':
        print(json.dumps(dict(status='INPUTS_VALIDATED_NO_GPU',shots=len(manifest['shots']),
              duration_ms=manifest['duration_frames']*40,manifest_sha256=fingerprint(manifest),source_sha256=source_digest())))
        return
    if a.operation=='assemble-review':
        if not all((a.database,a.assets,a.owner,a.scope_id,a.master,a.master_sha256,a.review_output)):
            p.error('Review assembly requires durable controller paths, owner, scope, complete master hash and output')
        from workers.media.longcat_assemble import assemble_review
        service=LongCatTransport(ControlService(a.database,a.assets))
        with service.control.transaction() as db:
            row=db.execute('SELECT project,manifest FROM longcat_scopes WHERE id=? AND owner=?',
                           (a.scope_id,a.owner)).fetchone()
            if not row:raise ValueError('Scope unavailable')
            service.control._load(db,a.owner,row[0])
            if fingerprint(json.loads(row[1]))!=fingerprint(manifest):raise ValueError('Stored manifest changed')
            receipts=[]
            for shot in manifest['shots']:
                receipt=db.execute('SELECT receipt FROM longcat_shots WHERE scope=? AND shot=? AND state=?',
                                   (a.scope_id,shot['id'],'published')).fetchone()
                if not receipt:raise ValueError('Complete review requires every durable shot')
                receipts.append(json.loads(receipt[0]))
        print(json.dumps(assemble_review(manifest,receipts,a.assets,a.master,a.master_sha256,a.review_output)))
        return
    if not all((a.database,a.assets,a.owner,a.owner_envelope,a.host_envelope,a.keys,a.credential_output)):
        p.error('Admission requires persistent controller paths, owner/host envelopes, installed keys and private credential output')
    if a.credential_output.exists():p.error('Credential destination exists; do not overwrite/replay an admission')
    config=json.loads(a.keys.read_text())
    def keys(name):return {k:(v['owner'],bytes.fromhex(v['key_hex'])) for k,v in config[name].items()}
    # Reserve the credential destination before the admission transaction so a
    # failure cannot accidentally overwrite another live worker credential.
    fd=os.open(a.credential_output,os.O_WRONLY|os.O_CREAT|os.O_EXCL,0o600)
    try:
        service=LongCatTransport(ControlService(a.database,a.assets))
        result=service.admit(a.owner,manifest,a.inputs,json.loads(a.owner_envelope.read_text()),
            json.loads(a.host_envelope.read_text()),approval_keys=keys('owner'),host_keys=keys('host'))
        with os.fdopen(fd,'w') as out:
            fd=None;json.dump(result,out);out.write('\n');out.flush();os.fsync(out.fileno())
        print(json.dumps(dict(status='SCOPE_ADMITTED_NO_POD_CREATED',scope_id=result['scope_id'],deadline=result['deadline'])))
    finally:
        if fd is not None:os.close(fd)
    # If the credential write failed after admission, revoke/reconcile the scope.
    # Never retry the consumed admission to mint a new deadline or reservation.


if __name__=='__main__':main()
