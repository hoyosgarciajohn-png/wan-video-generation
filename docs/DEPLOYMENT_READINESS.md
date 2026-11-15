# Local staging and deployment readiness

November 15, 2026. This package runs the connected Studio, durable SQLite/assets,
CPU fixture renderer and exporter on one local origin. It does not deploy a hosted
service, run Wan, provision a GPU, or establish production readiness. The existing
Python development HTTP handler remains the API transport; do not publish it to
the Internet or treat a reverse proxy as a production-hardening substitute.

## Native local staging

Use Linux, Python 3.11+ and FFmpeg/ffprobe. Node 22.12+ is needed for the Studio
build. Run these commands from the repository root as your regular user. Choose
an absolute external directory without spaces; `/home/john/wan-local` below is an
example to replace with your own location.

```sh
python -m deployment.prepare /home/john/wan-local --owner john
python3.11 -m venv /home/john/wan-local/venv
/home/john/wan-local/venv/bin/python -m pip install --require-hashes --only-binary=:all: -r deployment/requirements.lock
npm --prefix apps/studio ci
npm --prefix apps/studio run build
python deployment/check_artifacts.py --static --runtime-import
WAN_STUDIO_TOKEN_FILE=/home/john/wan-local/tokens.json WAN_STUDIO_ORIGIN=http://127.0.0.1:8080 /home/john/wan-local/venv/bin/python -m deployment.local_stage --state /home/john/wan-local/state
```

Open `http://127.0.0.1:8080`. The generated external `tokens.json` contains a
JSON object mapping one random token to the owner. Open it privately and use that
key in the Studio connection form. The preparer prints only the settings path,
uses mode 0600 for the token/settings files, refuses repository-local state, and
will not overwrite an existing configuration. Secrets are not bundled into the
Studio, Docker image or source archive. Rotate a token by editing the external
file while stopped, then restarting; in-memory sessions are invalidated on restart.

`state/studio.sqlite`, its SQLite sidecars/lock files and `state/assets` must stay
together on persistent storage. The static build contains only application code
and fictional public fixtures. Private uploaded/generated files are served only
through the authenticated API. No Vite development server/proxy is needed here:
static files and `/v1/studio` share the exact origin. Unknown API paths never
become SPA pages. Static serving confines decoded paths and symlinks to `dist`,
refuses hidden files, and supplies CSP, no-store and nosniff headers.

`GET /healthz` checks database access and fixture/export worker thread liveness.
It exposes no credentials or project data. It is a local readiness signal, not a
media-integrity, storage-capacity, successful-job or GPU-health guarantee. Stop
with Ctrl-C or SIGTERM. Admission stops and background jobs receive a stop signal;
each worker receives up to 60 seconds to exit. Durable job recovery still handles
interrupted work. Take backups using [BACKUP_RESTORE.md](BACKUP_RESTORE.md), not by
copying an active SQLite file alone.

## Container package — prepared, not built here

`deployment/Dockerfile` builds static Studio with `npm ci`, then packages only the
CPU service/source subset, FFmpeg and static artifact. All three image inputs are
pinned by registry digest. The six runtime Python packages/hashes are copied from
`workers/gpu/requirements.lock`; `check_artifacts.py` detects divergence. No CUDA,
PyTorch, model weights or GPU requirements are installed. `Dockerfile.dockerignore`
starts deny-all and allows only required source, lockfiles and fictional fixtures.

The prepared Compose service has a read-only root filesystem, temporary `/tmp`,
no added capabilities, no-new-privileges, a healthcheck, external state and a
read-only external secret-file mount. It runs as the regular host UID/GID written
by `prepare.py`. The container must listen on its internal interface, but Compose
publishes **only `127.0.0.1`**. Do not replace that binding with `0.0.0.0`.

On a Linux amd64 host with a working Docker daemon and Compose:

