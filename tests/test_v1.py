"""Logger explanations, metadata semantics and shared-work regression coverage."""

from datetime import UTC, datetime, timedelta
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

import pytest
from homeassistant.core import HomeAssistant

from custom_components.testo_smartconnect.binary_sensor import TestoBinary as Binary
from custom_components.testo_smartconnect.coordinator import TestoCoordinator as Coordinator
from custom_components.testo_smartconnect.entity import build_context
from custom_components.testo_smartconnect.model import telemetry_indexes
from custom_components.testo_smartconnect.sensor import TestoSensor as Sensor

NOW = datetime(2026, 11, 16, 20, 0, tzinfo=UTC)
PROPS = {f"s:{i}": {"device_uuid": "d", "sensor_uuid": "s", "channel_no": str(i)} for i in range(2)}


def sample(value="2.9", age=0):
    return {"timestamp": (NOW - timedelta(minutes=age)).isoformat(), "measurement": value}


@pytest.mark.parametrize(
    ("latest", "healthy", "expected"),
    [
        ({}, True, "no_data"),
        ({}, False, "api_error"),
        ({"s:0": sample()}, True, "partial"),
        ({"s:0": sample(), "s:1": sample()}, True, "ok"),
        ({"s:0": sample(age=61)}, True, "stale"),
        ({"s:0": sample("NaN")}, True, "invalid_value"),
        ({"s:0": sample(), "s:1": sample()}, False, "api_error"),
    ],
)
def test_logger_state_distinguishes_discovery_from_measurements(latest, healthy, expected):
    summaries, _ = telemetry_indexes(PROPS, latest, [], healthy, NOW, 60)
    assert summaries["d"]["logger_status"] == expected
    assert summaries["d"]["channels_total"] == 2
    assert summaries["d"]["channels_reporting"] == len(latest)


def test_counts_and_latest_time_remain_explicit():
    summary = telemetry_indexes(PROPS, {"s:0": sample(), "s:1": sample(age=70)}, [], True, NOW, 60)[0]["d"]
    assert summary["channels_current"] == 1
    assert summary["channels_stale"] == 1
    assert summary["channels_missing"] == 0
    assert summary["last_measurement"] == NOW


def test_alarm_index_groups_sensor_and_logger_sources_once():
    events = [
        {"uuid": "a", "alarm_source_uuid": "s", "alarm_time": NOW.isoformat(), "alarm_status": "Alarm"},
        {"uuid": "b", "alarm_source_uuid": "d", "alarm_time": NOW.isoformat(), "alarm_status": "Alarm"},
        {"uuid": "c", "alarm_source_uuid": "other", "alarm_time": NOW.isoformat(), "alarm_status": "Alarm"},
    ]
    _, grouped = telemetry_indexes(PROPS, {}, events, True, NOW, 60)
    assert [a["uuid"] for a in grouped["d"]] == ["a", "b"]


def fake_coordinator():
    cache = {"properties": list(PROPS.values())}
    summaries, alarms = telemetry_indexes(PROPS, {}, [], False, NOW, 60)
    return SimpleNamespace(
        entry=SimpleNamespace(unique_id="account", options={}, data={"region": "eu"}),
        cache=cache,
        indexes=build_context(cache),
        summaries=summaries,
        alarms_by_device=alarms,
        latest={},
        last_update_success=False,
        healthy=lambda k: True,
        fetched={},
        errors={"measurements": "HTTP 400"},
    )


def test_logger_explanation_survives_failed_update_and_id_is_stable():
    c = fake_coordinator()
    status = Sensor(c, "d", None, "logger_status", "Availability")
    assert status.available
    assert status.native_value == "api_error"
    assert status.extra_state_attributes["discovered_in_api"] is True
    assert status.extra_state_attributes["measurement_error"] == "HTTP 400"
    assert Sensor(c, "d", "s:0", "measurement", "Temperature").unique_id == "account_d_s:0_measurement"


def test_missing_metadata_is_unknown_not_false():
    c = fake_coordinator()
    assert Binary(c, "d", None, "active", "Active").is_on is None
    assert Binary(c, "d", "s:0", "connected", "Probe connected").is_on is None
    c.indexes[0]["s:0"]["sensor_is_connected"] = "false"
    assert Binary(c, "d", "s:0", "connected", "Probe connected").is_on is False


@pytest.mark.asyncio
async def test_measurements_only_refresh_reuses_metadata_and_noop_skips_storage(tmp_path):
    entry = SimpleNamespace(entry_id="performance", options={}, data={})
    entry.async_on_unload = lambda fn: None
    c = Coordinator(HomeAssistant(str(tmp_path)), entry)
    c.cache = {"properties": list(PROPS.values())}
    c.indexes = build_context(c.cache)
    c.save = AsyncMock()
    c.fetched = {k: datetime.now(UTC).isoformat() for k in ("properties", "objects", "locations", "status", "alarms")}
    c.api = SimpleNamespace(query=AsyncMock(return_value=[]))
    indexes = c.indexes
    with patch("custom_components.testo_smartconnect.coordinator.build_context") as build:
        await c._async_update_data()
        build.assert_not_called()
        assert c.indexes is indexes
        c.save.assert_awaited_once()
        c.save.reset_mock()
        c.api.query.reset_mock()
        await c._async_update_data()
        c.save.assert_not_awaited()
        c.api.query.assert_not_awaited()


def test_sensor_reads_reuse_alarm_index():
    c = fake_coordinator()
    c.alarms_by_device = {"d": [{"alarm_status": "Alarm"}]}
    entity = Sensor(c, "d", None, "observed_alarms", "Alarms")
    with patch("custom_components.testo_smartconnect.sensor.observed_alarms") as fold:
        assert entity.native_value == 1
        assert entity.device_alarms() is c.alarms_by_device["d"]
        fold.assert_not_called()
