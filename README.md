# Testo Smart Connect for Home Assistant

[![Validate](https://github.com/c-a-r-s-t-e-n/testo-smartconnect-homeassistant/actions/workflows/validate.yml/badge.svg)](https://github.com/c-a-r-s-t-e-n/testo-smartconnect-homeassistant/actions/workflows/validate.yml)
[![Release](https://img.shields.io/github/v/release/c-a-r-s-t-e-n/testo-smartconnect-homeassistant?include_prereleases)](https://github.com/c-a-r-s-t-e-n/testo-smartconnect-homeassistant/releases)
[![License: MIT](https://img.shields.io/badge/license-MIT-blue.svg)](LICENSE)
[![HACS](https://img.shields.io/badge/HACS-custom%20integration-41BDF5)](https://hacs.xyz/)

An independent, read-only community integration for an **existing Home Assistant installation**. It retrieves logger measurements, device diagnostics, measurement-site assignments, configured thresholds and alarm events through the official Testo Smart Connect API.

**Status: community preview, version 0.1.1.** API authentication, installation, device discovery and battery readings have been confirmed in a user's installation. Measurement availability is under investigation; this release improves request compatibility, recovery and diagnostics. Automated tests and replay of a private export do not replace an end-to-end live test. This project is not affiliated with Testo and does not replace Testo alarm delivery or HACCP records.

## Requirements

- Home Assistant **2025.3 or later**.
- A Testo Smart Connect account with the paid **API add-on** and a valid API key.
- Outbound HTTPS access to the regional Testo API and its signed S3 result storage.
- HACS for the recommended installation method.

The EU export was verified with logger model codes `0572 2031`, `0572 2032`, `0572 2033` and `0572 2035`. Discovery uses API identifiers, not a fixed model list. AM and AP use the documented regional hosts but have not been tested with live accounts. Legacy Saveris APIs, mobile instruments without Smart Connect exports, and Polarfoxx are outside this project's scope.

## Install with HACS

[![Open repository in HACS](https://my.home-assistant.io/badges/hacs_repository.svg)](https://my.home-assistant.io/redirect/hacs_repository/?owner=c-a-r-s-t-e-n&repository=testo-smartconnect-homeassistant&category=integration)

1. Open **HACS → Custom repositories**.
2. Add `https://github.com/c-a-r-s-t-e-n/testo-smartconnect-homeassistant`, category **Integration**.
3. Download **Testo Smart Connect**. Enable pre-release versions if necessary and select the desired release.
4. Restart Home Assistant completely.
5. Open **Settings → Devices & services → Add integration → Testo Smart Connect**.
6. Enter the API key and select **Europe (EU)**, **Americas (AM)** or **Asia Pacific (AP)** to match your account. The setup dialog includes a link to the [European Testo Cloud](https://www.eu.smartconnect.testo.com/).
7. Allow several minutes for the initial exports to complete.

This is a HACS custom repository, not a Supervisor add-on. It has not been admitted to the default HACS catalog. No YAML configuration, VPN or direct logger access is required.

For manual installation, copy `custom_components/testo_smartconnect` to `/config/custom_components/testo_smartconnect`, restart Home Assistant, and follow steps 5–7.

## Update from 0.1.0

Download **0.1.1** in HACS and restart Home Assistant. Keep the existing integration entry: API credentials, device identifiers and existing entity unique IDs are preserved. New diagnostic entities are discovered automatically. The stored API budget is migrated without resetting the monthly counter.

The new per-channel **data status** sensor distinguishes `ok`, `api_error`, `no_data`, `invalid_value` and `stale`. Check this sensor if a measurement remains unavailable; do not delete the integration or repeatedly submit setup requests.

## Data coverage

All six Smart Connect export domains are queried without a restrictive `$select`. Full field inventory and mapping rules: [docs/API.md](docs/API.md).

| Domain | Endpoint | Integration use |
|---|---|---|
| Devices and channels | `/v3/devices/properties` | Identity, names, model, firmware, units, capabilities and intervals |
| Device status | `/v4/devices/status` | Battery, radio quality, power and communication times |
| Measurements | `/v2/measurements` | Latest measurement per sensor and channel, unit and UTC timestamp |
| Measuring objects | `/v1/measuring-objects` | Channel assignments, thresholds, delay and hysteresis metadata |
| Locations | `/v1/locations` | Measurement-site names |
| Alarms | `/v3/alarms` | Observed alarm events and latest event states in a rolling 24-hour window |

The current OpenAPI specification defines device status **v4**. Some narrative examples still use v3; this integration follows the specification and the verified export.

### Channel entities

| Entity | Behavior |
|---|---|
| Measurement | Numeric physical value; temperature and humidity use Home Assistant device classes |
| Sample time | UTC time of the actual measurement |
| Sample age | Minutes since that measurement |
| Data status | `ok`, `api_error`, `no_data`, `invalid_value` or `stale` |
| Data stale | Problem sensor; also on when no sample has ever been received |
| Invalid measurement | Whether the latest sample contains an invalid numeric value; unknown without a sample |
| Lower / upper limit | Unambiguous configured limits; disabled by default |
| Outside configured limits | Immediate comparison with the configured limits; no Testo delay/hysteresis simulation |

Measurement attributes include `data_status`, `measurement_error`, `last_successful_measurement_fetch`, `sample_time`, the physical property and reported channel metadata. Unavailable measurements remain unavailable instead of silently reporting zero or an old value as current.

**A discovered channel is not proof of a working probe.** An export used during development contained 13 channel definitions but current measurements for only six. Unused, disconnected or faulty channels can correctly remain unavailable.

### Logger entities

Battery level, radio quality (percent, not RSSI/dBm), battery temperature if available, reported external power, last/next communication, status timestamp, connection type, firmware, measurement/communication intervals, observed active alarm count and last observed alarm time.

Battery temperature, next communication and status timestamp are disabled by default. Enable them in the entity registry if needed. Empty boolean or numeric fields remain unknown. Some diagnostics are visible on the device page rather than the automatic overview dashboard.

Home Assistant assigns entity IDs from names and existing registry entries. Copy actual IDs from Developer Tools; examples below are placeholders. Device links open the matching regional Testo Cloud portal. Entity labels are currently English; setup and options are translated into English and German.

## Polling, latency and API budget

| Export | Default interval |
|---|---:|
| Measurements | 10 minutes, configurable from 10–60 |
| Device status | 30 minutes |
| Alarms | 30 minutes, querying the preceding 24 hours |
| Devices, measuring objects, locations | Each once per 24 hours |

All loggers share one export per domain; there is no per-device polling. These defaults require approximately **7,533 POST requests in a 31-day month**, plus setup, recovery and retries. Longer measurement intervals also delay the scheduler's other checks, so status/alarm intervals are minimum ages rather than independent timers.

Testo documents a limit of **10,000 POST requests per account per month**. GET polling and result downloads do not consume that POST allowance. A persisted local counter stops new exports at 9,500 requests. It does not know requests made by other clients or setup validation. Month rollover uses UTC; the server remains authoritative.

- Export requests use UTC timestamps formatted as `YYYY-MM-DDTHH:MM:SSZ`, matching the successful diagnostic script.
- Initial measurement retrieval covers 24 hours. Subsequent retrieval overlaps the last successful fetch by one hour; recovery is capped at 24 hours. If no channel samples exist, retrieval continues to use the 24-hour window.
- Only the newest sample per sensor/channel is retained. Historical values are not backfilled into Home Assistant Recorder.
- The default stale threshold is 60 minutes, configurable from 15–1,440 minutes. Time diagnostics update on the polling cycle.
- Actual freshness also depends on logger transmission intervals and Testo processing latency. This API is not a real-time stream.

## Reliability and performance

The client submits an asynchronous export, polls its request UUID with bounded backoff, then reads **all** result files. Pending jobs are resumed within the running process. Jobs older than 55 minutes and expired storage results are discarded so a later refresh can submit a replacement. POST requests are never automatically retried within the same query.

Queries are serialized to keep account load predictable. Measurements are fetched immediately after device metadata, before optional metadata and alarm exports. CSV decoding/parsing runs in a worker thread. Device, channel, assignment and status indexes are shared across entities and rebuilt once per refresh. Request-budget writes use a small separate store instead of repeatedly writing the entire metadata cache.

The client enforces bounded HTTP timeouts, a five-minute cooldown for HTTP 429, local quota protection, HTTPS storage-host checks, no redirects, and limits of 100 result files, 20 MiB per file and 100,000 rows per export. Exceeding a limit fails explicitly rather than accepting a partial result. Required measurement columns are validated. Failed domains are reported independently, allowing battery readings to remain available during a measurement-export failure.

Measurement values are already scaled by Testo. `channel_physical_unit_exponent` is not applied again. NaN, infinity and invalid values are never converted to zero. Sensor UUID **and channel number** form the measurement key. The newest sample wins, including an invalid newest sample; an older valid value is never substituted.

## Troubleshooting missing measurements

Open the logger's device page and inspect **data status**, sample time and the measurement attributes.

| Data status | Meaning | Next step |
|---|---|---|
| `ok` | A recent finite measurement is present | Inspect the corresponding measurement entity and dashboard selection |
| `api_error` | Measurement export failed or has not completed successfully | Read `measurement_error`; wait for the next poll, check quota or download diagnostics |
| `no_data` | Successful export, no matching sample for this channel | Check the probe and channel in Testo Cloud; unused channels are expected |
| `invalid_value` | Latest row is not a finite numeric value | Check probe errors in Testo Cloud |
| `stale` | Latest sample exceeds the configured age threshold | Check actual sample time and logger communication before changing the threshold |

Download diagnostics from **Settings → Devices & services → Testo Smart Connect → Download diagnostics**. They contain endpoint row counts, fetch times, safe errors, structural field names and local budget information, not the API key, signed URLs or raw device identifiers. In 0.1.0 the measurement row count was misleadingly zero because the raw history was deliberately discarded; 0.1.1 records the actual export count separately.

Battery readings alone prove that the status endpoint works; they do not prove that the measurement export succeeded. Do not publish raw diagnostic scripts/exports, API keys, Home Assistant storage files or signed download URLs in issues.

## Alarm semantics

Alarm events are grouped by `source_alarm_event_uuid` (falling back to `uuid`); the latest status change determines the observed event state. A later `Ok` resolves the corresponding observed alarm.

**The count is not a complete global alarm state.** An unresolved alarm that started outside the queried 24-hour window can be absent. Zero means no active alarm events observed in that window, not a guarantee of alarm-free equipment. Testo's native alarm system remains authoritative.

The separate threshold problem sensor performs an instantaneous comparison. Delay and hysteresis rules are exposed as attributes but are not simulated. Ambiguous assignments or multiple equivalent limit rules do not produce invented scalar limits.

## Automation example

Replace both entity/service placeholders with IDs from your own installation. The notification action requires the Home Assistant Companion App.

```yaml
alias: "Testo: stale measurement data"
triggers:
  - trigger: state
    entity_id: binary_sensor.REPLACE_WITH_DATA_STALE
    to: "on"
    for: "00:10:00"
actions:
  - action: notify.mobile_app_REPLACE_WITH_PHONE
    data:
      title: "Testo: measurement data unavailable"
      message: "The measurement site is no longer providing recent data."
mode: single
```

A state trigger does not cover every startup or unavailable-state scenario. Add startup/availability handling for your deployment; a Home Assistant restart resets pending `for` timers.

## Dashboard example

```yaml
type: entities
title: Cold storage
entities:
  - sensor.REPLACE_WITH_TEMPERATURE
  - sensor.REPLACE_WITH_SAMPLE_TIME
  - sensor.REPLACE_WITH_DATA_STATUS
  - sensor.REPLACE_WITH_BATTERY
  - binary_sensor.REPLACE_WITH_DATA_STALE
```

## Security and maintenance

The API key is stored in the Home Assistant config entry. Protect the host and backups. API credentials are sent only to the selected Testo API host, never to signed S3 downloads. Diagnostics and logged errors avoid credentials and response bodies. Private exports are not included in this repository.

To rotate a key, use the reauthentication flow when Home Assistant requests it; the replacement must belong to the same account and region. Removing the integration removes its private cache and budget store. Downloaded HACS files are removed separately in HACS. Recorder history follows Home Assistant retention settings.

Report reproducible issues with integration/HA versions, the affected data status, and sanitized diagnostics. See [SECURITY.md](SECURITY.md) for security reports and [CONTRIBUTING.md](CONTRIBUTING.md) for development.

## Development and validation

```bash
python -m pip install -r requirements-dev.txt
ruff check .
ruff format --check .
pytest -q
```

CI runs tests on Python 3.13, Ruff, Home Assistant hassfest and HACS validation. Release automation verifies the tag against the manifest version and builds the integration ZIP. Tests use synthetic data and actual Home Assistant classes. A private export is used only for local schema/replay checks and is never committed.

## Documentation and license

- [API mapping](docs/API.md)
- [Changelog](CHANGELOG.md)
- [Testo API reference](https://developers.testo.dev/smart-connect-api/api_reference/)
- [Testo API FAQ](https://developers.testo.dev/smart-connect-api/faq/)
- [Testo asynchronous API concepts](https://developers.testo.dev/smart-connect-api/concepts/)
- [Original community icon](docs/BRANDING.md)

MIT licensed. Testo trademarks remain the property of their respective owners.