```sh
docker compose --env-file /home/john/wan-local/compose.env -f deployment/compose.yaml config
docker compose --env-file /home/john/wan-local/compose.env -f deployment/compose.yaml up --build -d
docker compose --env-file /home/john/wan-local/compose.env -f deployment/compose.yaml ps
docker image inspect wan-studio-local:staging --format '{{.Id}}'
docker compose --env-file /home/john/wan-local/compose.env -f deployment/compose.yaml down
```

Keep the build log and resulting image ID. `down` leaves external state/secrets
intact. Change `WAN_PORT` in the external settings file if needed; Compose keeps
the API origin and loopback published port aligned. The local staging cookie is
HttpOnly/SameSite Strict; HTTP loopback intentionally has no Secure attribute.
This is another reason the package is not a public deployment configuration.

## Starting a verified restore

Restore outputs use `database.sqlite`, whereas a new staging workspace defaults
to `studio.sqlite`. Explicit restore paths prevent silently starting a new empty
workspace. Verify the backup/restore first as documented in BACKUP_RESTORE.md.
Then start the restored paths explicitly:

```sh
WAN_STUDIO_TOKEN_FILE=/home/john/wan-local/tokens.json WAN_STUDIO_ORIGIN=http://127.0.0.1:8080 /home/john/wan-local/venv/bin/python -m deployment.local_stage --state /home/john/wan-restored --database /home/john/wan-restored/database.sqlite --assets /home/john/wan-restored/assets
```

A state directory marked `RESTORED.json` refuses startup without an explicit database override. An explicit database/assets override must already exist; a misspelled restore
path fails instead of creating a database. Token-to-owner mapping must match the
owners in the restored database. Tokens are deliberately outside the data backup.
For Compose, set external `WAN_STATE_DIR=/home/john/wan-restored`,
`WAN_DATABASE_PATH=/data/database.sqlite` and `WAN_ASSETS_PATH=/data/assets` before
starting. These map to the same validated path overrides inside the container.
Do not run two staging instances against one restored state directory.

## Verification and remaining gates

| Evidence | Result |
|---|---|
| Fresh Docker/Podman probe | Neither executable is installed; no container build or run occurred |
| Docker Registry metadata | Node 22 bookworm and Python 3.11 bookworm index digests resolved over authenticated registry HTTPS; no image layers pulled |
| Runtime dependency resolution | Six Linux amd64/Python 3.11 wheels downloaded with `--require-hashes`; no installation; temporary wheel directory removed |
| `python -m unittest deployment.test_staging -v` | 8 tests: real loopback HTTP/static/auth, confinement, health, secret preparation, isolated runtime source imports, restored DB startup and SIGTERM |
| `python deployment/check_artifacts.py --static --runtime-import` | Pins, lock subset, built static references and isolated runtime COPY imports pass |
| Built Studio process smoke | Real static artifact served; both CPU workers ready; health 200; SIGTERM exit 0; external database retained |
| Compose YAML parse | Parsed successfully; actual Compose validation/runtime unverified |

Native tests ran on Python 3.12.14 and Node 24.22.1. Container inputs target Python
3.11 and Node 22; their actual image startup remains unverified. The isolated
COPY-source import test checks missing files/imports, not image layers or ABI.
Before any hosted release, use a production HTTP/service design, deployment-specific
TLS/secret operations, restore drills and owner release approval. Browser-native
acceptance and real Wan creative quality remain separate open gates.

The GPU worker already has pinned CUDA/PyTorch/FFmpeg inputs and dependency hashes
in `workers/gpu/Dockerfile`. Its previous BuildKit attempt failed because the host
forbade required Unix sockets; no GPU worker image digest/build or CUDA inference
was established. See `workers/gpu/evidence/BUILD_ATTEMPT.md`. A Docker-capable host
must build and smoke both prepared images before those gates close. B06 still
requires John's explicit GPU dollar ceiling and runtime envelope. This staging
work incurred no provider spend and left no service running.
