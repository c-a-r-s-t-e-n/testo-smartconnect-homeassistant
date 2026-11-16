"""Regression tests for the reported missing measurements and recovery paths."""

import json
from datetime import UTC, datetime, timedelta
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

import pytest
from homeassistant.core import HomeAssistant
from test_api import Response, Session

from custom_components.testo_smartconnect.api import ApiError, ExpiredResultError, api_datetime, safe_download_url
from custom_components.testo_smartconnect.api import TestoApi as ApiClient
from custom_components.testo_smartconnect.config_flow import user_schema
from custom_components.testo_smartconnect.coordinator import TestoCoordinator as Coordinator
from custom_components.testo_smartconnect.entity import context
from custom_components.testo_smartconnect.model import assignment_map, limits
from custom_components.testo_smartconnect.sensor import TestoSensor as Sensor

UUID = "00000000-0000-0000-0000-000000000001"
URL = "https://tds-eu-p-data-storage-query-results.s3.amazonaws.com/test.csv"


def client_responses(csv):
    return Session(
        [Response({"request_uuid": UUID}), Response({"status": "Completed", "data_urls": [URL]}), Response(csv)]
    )


@pytest.mark.parametrize(
    ("value", "expected"),
    [
        ("2026-11-16T21:30:00.123456+01:00", "2026-11-16T20:30:00Z"),
        ("2026-11-16T20:30:00Z", "2026-11-16T20:30:00Z"),
    ],
)
def test_export_time_format(value, expected):
    assert api_datetime(value) == expected


@pytest.mark.asyncio
async def test_time_filter_body_and_validation_before_quota_reservation():
    session = client_responses(b"sensor_uuid,channel_no,timestamp,measurement\n")
    api = ApiClient(session, "secret")
    with patch("asyncio.sleep", new=AsyncMock()):
        await api.query("measurements", "2026-11-16T19:00:00.111+00:00", "2026-11-16T21:00:00+01:00")
    body = session.calls[0][2]["json"]
    assert body["date_time_from"] == "2026-11-16T19:00:00Z"
    assert body["date_time_until"] == "2026-11-16T20:00:00Z"
    with pytest.raises(ApiError, match="time range"):
        await api.query("measurements", "not-a-time")
    assert api.budget["posts"] == 1


@pytest.mark.asyncio
async def test_cooldown_does_not_consume_local_budget():
    api = ApiClient(Session([Response({}, 429)]), "secret")
    with pytest.raises(ApiError):
        await api.query("properties")
    with pytest.raises(ApiError, match="cooldown"):
        await api.query("status")
    assert api.budget["posts"] == 1


@pytest.mark.asyncio
async def test_expired_storage_does_not_trap_pending_job():
    session = Session(
        [
            Response({"request_uuid": UUID}),
            Response({"status": "Completed", "data_urls": [URL]}),
            Response(b"expired", 403),
            Response({"request_uuid": UUID}),
            Response({"status": "Completed", "data_urls": []}),
        ]
    )
    api = ApiClient(session, "secret")
    with patch("asyncio.sleep", new=AsyncMock()):
        with pytest.raises(ExpiredResultError):
            await api.query("measurements")
        assert not api.pending
        assert await api.query("measurements") == []
    assert api.budget["posts"] == 2


@pytest.mark.asyncio
async def test_required_measurement_columns_are_checked():
    api = ApiClient(client_responses(b"sensor_uuid,measurement\ns,2.9\n"), "secret")
    with patch("asyncio.sleep", new=AsyncMock()), pytest.raises(ApiError, match="required columns"):
        await api.query("measurements")


def test_invalid_storage_port_is_safe():
    assert not safe_download_url("https://tds-eu.s3.amazonaws.com:invalid/file")


