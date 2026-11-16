# Contributing

Use Python 3.13 with the minimum Home Assistant baseline:

```bash
python -m pip install -r requirements-dev.txt
ruff check .
ruff format --check .
pytest -q
```

CI also runs the suite on Python 3.14 with Home Assistant 2026.11.2. Integration runtime dependencies are supplied by Home Assistant. Pillow is only needed to regenerate branding with `python scripts/build_branding.py`.

Add regression tests for behavior changes. Use synthetic fixtures; do not commit private exports, API keys, signed download URLs or device/account identifiers. Keep entity unique IDs stable. Distinguish missing data, stale data, invalid data and API failures. Document any changes to quota consumption or alarm semantics.

Before publishing, verify Ruff, tests on both baselines, hassfest and HACS checks. Release tags must match the manifest version. The release workflow builds the component-only ZIP and publishes it on the matching GitHub release.
