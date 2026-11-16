# API mapping and implementation notes

All six exports were verified with a private diagnostic capture. Only schema field names appear below. Private source files are not part of this repository.

## Transport

POST with `x-custom-api-key` starts an export; GET with request UUID polls for completion; signed S3 downloads receive no API headers. Explicit CSV, UTF-8 with optional BOM, all result files. POST-only monthly quota. No POST retry inside a failed query.

## Field inventory

### /v3/devices/properties

`tenant_uuid`, `customer_site`, `device_uuid`, `device_category`, `device_serial_no`, `device_model_code`, `device_firmware_version`, `device_supported_battery_types`, `device_display_name`, `device_is_active`, `device_communication_log_time`, `device_measuring_cycle`, `device_measuring_cycle_effective`, `device_is_ethernetprobe`, `device_is_powersuppliable`, `device_is_wirelessprobe`, `device_last_modified`, `sensor_uuid`, `sensor_serial_no`, `sensor_model_code`, `sensor_firmware_version`, `sensor_display_name`, `sensor_is_wired`, `sensor_is_radio`, `sensor_is_connected`, `sensor_measuring_cycle`, `sensor_measuring_cycle_effective`, `sensor_last_modified`, `channel_id`, `channel_no`, `channel_physical_unit`, `channel_physical_property_name`, `channel_physical_extension`, `channel_physical_unit_exponent`, `channel_attenuation`, `channel_is_external`, `channel_is_calibration_possible`, `channel_last_modified`, `equipment_uuid`, `equipment_parts_uuid`

### /v4/devices/status

`device_uuid`, `tenant_uuid`, `customer_site`, `serial_no`, `model_code`, `production_date`, `connection_type`, `radio_level_percent`, `battery_level_percent`, `battery_temperature`, `is_powersupply_on`, `last_communication_time`, `next_communication_time`, `status_time`, `processed_at`

### /v2/measurements

`uuid`, `sensor_uuid`, `channel_no`, `serial_no`, `model_code`, `tenant_uuid`, `customer_site`, `timestamp`, `timestamp_local`, `measurement`, `physical_property_name`, `physical_unit`, `physical_extension`, `processed_at`

### /v1/measuring-objects

`customer_uuid`, `measuring_object_uuid`, `product_family_id`, `customer_site`, `version_timestamp`, `measurement_alarm_configuration`, `back_reference`, `channel_assignments`, `valid_from`

### /v1/locations

`tenant_uuid`, `location_uuid`, `location_name`, `location_type`, `parent_location_type`, `location_subtype`, `valid_from`, `last_modified_at`

### /v3/alarms

`uuid`, `alarm_reason`, `alarm_status`, `last_status_change_time`, `alarm_condition_type`, `alarm_severity`, `alarm_time`, `alarm_time_local`, `alarm_value`, `physical_unit`, `physical_property_name`, `physical_extension`, `alarm_source_uuid`, `serial_no`, `tenant_uuid`, `customer_site`, `alarm_type`, `source_alarm_event_uuid`, `processed_at`

## Mapping limitations

- Channel identity is `(sensor_uuid, channel_no)`, device identity is `device_uuid`.
- `measurement` is already scaled. Unit exponent is metadata, not an instruction to multiply again.
- Measurement time uses UTC `timestamp`; local timestamps are display metadata.
- Status records choose newest `status_time`; absent booleans are unknown, not false.
- Measuring-object `channel_assignments` and `measurement_alarm_configuration` are JSON inside CSV cells.
- Assignments use sensor UUID plus physical property; ambiguous mappings are deliberately unresolved.
- Location names use `location_name`, not the `name` shown in some FAQ examples. No parent UUID was present.
- Equipment/composite back references are retained in cache but not guessed into a location.
- All exported columns remain in private metadata cache; selected scalar metrics become entities. No secret or customer metadata is included in public diagnostics.
- Alarm rows are reduced by source event identity and latest status change. The 24h window cannot certify globally active alarms.
- Deduplication for latest measurements is implicit in sensor/channel/time selection; no historical recorder import.

## Sources

- https://developers.testo.dev/smart-connect-api/faq/
- https://developers.testo.dev/smart-connect-api/api_reference/
- https://developers.testo.dev/smart-connect-api/concepts/

Documentation checked 2026-11-16. Older examples use status v3; this implementation uses the verified v4 endpoint.

## Version 0.1.1 request and diagnostics changes

The OpenAPI JSON was reviewed at `https://developers.testo.dev/smart-connect-api/api_reference/swagger.json`. It confirms all six endpoint versions used here. The time schema uses `date-time`; the implementation now emits UTC seconds with a `Z` suffix, matching the successful PowerShell capture. The specification does not establish that offsets are invalid, so this change is a compatibility measure, not proof of the live failure cause.

Shared lookup indexes are rebuilt once per coordinator refresh; CSV parsing runs outside the event loop. Measurement exports retain their actual row count separately from the latest-sample cache. Per-channel data-status entities distinguish API failure, missing samples, invalid samples, stale samples and valid current data. Raw measurements remain excluded from downloadable diagnostics.
