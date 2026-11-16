"""Pure data normalization; CSV values are strings, never implicitly truthy."""

from __future__ import annotations

import json
import math
from datetime import UTC, datetime


def number(value):
    try:
        result = float(value)
        return result if math.isfinite(result) else None
    except (TypeError, ValueError):
        return None


def boolean(value):
    if value is True or str(value).lower() == "true":
        return True
    if value is False or str(value).lower() == "false":
        return False
    return None


def timestamp(value):
    try:
        result = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
        return result.replace(tzinfo=UTC) if result.tzinfo is None else result.astimezone(UTC)
    except (TypeError, ValueError):
        return None


def nested(value, default):
    if isinstance(value, (list, dict)):
        return value
    try:
        return json.loads(value)
    except (ValueError, TypeError):
        return default


def channel_key(row):
    return f"{row.get('sensor_uuid', '')}:{row.get('channel_no', '')}"


def latest_measurements(rows, previous=None):
    """Use measurement time, not arrival order; keep channels distinct."""
    result = dict(previous or {})
    for row in rows:
        key = channel_key(row)
        dt = timestamp(row.get("timestamp"))
        old = timestamp(result.get(key, {}).get("timestamp"))
        if dt and (old is None or dt >= old):
            result[key] = row  # Invalid newest value must NOT resurrect an older valid value.
    return result


def latest_status(rows):
    result = {}
    for row in rows:
        key = row.get("device_uuid")
        if not key:
            continue
        dt = timestamp(row.get("status_time")) or datetime.min.replace(tzinfo=UTC)
        old = timestamp(result.get(key, {}).get("status_time"))
        if old is None or dt >= old:
            result[key] = row
    return result


def observed_alarms(rows):
    """Latest state per source event within the requested window, not global truth."""
    result = {}
    for row in rows:
        key = row.get("source_alarm_event_uuid") or row.get("uuid")
        dt = timestamp(row.get("last_status_change_time")) or timestamp(row.get("alarm_time"))
        old = result.get(key, {})
        old_dt = timestamp(old.get("last_status_change_time")) or timestamp(old.get("alarm_time"))
        if key and dt and (old_dt is None or dt >= old_dt):
            result[key] = row
    return list(result.values())


def assignment_map(properties, objects, locations):
    """Only resolve unambiguous channel assignments; preserve raw config locally."""
    names = {r.get("location_uuid"): r.get("location_name") for r in locations}
    result = {}
    for obj in sorted(objects, key=lambda r: str(r.get("version_timestamp", ""))):
        assignments = nested(obj.get("channel_assignments"), [])
        if not isinstance(assignments, list):
            continue
        for assignment in assignments:
            if not isinstance(assignment, dict):
                continue
            sensor = assignment.get("sensorChannel") or {}
            if not isinstance(sensor, dict):
                continue
            sid = sensor.get("sensorUuid")
            prop = str((sensor.get("physicalProperty") or {}).get("physicalValueId", "")).lower().removeprefix("pv_")
            candidates = [
                p
                for p in properties
                if p.get("sensor_uuid") == sid
                and (not prop or p.get("channel_physical_property_name", "").lower() == prop)
            ]
            if "channelNo" in sensor:
                candidates = [p for p in candidates if str(p.get("channel_no")) == str(sensor["channelNo"])]
            if len(candidates) != 1:
                continue  # Never guess between two temperature channels on one sensor.
            result[channel_key(candidates[0])] = {
                "name": names.get(obj.get("back_reference")),
                "configuration": nested(obj.get("measurement_alarm_configuration"), {}),
            }
    return result


def limits(assignment):
    """Expose all threshold rules; scalar thresholds only if unambiguous."""
    config = assignment.get("configuration") or {}
    if not isinstance(config, dict):
        config = {}
    rules = [
        r
        for group in (config.get("measurementAlarmConditionSet") or [])
        if isinstance(group, dict)
        for r in (group.get("measurementAlarmConditions") or [])
        if isinstance(r, dict)
    ]
    result = {"rules": rules}
    for label, kind in (("lower", "Lower limit"), ("upper", "Upper limit")):
        values = [number(r.get("limitValue")) for r in rules if r.get("measurementAlarmConditionTypeId") == kind]
        result[label] = values[0] if len(values) == 1 else None
    return result


CHANNEL_STATES = ("ok", "no_data", "stale", "invalid_value", "api_error")
LOGGER_STATES = ("ok", "partial", "no_data", "stale", "invalid_value", "api_error")


def measurement_state(sample, healthy, now, stale_minutes):
    """Do not confuse successful discovery with successful measurements."""
    if not healthy:
        return "api_error"
    if not sample:
        return "no_data"
    if number(sample.get("measurement")) is None:
        return "invalid_value"
    dt = timestamp(sample.get("timestamp"))
    if dt is None or (now - dt).total_seconds() > stale_minutes * 60:
        return "stale"
    return "ok"


def telemetry_indexes(properties, latest, alarms, healthy, now, stale_minutes):
    """Linear-time channel summaries and alarm lookup shared by every entity."""
    summaries = {}
    owners = {}
    for key, prop in properties.items():
        did = prop["device_uuid"]
        owners[did] = did
        owners[prop["sensor_uuid"]] = did
        summary = summaries.setdefault(
            did,
            {
                "channels_total": 0,
                "channels_reporting": 0,
                "channels_current": 0,
                "channels_missing": 0,
                "channels_stale": 0,
                "channels_invalid": 0,
                "last_measurement": None,
            },
        )
        sample = latest.get(key, {})
        # Classify cached data independently of API health; error remains explicit.
        state = measurement_state(sample, True, now, stale_minutes)
        summary["channels_total"] += 1
        summary["channels_reporting"] += bool(sample)
        summary["channels_current"] += state == "ok"
        summary["channels_missing"] += state == "no_data"
        summary["channels_stale"] += state == "stale"
        summary["channels_invalid"] += state == "invalid_value"
        dt = timestamp(sample.get("timestamp"))
        if dt and (summary["last_measurement"] is None or dt > summary["last_measurement"]):
            summary["last_measurement"] = dt
    for summary in summaries.values():
        if not healthy:
            state = "api_error"
        elif not summary["channels_reporting"]:
            state = "no_data"
        elif summary["channels_current"] == summary["channels_total"]:
            state = "ok"
        elif summary["channels_current"]:
            state = "partial"
        elif summary["channels_invalid"]:
            state = "invalid_value"
        else:
            state = "stale"
        summary["logger_status"] = state
    grouped = {did: [] for did in summaries}
    for alarm in observed_alarms(alarms):
        did = owners.get(alarm.get("alarm_source_uuid"))
        if did in grouped:
            grouped[did].append(alarm)
    return summaries, grouped
