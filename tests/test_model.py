"""Synthetic fixtures only; no customer exports are committed."""

from custom_components.testo_smartconnect.model import (
    assignment_map,
    boolean,
    latest_measurements,
    latest_status,
    limits,
    number,
    observed_alarms,
)


def test_csv_boolean_and_nonfinite_values():
    assert boolean("false") is False
    assert boolean("") is None
    assert boolean("true") is True
    for value in ("", "NaN", "inf", "-inf", None, "Error"):
        assert number(value) is None
    assert number("-19.095398") == -19.095398


def test_channels_and_time_order_and_invalid_newest():
    rows = [
        {"sensor_uuid": "s", "channel_no": "0", "timestamp": "2026-01-01T12:00:00Z", "measurement": "2"},
        {"sensor_uuid": "s", "channel_no": "1", "timestamp": "2026-01-01T12:00:00Z", "measurement": "50"},
        {"sensor_uuid": "s", "channel_no": "0", "timestamp": "2026-01-01T11:00:00Z", "measurement": "9"},
    ]
    result = latest_measurements(rows + rows)
    assert len(result) == 2
    assert result["s:0"]["measurement"] == "2"
    result = latest_measurements([dict(rows[0], timestamp="2026-01-01T13:00:00Z", measurement="NaN")], result)
    assert number(result["s:0"]["measurement"]) is None


def test_latest_device_status():
    rows = [
        {"device_uuid": "d", "status_time": "2026-01-01T12:00:00Z", "battery_level_percent": "60"},
        {"device_uuid": "d", "status_time": "2026-01-01T11:00:00Z", "battery_level_percent": "90"},
    ]
    assert latest_status(rows)["d"]["battery_level_percent"] == "60"


def test_alarm_resolution_uses_event_identity_and_status_time():
    event = {"source_alarm_event_uuid": "event", "alarm_source_uuid": "sensor"}
    rows = [
        dict(event, uuid="new", alarm_status="Ok", last_status_change_time="2026-01-01T12:00:00Z"),
        dict(event, uuid="old", alarm_status="Alarm", last_status_change_time="2026-01-01T11:00:00Z"),
    ]
    assert observed_alarms(rows)[0]["alarm_status"] == "Ok"
    assert len(observed_alarms(rows + rows)) == 1


def test_assignment_refuses_ambiguous_temperature_channels():
    prop = {"sensor_uuid": "sensor", "channel_no": "0", "channel_physical_property_name": "Temperature"}
    obj = {
        "channel_assignments": [
            {"sensorChannel": {"sensorUuid": "sensor", "physicalProperty": {"physicalValueId": "PV_TEMPERATURE"}}}
        ],
        "back_reference": "location",
    }
    locations = [{"location_uuid": "location", "location_name": "Synthetic cold room"}]
    assert assignment_map([prop], [obj], locations)["sensor:0"]["name"] == "Synthetic cold room"
    assert assignment_map([prop, dict(prop, channel_no="2")], [obj], locations) == {}


def test_limits_preserve_delay_hysteresis_and_reject_ambiguous_scalars():
    rule = {"measurementAlarmConditionTypeId": "Upper limit", "limitValue": 8, "delay": 60000, "limitHysteresis": 0.5}
    assignment = {"configuration": {"measurementAlarmConditionSet": [{"measurementAlarmConditions": [rule]}]}}
    assert limits(assignment)["upper"] == 8
    assert limits(assignment)["rules"][0]["delay"] == 60000
    assignment["configuration"]["measurementAlarmConditionSet"][0]["measurementAlarmConditions"].append(
        dict(rule, limitValue=10)
    )
    assert limits(assignment)["upper"] is None
