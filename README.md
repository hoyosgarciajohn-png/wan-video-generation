# Wan Video Generation

A private foundation for self-hosted Wan production using temporary Runpod GPU Pods. Target projects are music videos up to 5 minutes and short films and cartoons up to 30 minutes.

The local integration checkpoint includes the storyboard fixture UI, durable fixture controller, Wan worker source, CPU exporter and QA checks. See [integration evidence and remaining gates](docs/B05_INTEGRATION_CHECKPOINT.md). Hosted authentication, Studio/backend transport, paid GPU dispatch and production deployment remain pending.

## Start

Read [the master handoff](docs/WAN_00_Master_Handoff.md), [architecture](docs/ARCHITECTURE.md), [shared contract](docs/CONTRACT.md), and [workstream assignments](docs/WORKSTREAMS.md).

```sh
python3 -m venv .venv
. .venv/bin/activate
python -m pip install -r requirements-dev.txt
python scripts/validate_contract.py --media-root fixtures
python -m unittest discover -s tests -v
```

Install FFmpeg, including ffprobe, through your operating system package manager. Fixture media is synthetic and intentionally tiny. Run validation from the repository root. Python dependencies are confined to development checks at this stage.

The 0.1.0 schema and complete fictional project live under `contracts/` and `fixtures/`. The previous starter ZIP is an archived draft. Use this repository as the current source for implementations.
