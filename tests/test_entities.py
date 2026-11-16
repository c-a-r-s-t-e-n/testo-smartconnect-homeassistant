"""Behavior against real Home Assistant entity classes with synthetic data."""

from datetime import UTC, datetime, timedelta
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock

import pytest
from homeassistant.core import HomeAssistant

from custom_components.testo_smartconnect.binary_sensor import TestoBinary as ProblemSensor
from custom_components.testo_smartconnect.sensor import TestoSensor as MeasurementSensor


def coordinator():
    now = datetime.now(UTC)
    p = {
        "device_uuid": "device",
        "device_display_name": "Synthetic logger",
        "sensor_uuid": "sensor",
        "channel_no": "0",
        "device_model_code": "test",
        "channel_physical_property_name": "Temperature",
        "channel_physical_unit": "°C",
        "channel_physical_unit_exponent": "-1",
    }
    c = MagicMock()
    c.entry = SimpleNamespace(unique_id="account", data={"region": "eu"}, options={})
    c.cache = {
        "properties": [p],
        "status": [{"device_uuid": "device", "battery_level_percent": "0", "is_powersupply_on": ""}],
        "objects": [],
        "locations": [],
        "alarms": [],
    }
    c.latest = {"sensor:0": {"timestamp": now.isoformat(), "measurement": "2.9", "physical_unit": "°C"}}
    c.fetched = {"status": now.isoformat()}
    c.last_update_success = True
    c.healthy = lambda kind: True
    return c


def test_measurement_not_scaled_and_stale_unavailable():
    c = coordinator()
    e = MeasurementSensor(c, "device", "sensor:0", "measurement", "Temperature")
    assert e.native_value == 2.9
    assert e.available
    c.latest["sensor:0"]["timestamp"] = (datetime.now(UTC) - timedelta(hours=2)).isoformat()
    assert not e.available
    assert ProblemSensor(c, "device", "sensor:0", "stale", "Stale").is_on


def test_zero_battery_is_not_missing_and_empty_power_is_unknown():
    c = coordinator()
    assert MeasurementSensor(c, "device", None, "battery_level_percent", "Battery").native_value == 0
    assert ProblemSensor(c, "device", None, "power", "Power").is_on is None


def test_invalid_measurement_replaces_old_number():
    c = coordinator()
    c.latest["sensor:0"]["measurement"] = "NaN"
    e = MeasurementSensor(c, "device", "sensor:0", "measurement", "Temperature")
    assert e.native_value is None
    assert not e.available
    assert ProblemSensor(c, "device", "sensor:0", "invalid", "Invalid").is_on


def test_missing_limits_are_unknown():
    c = coordinator()
    assert ProblemSensor(c, "device", "sensor:0", "limit", "Limit").is_on is None


@pytest.mark.asyncio
async def test_discovery_adds_new_channels_once():
    from custom_components.testo_smartconnect.sensor import async_setup_entry

    c = coordinator()
    callbacks = []
    c.async_add_listener.side_effect = lambda fn: callbacks.append(fn) or (lambda: None)
    entry = SimpleNamespace(runtime_data=c, async_on_unload=lambda fn: None)
    add = MagicMock()
    await async_setup_entry(None, entry, add)
    first_count = len(add.call_args.args[0])
    callbacks[0]()
    assert add.call_count == 1
    c.cache["properties"].append(dict(c.cache["properties"][0], channel_no="1"))
    callbacks[0]()
    assert add.call_count == 2
    assert len(add.call_args.args[0]) == 6
    assert first_count > 5


@pytest.mark.asyncio
async def test_coordinator_schedule_and_partial_failure(tmp_path):
    from custom_components.testo_smartconnect.api import ApiError
    from custom_components.testo_smartconnect.coordinator import TestoCoordinator

    hass = HomeAssistant(str(tmp_path))
    entry = SimpleNamespace(entry_id="test", options={}, data={"api_key": "synthetic", "region": "eu"})
    entry.async_on_unload = lambda fn: None
    c = TestoCoordinator(hass, entry)
    c.save = AsyncMock()
    c.api = SimpleNamespace(query=AsyncMock())

    async def query(kind, *args):
        if kind == "properties":
            return coordinator().cache["properties"]
        return []

    c.api.query.side_effect = query
    await c._async_update_data()
    assert c.api.query.await_count == 6
    c.api.query.reset_mock()
    await c._async_update_data()
    assert c.api.query.await_count == 0
    c.fetched["measurements"] = (datetime.now(UTC) - timedelta(minutes=11)).isoformat()
    c.api.query.side_effect = ApiError("Synthetic failure")
    data = await c._async_update_data()
    assert "measurements" in data["errors"]
    assert c.healthy("status")
    assert not c.healthy("measurements")


@pytest.mark.asyncio
async def test_diagnostics_never_include_raw_identifiers_or_key():
    from custom_components.testo_smartconnect.diagnostics import async_get_config_entry_diagnostics

    c = coordinator()
    c.errors = {}
    c.row_counts = {}
    c.budget = {"posts": 6}
    entry = SimpleNamespace(runtime_data=c, data={"region": "eu", "api_key": "private-key"}, options={})
    result = await async_get_config_entry_diagnostics(None, entry)
    assert "private-key" not in str(result)
    assert "Synthetic logger" not in str(result)
