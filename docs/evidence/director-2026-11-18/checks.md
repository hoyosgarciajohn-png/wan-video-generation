# Fictional validation — November 18, 2026

- `python scripts/validate_contract.py --media-root fixtures`: PASS.
- `python -m unittest discover -s tests -v`: 249 run, OK, one skip.
- `npm test --prefix apps/studio`: 18 passed.
- `npm run test:ui --prefix apps/studio`: 19 passed.
- `npm run build --prefix apps/studio`: TypeScript and Vite PASS.
- `git diff --check`: PASS.
- Browser: fictional project selection, 12-shot build, save/review with missing
  audio and image issues, reload and restored shot count; desktop visual review.
- Backup: new Director table included, fictional restore preserves brief.
- Provider: fake transport verifies exact payloads, rejection of unsupported
  singing input, no automatic retry after unknown submission, URL host restriction.

Initial checks exposed missing local `.venv` for Node contract tests and a new
brief-table rejection in backups. Created the expected local environment and
fixed the backup validator, then reran affected checks successfully.

No real user media, GPU, paid generation or live provider credentials used.
Model access, generated quality, mobile browser acceptance and production remain
unverified. Screenshot is fictional QA, not a deployed service.
