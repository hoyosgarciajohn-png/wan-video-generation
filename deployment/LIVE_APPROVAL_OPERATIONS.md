# Live approval authority: operator preparation

No real approval, signing key, host acceptance or spending limit has been created
for John. This document describes the trust setup required before using the new
admission source. Production dispatch remains disabled.

## Two separate identity checks

The API derives the requesting owner from its provisioned Studio session. A JSON
`owner_id` is not a substitute for that session. The approval service additionally
verifies a signed grant using a key installed by the trusted server operator and
bound to a specific owner. The grant's owner must match the authenticated session
and the saved project's owner.

A valid HMAC proves that a holder of the installed shared secret signed the exact
grant bytes. It does not prove that John personally reviewed them. The operator
must establish and record the owner's actual authorization before signing. Anyone
holding that secret can issue approvals for the bound owner. Keep the signing
process separate from the browser, worker, uploaded files and untrusted callers.
No request can install a new verification key or choose its own trust root.

## Provisioning responsibilities

| Item | Trusted location | Required handling |
|---|---|---|
| Studio access token | Existing external server secret configuration | Maps to the correct owner; never embed in frontend source |
| Approval signing/verification secret | Operator secret store and approval service | Independently generated high-entropy secret; bind key ID to one owner |
| Signed grant | Durable approval record | Exact bounded terms/configuration; treat as sensitive approval material |
| Runpod account API key | Future controller/cleanup service only | Never deliver to GPU worker or approval request body |
| Worker credential | Scoped worker runtime injection | Separate short-lived credential for the admitted batch |

Do not reuse the Studio token, Runpod key or worker credential as the HMAC secret.
Do not save signing secrets in Git, approval JSON, database rows, backups, logs,
screenshots or a shell command. No key-generation or signing endpoint is exposed
to users by this batch. Installation of authority is a trusted host responsibility;
the default local staging host does not enable it automatically.

Before provisioning an approval key, verify the owner account and record who is
authorized to sign for that owner. Establish rotation and compromise procedures.
Removing an old verification key must not mint a replacement grant or reset
historical reservations. Revocation blocks new admissions; cancellation and
liability recovery are separate operations. Restoring a database must not silently
reactivate copied authority.

## Grant review before signing

Review the exact project, pinned model, immutable image, launch configuration,
total USD cap, per-job runtime envelope, validity window and unique grant identity.
The owner's project limit remains unspecified today. A fictional test grant is
only test input and must never be installed as this project's real authorization.
Do not infer a cap from example values or from a general instruction to continue
implementation.

An authenticated grant supplies authorization, not infrastructure evidence. A
digest-shaped image name does not establish that the image was built, published,
or tested. A region/volume ID does not prove capacity or placement. Continue to
require the actual evidence described in `BUILD_VERIFICATION.md`,
`FIRST_WAN_RUN.md` and `RUNPOD_DEPLOYMENT.md`.

## Admission and release boundaries

The admission checkpoint saves a canonical job and budget reservation together.
It does not contact Runpod or run a worker. The public fixture routes and
simulation-only ledger retain their existing meaning. Never translate a simulated
approval into a real grant by changing a mode field.

Keep an admitted job blocked until its independently reviewed production
execution path can enforce the grant, current budget, deadline, verified build,
host/storage acceptance, scoped credentials and independent cleanup. This batch
does not remove those launch gates. It does not prove real Wan compatibility,
actual costs or human creative acceptance.

Before the first permitted launch, review the specific release and resource
action with the owner. Record the actual cap and runtime; bind them to the job
and tested configuration. Afterward, record observed output, termination and
final charges. A reservation is an estimate and cannot guarantee a provider-level
hard spending stop during network or control-plane failures.
