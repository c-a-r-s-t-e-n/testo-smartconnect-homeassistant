# Troubleshooting

## Missing measurements

1. Open the logger device and inspect **Measurement availability** and channel counts.
2. Open the affected channel's **Data status**, sample time and sample age.
3. For API errors, inspect `measurement_error` and `last_successful_measurement_fetch`.
4. Compare the same probe in Testo Cloud. A successful properties/status export does not imply a successful measurement export.
5. Download the integration's sanitized diagnostics and include them with your integration version, Home Assistant version and a concise reproduction.

`no_data` describes the retained query window, not the logger's entire lifetime. `partial` can be normal for unused external probe ports. Do not repeatedly delete and recreate the integration: setup consumes requests and removing the entry removes its locally tracked budget.

Status explanations remain visible for discovered devices even when all exports fail. Unknown boolean values remain unknown rather than false. Logger-active/probe-connected properties are refreshed daily; they are not online/offline detection.

## Missing Marketplace icon

This repository ships light/dark standard/high-resolution icons and wordmarks in `custom_components/testo_smartconnect/brand/`. The README header uses a direct public repository image, independently of the Marketplace's icon service.

On Home Assistant versions supporting local brands, installed integration images are served through the brands API. Install/update and restart Home Assistant before testing the icon; refresh the browser afterwards. Before installation, Marketplace uses a central catalog/CDN service. A custom repository that is not indexed there may still show a placeholder. There is no supported `icon_url` override in `hacs.json`; this project does not alter Home Assistant internals to bypass that service.

Older HACS releases can display a placeholder even when Home Assistant shows the local icon correctly. Brand assets are included in the release ZIP; repository-only modifications cannot guarantee external CDN behavior.

References:
- https://contributors.home-assistant.io/marketplace/reference/repository-structure/
- https://github.com/home-assistant/brands#marketplace-icons
- https://developers.home-assistant.io/blog/2026/02/24/brands-proxy-api/

## Alarm interpretation

The alarm count covers observed events in a 24-hour window. Use Testo's native alarms for authoritative alarm delivery. Threshold sensors perform an immediate comparison and do not reproduce Testo's delay or hysteresis state machine.

## Automation example

Use your own entity and Companion App service IDs. Also account for startup and unavailable states in production: state triggers do not cover every restart scenario.

```yaml
alias: "Testo: missing measurements"
triggers:
  - trigger: state
    entity_id: sensor.REPLACE_WITH_LOGGER_STATUS
    to: "no_data"
    for: "00:20:00"
actions:
  - action: notify.mobile_app_REPLACE_WITH_PHONE
    data:
      title: "Testo: no measurements"
      message: "The logger is detected, but no measurement data is available."
mode: single
```

Translations affect displayed labels; automation states remain `ok`, `partial`, `no_data`, `stale`, `invalid_value` and `api_error`.
