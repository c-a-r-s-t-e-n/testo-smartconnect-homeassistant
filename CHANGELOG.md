# Changelog

## 0.1.1 — 2026-11-16

- Replace raw region codes with translated dropdown labels and add a Testo Cloud link to setup.
- Normalize time-filter requests to UTC seconds with a `Z` suffix, matching the successful diagnostic script; retain a 24-hour recovery window when no channel samples exist.
- Add per-channel data-status diagnostics, safe measurement error attributes and actual export row counts to distinguish failed exports from unused, invalid or stale channels.
- Prioritize measurement exports, share entity lookup indexes, parse CSV off the event loop and persist budget reservations separately from the full cache.
- Prevent quota reservations during rate-limit cooldown; expire abandoned jobs and recover from expired result downloads without immediate POST retries.
- Validate measurement columns, reject malformed download URLs and handle nullable alarm configuration.
- Rewrite the README in technical English with upgrade, troubleshooting, API budget and alarm semantics documentation.
- Add regression coverage for request date formatting, recovery, export-to-entity mapping, missing data, nullable metadata, region labels and shared indexes.

Measurement availability still requires confirmation in the reporting user's live installation. Authentication, discovery and battery readings have been confirmed; an exact live failure cause was not available from screenshots alone.

## 0.1.0 — 2026-11-16

Initial community preview: six API domains, channel measurements, logger diagnostics, thresholds, observed alarms, UI configuration, persistent cache and API budget protection.