def test_nullable_nested_configuration():
    assert limits({"configuration": None}) == {"rules": [], "lower": None, "upper": None}
    assert (
        limits({"configuration": {"measurementAlarmConditionSet": [None, {"measurementAlarmConditions": None}]}})[
            "rules"
        ]
        == []
    )
    assert assignment_map([], [{"channel_assignments": json.dumps([None, {"sensorChannel": None}])}], []) == {}


def test_readable_region_selector_keeps_stored_region_codes():
    schema = user_schema()
    region = next(v for k, v in schema.schema.items() if str(k) == "region")
    assert region.config["translation_key"] == "region"
    assert region.config["options"] == ["eu", "am", "ap"]
    assert region.config["mode"] == "dropdown"


@pytest.mark.asyncio
async def test_csv_to_coordinator_to_measurement_and_shared_indexes(tmp_path):
    now = datetime.now(UTC)
    stamp = now.strftime("%Y-%m-%dT%H:%M:%SZ")
    session = client_responses(
        f"sensor_uuid,channel_no,timestamp,measurement,physical_unit\ns,0,{stamp},2.9,°C\ns,1,{stamp},-18.2,°C\n".encode()
    )
    api = ApiClient(session, "secret")
    entry = SimpleNamespace(
        entry_id="test", unique_id="synthetic", options={}, data={"region": "eu", "api_key": "secret"}
    )
    entry.async_on_unload = lambda fn: None
    c = Coordinator(HomeAssistant(str(tmp_path)), entry)
    c.save = AsyncMock()
    props = [
        {"device_uuid": "d", "sensor_uuid": "s", "channel_no": str(i), "channel_physical_property_name": "Temperature"}
        for i in range(3)
    ]

    async def query(kind, *args):
        if kind == "properties":
            return props
        if kind == "measurements":
            return await api.query(kind, *args)
        return []

    c.api = SimpleNamespace(query=AsyncMock(side_effect=query))
    with patch("asyncio.sleep", new=AsyncMock()):
        await c._async_update_data()
    c.last_update_success = True
    assert c.row_counts["measurements"] == 2
    assert c.cache["measurements"] == []
    assert context(c) is context(c)
    for key, expected in [("s:0", 2.9), ("s:1", -18.2)]:
        e = Sensor(c, "d", key, "measurement", "Temperature")
        assert e.available
        assert e.native_value == expected
        assert e.data_status == "ok"
    missing = Sensor(c, "d", "s:2", "data_status", "Data status")
    assert missing.available
    assert missing.native_value == "no_data"
    c.errors["measurements"] = "HTTP 400"
    assert missing.native_value == "api_error"
    assert missing.extra_state_attributes["measurement_error"] == "HTTP 400"
    c.errors.clear()
    c.latest["s:0"]["timestamp"] = (now - timedelta(hours=2)).isoformat()
    assert Sensor(c, "d", "s:0", "data_status", "Status").native_value == "stale"
    c.latest["s:1"]["measurement"] = "NaN"
    assert Sensor(c, "d", "s:1", "data_status", "Status").native_value == "invalid_value"


@pytest.mark.asyncio
async def test_empty_history_keeps_full_recovery_window(tmp_path):
    entry = SimpleNamespace(entry_id="test", options={}, data={})
    entry.async_on_unload = lambda fn: None
    c = Coordinator(HomeAssistant(str(tmp_path)), entry)
    c.save = AsyncMock()
    c.cache["properties"] = [{"device_uuid": "d", "sensor_uuid": "s", "channel_no": "0"}]
    c.fetched = {k: datetime.now(UTC).isoformat() for k in ("properties", "objects", "locations", "status", "alarms")}
    c.fetched["measurements"] = (datetime.now(UTC) - timedelta(minutes=11)).isoformat()
    c.api = SimpleNamespace(query=AsyncMock(return_value=[]))
    await c._async_update_data()
    kind, start, end = c.api.query.call_args.args
    assert kind == "measurements"
    assert datetime.fromisoformat(end) - datetime.fromisoformat(start) == timedelta(hours=24)
