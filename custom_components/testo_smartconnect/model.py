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
            sensor = assignment.get("sensorChannel", {})
            sid = sensor.get("sensorUuid")
            prop = str(sensor.get("physicalProperty", {}).get("physicalValueId", "")).lower().removeprefix("pv_")
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
    config = assignment.get("configuration", {})
    rules = [
        r
        for group in config.get("measurementAlarmConditionSet", [])
        for r in group.get("measurementAlarmConditions", [])
    ]
    result = {"rules": rules}
    for label, kind in (("lower", "Lower limit"), ("upper", "Upper limit")):
        values = [number(r.get("limitValue")) for r in rules if r.get("measurementAlarmConditionTypeId") == kind]
        result[label] = values[0] if len(values) == 1 else None
    return result
