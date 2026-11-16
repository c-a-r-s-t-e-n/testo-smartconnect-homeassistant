# Contributing

Open an issue describing expected behavior, integration/HA versions and sanitized field names.
Never attach raw customer exports, API keys, serial numbers or signed storage links.

Use Python 3.13 and `requirements-dev.txt`. Run `ruff check .`, `ruff format --check .`
and `pytest -q`. Add synthetic regression tests for parser, time, identity and quota changes.
Do not hard-code logger names, tenant IDs or serial numbers. Preserve existing unique IDs.
Update README, API mapping and changelog for changed behavior. Do not add device writes.

Release tags must match manifest.json (e.g. v0.1.0). Release workflow tests before packaging
and creates a prerelease. HACS custom repository installation uses the standard component
folder. Check all Validate jobs before tagging a release.
