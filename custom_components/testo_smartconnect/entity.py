"""Shared device/channel lookup and availability rules."""

from datetime import UTC, datetime

from homeassistant.helpers.entity import DeviceInfo
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import CONF_STALE, DEFAULT_STALE, DOMAIN
from .model import assignment_map, channel_key, latest_status, telemetry_indexes, timestamp


def build_context(cache):
    props = {channel_key(r): r for r in cache.get("properties", [])}
    devices = {r["device_uuid"]: r for r in props.values()}
    assignments = assignment_map(list(props.values()), cache.get("objects", []), cache.get("locations", []))
    return props, devices, assignments, latest_status(cache.get("status", []))


def context(coordinator):
    """Reuse indexes built once by the coordinator for all entity reads."""
    indexes = getattr(coordinator, "indexes", None)
    return indexes if isinstance(indexes, tuple) else build_context(coordinator.cache)


class TestoEntity(CoordinatorEntity):
    _attr_has_entity_name = True

    def __init__(self, coordinator, device_id, channel, metric, label):
        super().__init__(coordinator)
        self.device_id = device_id
        self.channel = channel
        self.metric = metric
        self._attr_name = label
        self._attr_unique_id = f"{coordinator.entry.unique_id}_{device_id}_{channel or 'device'}_{metric}"

    @property
    def logger_summary(self):
        summaries = getattr(self.coordinator, "summaries", None)
        if not isinstance(summaries, dict):
            summaries, _ = telemetry_indexes(
                context(self.coordinator)[0],
                self.coordinator.latest,
                [],
                self.coordinator.healthy("measurements"),
                datetime.now(UTC),
                self.coordinator.entry.options.get(CONF_STALE, DEFAULT_STALE),
            )
        return summaries.get(self.device_id, {})

    @property
    def props(self):
        props, devices, _, _ = context(self.coordinator)
        return props.get(self.channel, {}) if self.channel else devices.get(self.device_id, {})

    @property
    def sample(self):
        return self.coordinator.latest.get(self.channel, {})

    @property
    def status(self):
        return context(self.coordinator)[3].get(self.device_id, {})

    @property
    def assignment(self):
        return context(self.coordinator)[2].get(self.channel, {})

    @property
    def age(self):
        dt = timestamp(self.sample.get("timestamp"))
        return max(0, (datetime.now(UTC) - dt).total_seconds() / 60) if dt else None

    @property
    def stale(self):
        return self.age is None or self.age > self.coordinator.entry.options.get(CONF_STALE, DEFAULT_STALE)

    @property
    def device_info(self):
        props = context(self.coordinator)[1].get(self.device_id, {})
        return DeviceInfo(
            identifiers={(DOMAIN, f"{self.coordinator.entry.unique_id}_{self.device_id}")},
            name=props.get("device_display_name") or "Testo logger",
            manufacturer="Testo",
            model=props.get("device_model_code"),
            sw_version=props.get("device_firmware_version"),
            serial_number=props.get("device_serial_no"),
            configuration_url=f"https://www.{self.coordinator.entry.data['region']}.smartconnect.testo.com/",
        )

    @property
    def available(self):
        return super().available and bool(self.props)
