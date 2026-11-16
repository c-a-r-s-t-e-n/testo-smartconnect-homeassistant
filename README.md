![Testo Smart Connect — Home Assistant community integration](https://raw.githubusercontent.com/c-a-r-s-t-e-n/testo-smartconnect-homeassistant/main/docs/assets/header.png)

# Testo Smart Connect for Home Assistant

[![Validate](https://github.com/c-a-r-s-t-e-n/testo-smartconnect-homeassistant/actions/workflows/validate.yml/badge.svg)](https://github.com/c-a-r-s-t-e-n/testo-smartconnect-homeassistant/actions/workflows/validate.yml)
[![Release](https://img.shields.io/github/v/release/c-a-r-s-t-e-n/testo-smartconnect-homeassistant)](https://github.com/c-a-r-s-t-e-n/testo-smartconnect-homeassistant/releases/latest)
[![License: MIT](https://img.shields.io/badge/license-MIT-blue.svg)](LICENSE)

**Monitor your Testo loggers, understand missing readings, and build your own Home Assistant automations.** This independent community integration connects to the official Testo Smart Connect API. It works in an existing Home Assistant installation without a VPN, local gateway or YAML configuration.

| Measurements | Logger health | Alarm insight |
|---|---|---|
| Temperature, humidity and other exported physical values | Battery, radio quality, power and communication times | Configured thresholds and observed alarm events |
| Sample time, age and per-channel data status | Clear explanations for missing or partial data | Immediate threshold comparisons for automations |
| Automatic device and channel discovery | Channel counts and latest logger measurement | Explicit distinction from Testo's native alarm system |

## Requirements

- Home Assistant **2025.3 or newer**. The built-in **Marketplace** is available in Home Assistant 2026.11 and newer; use HACS on supported older installations.
- Testo Smart Connect account, an active **API add-on**, and an API key.
- Outbound HTTPS access to the regional Testo API and its signed S3 export storage.

This is a read-only custom integration, not a Supervisor app. It is independently maintained and is not affiliated with Testo. Keep Testo's own alarms and compliance records enabled for their intended purpose.

<!-- ha-marketplace:exclude-start -->
## Installation

1. Add `https://github.com/c-a-r-s-t-e-n/testo-smartconnect-homeassistant` to the Marketplace's custom repositories, type **Integration**. On older Home Assistant versions, use **HACS → Custom repositories**.
2. Install **Testo Smart Connect**, selecting the latest release.
3. Restart Home Assistant completely.
4. Open **Settings → Devices & services → Add integration → Testo Smart Connect**.

For a manual installation, copy `custom_components/testo_smartconnect` to `/config/custom_components/testo_smartconnect`, restart and add the integration.

[Releases](https://github.com/c-a-r-s-t-e-n/testo-smartconnect-homeassistant/releases) · [Report an issue](https://github.com/c-a-r-s-t-e-n/testo-smartconnect-homeassistant/issues/new/choose)
<!-- ha-marketplace:exclude-end -->

## Configuration

Enter the API key and select **Europe (EU)**, **Americas (AM)** or **Asia Pacific (AP)** to match your Testo account. The setup dialog links to [Testo Cloud](https://www.eu.smartconnect.testo.com/). Allow several minutes for initial synchronization.

Under **Configure**, adjust the measurement polling interval (10–60 minutes) and stale-data threshold (15–1,440 minutes; default 60). Use a threshold compatible with the logger's actual transmission interval. Supported setup, region labels and measurement-availability states are translated into English and German.

## What you get

### Per logger

- **Measurement availability**: a visible, translated status that distinguishes complete, partial, missing, stale or invalid data from an API request failure.
- **Discovered channels**, **channels with samples**, **channels with current data**, and **latest measurement**.
- Battery percentage, radio quality, reported external power, connection type and communication timestamps.
- Firmware, measurement interval, communication interval, observed active alarm count and last observed alarm time.
- Optional diagnostics: battery temperature, next communication, status timestamp and **logger active reported**.

### Per channel

- Measurement, actual sample time, sample age and translated data status.
- Stale-data and invalid-value problem sensors.
- Lower/upper limits and an instantaneous outside-limits problem sensor.
- Optional **probe connected reported** diagnostic.
- Attributes for sensor model/firmware, reported measuring interval, calibration capability, physical property/extension and cloud processing timestamp, where provided by the API.

Optional diagnostics are disabled by default to keep the entity list focused. Enable them from the device's entity list. Existing entity unique IDs remain stable across updates. Home Assistant assigns entity IDs, so copy the actual IDs from your installation when building dashboards or automations.

## A logger is detected but has no readings

Device discovery and measurement delivery are separate. A logger can be correctly registered in Testo's API, with a working battery/status export, while its probes provide no recent measurements.

| Availability state | Meaning and next step |
|---|---|
| Current measurements available | All discovered channels have recent, finite readings. |
| Partial data | Some channels report current readings; others are unused, missing, stale or invalid. Check the per-channel data status. |
| Detected in API — no measurements received | The device was discovered successfully, but there are no matching samples in the retained measurement window. Check probes and Testo Cloud. This does **not** mean authentication failed. |
| Detected — measurements are stale | Samples exist but exceed the configured age threshold. Check the last measurement and logger transmission times. |
| Detected — invalid measurements | No current valid channels remain and at least one latest sample is invalid. Check probe faults in Testo Cloud. |
| Detected — measurement request failed | Measurement retrieval failed. Inspect `measurement_error` and the last successful fetch timestamp. |

The logger status exposes counts of missing, stale and invalid channels. Definitions for unused channels are retained rather than silently hidden. A reported probe connection or logger-active flag is metadata, not proof of current communication. These flags update with the daily properties export.

Download sanitized diagnostics from the integration entry for endpoint errors, returned row counts, fetch times and budget information. Share those with an issue; never publish API keys, raw exports, Home Assistant storage files or signed download URLs.

## Data coverage and supported devices

The integration uses all six official Smart Connect export domains:

| Endpoint | Purpose |
|---|---|
| `/v3/devices/properties` | Devices, sensors, channels, units, capabilities and intervals |
| `/v4/devices/status` | Battery, radio quality, power and communication |
| `/v2/measurements` | Latest physical value per sensor and channel |
| `/v1/measuring-objects` | Channel assignments and configured threshold rules |
| `/v1/locations` | Measurement-site names |
| `/v3/alarms` | Alarm events within the requested time window |

Discovery is dynamic. Verified export schemas include logger model codes `0572 2031`, `0572 2032`, `0572 2033` and `0572 2035`. EU has been checked against an actual account export; AM/AP hosts follow the documented API but have not been verified with live accounts. This integration does not support legacy Saveris APIs, Polarfoxx or mobile instruments whose data is absent from Smart Connect.

The API's physical measurement is already scaled; the unit exponent is not applied twice. Missing or invalid values are never converted to zero. Sensor UUID **and channel number** identify readings. [Complete field inventory and mapping rules](docs/API.md).

## Refresh intervals and API quota

| Data | Default interval |
|---|---:|
| Measurements, all loggers in one export | 10 minutes |
| Device status and alarm events | 30 minutes each |
| Devices, measuring objects and locations | 24 hours each |

The defaults use approximately **7,533 POST requests per 31-day month**, plus setup and recovery. Testo documents **10,000 POST requests per account per month**; GET polling and downloads do not count. A persisted local counter stops new exports at 9,500. Other API clients and setup validation are not included in this local count.

Longer measurement intervals also delay the shared scheduler's other checks. Freshness depends on logger transmission and cloud processing; this is not a live stream. Initial/recovery queries cover up to 24 hours, then overlap successful retrieval by one hour. Only the latest sample per channel is retained; historical data is not backfilled into Recorder.

## Performance and reliability

- One shared request per data domain, with no per-logger API polling.
- Bounded asynchronous export polling; pending jobs resume and expired results recover on a later refresh.
- CSV parsing outside the event loop, bounded file/row limits and required-field validation.
- Shared lookup indexes rebuilt only when their source metadata changes; logger summaries and alarm grouping computed once per refresh.
- Lightweight persistent quota reservations; full cache writes only after successful retrieval.
- Independent endpoint errors, a rate-limit cooldown, protected signed downloads and explicit stale-data handling.

[Architecture and operational details](docs/API.md) · [Troubleshooting](docs/TROUBLESHOOTING.md)

## Alarm behavior

Observed alarms use a rolling **24-hour event window**, grouped by source event and latest status change. A later `Ok` resolves the corresponding observed event. The count cannot represent every globally active alarm: an older unresolved event may be absent. Zero is not a guarantee of alarm-free equipment.

The threshold problem sensor compares a current reading immediately. Testo delay/hysteresis rules are exposed as attributes but are not simulated. Ambiguous assignments do not produce invented scalar limits. Testo's native alarm delivery remains authoritative.

## Updates and removal

Install updates through the Marketplace or HACS, then restart Home Assistant. Keep the integration entry to preserve credentials and entity registry customization. API-key reauthentication verifies the same account and region.

Removing the integration removes its private cache and local budget store; uninstall downloaded files separately in the Marketplace/HACS. Recorder history follows Home Assistant retention settings. Protect the Home Assistant host and backups because they contain the API key.

<!-- ha-marketplace:exclude-start -->
## Development and support

CI tests both the minimum supported Home Assistant baseline and Home Assistant 2026.11.2, alongside Ruff, Home Assistant hassfest, HACS validation and release packaging. Tests exercise API transport, recovery, mapping, configuration and Home Assistant entities using synthetic data. Passing CI does not certify every device, account or network; report runtime problems with sanitized diagnostics.

[Contributing](CONTRIBUTING.md) · [Security](SECURITY.md) · [Changelog](CHANGELOG.md) · [Brand assets](docs/BRANDING.md)

MIT licensed. Testo trademarks remain the property of their respective owners.
<!-- ha-marketplace:exclude-end -->
