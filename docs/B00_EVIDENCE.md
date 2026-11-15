# B00 evidence
Date November 15, 2026

Repository created as private under hoyosgarciajohn-png/wan-video-generation. Connector metadata confirms admin, push and pull access. The initial repository contained a README and no AGENTS.md. Project instructions are introduced with this foundation.

The foundation is reviewed through setup/b00-foundation and a pull request. Local checks validate the fictional contract and media plus the fake provider's allocation/deletion behaviors. Record commands and results below after execution.

The backend controller, deployed authentication, GPU inference, paid billing, production shutdown and creative acceptance require their scheduled batches. The fake provider is in-memory and has no external effects.

## Recorded local results

- `python scripts/validate_contract.py --media-root fixtures` passed, including asset checksums and ffprobe metadata.
- `python -m unittest discover -s tests -v` passed all 14 tests.
- JSON Schema meta-validation passed. Tested dependency is jsonschema 4.26.0.
- Schema tests cover references, ownership fields, budgets, frozen snapshots, lease timestamps, historical timeline approvals, export references and malformed media records.
- Fake-provider tests cover an allocation hidden by timeout, duplicate allocation on blind retry, a failed deletion and idempotent deletion.

Runpod compute charges incurred during B00 are $0 and Runpod resources created are zero. The tested fixture has a two-second blue clip and matching synthetic audio. These checks establish the foundation and fixtures. Real GPU timing, image quality, controller durability and hosted lifecycle remain for their owning batches.

Publication and workstream branch confirmation are recorded in [B00 issue 1](https://github.com/hoyosgarciajohn-png/wan-video-generation/issues/1). The merged foundation PR identifies the exact baseline commit.
