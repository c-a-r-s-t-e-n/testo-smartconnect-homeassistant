"""Freshness, current threshold deviation and reported power state."""

from homeassistant.components.binary_sensor import BinarySensorDeviceClass, BinarySensorEntity
from homeassistant.helpers.entity import EntityCategory

from .entity import TestoEntity, context
from .model import boolean, limits, number


async def async_setup_entry(hass, entry, async_add_entities):
    coordinator = entry.runtime_data
    known = set()

    def discover():
        props, devices, assignments, _ = context(coordinator)
        new = []
        for did in devices:
            active_uid = (did, "active")
            if active_uid not in known:
                known.add(active_uid)
                new.append(TestoBinary(coordinator, did, None, "active", "Logger active reported"))
            uid = (did, "power")
            if uid not in known:
                known.add(uid)
                new.append(TestoBinary(coordinator, did, None, "power", "External power reported"))
        for key, p in props.items():
            label = assignments.get(key, {}).get("name") or p.get("sensor_display_name") or "Channel"
            for metric, suffix in (
                ("connected", "probe connected reported"),
                ("stale", "data stale"),
                ("invalid", "invalid measurement"),
                ("limit", "outside configured limits"),
            ):
                uid = (key, metric)
                if uid not in known:
                    known.add(uid)
                    new.append(
                        TestoBinary(coordinator, p["device_uuid"], key, metric, f"{label} {p['channel_no']} {suffix}")
                    )
        if new:
            async_add_entities(new)

    discover()
    entry.async_on_unload(coordinator.async_add_listener(discover))


class TestoBinary(TestoEntity, BinarySensorEntity):
    _attr_entity_category = EntityCategory.DIAGNOSTIC

    def __init__(self, coordinator, device_id, channel, metric, label):
        super().__init__(coordinator, device_id, channel, metric, label)
        if metric in ("active", "connected"):
            self._attr_name = None
            self._attr_translation_key = metric
            if metric == "connected":
                self._attr_translation_placeholders = {"channel": label.removesuffix(" probe connected reported")}
            self._attr_entity_registry_enabled_default = False
            self._attr_icon = "mdi:connection"

    @property
    def device_class(self):
        if self.metric in ("active", "connected"):
            return None
        return BinarySensorDeviceClass.POWER if self.metric == "power" else BinarySensorDeviceClass.PROBLEM

    @property
    def available(self):
        if not super().available:
            return False
        if self.metric in ("active", "connected"):
            return self.coordinator.healthy("properties")
        if self.metric == "power":
            return self.coordinator.healthy("status")
        if self.metric == "limit":
            return self.coordinator.healthy("measurements") and self.coordinator.healthy("objects") and not self.stale
        return True

    @property
    def is_on(self):
        if self.metric in ("active", "connected"):
            return boolean(self.props.get("device_is_active" if self.metric == "active" else "sensor_is_connected"))
        if self.metric == "power":
            return boolean(self.status.get("is_powersupply_on"))
        if self.metric == "stale":
            return self.stale
        if self.metric == "invalid":
            return number(self.sample.get("measurement")) is None if self.sample else None
        value = number(self.sample.get("measurement"))
        bounds = limits(self.assignment)
        if value is None or (bounds["lower"] is None and bounds["upper"] is None):
            return None
        return (bounds["lower"] is not None and value < bounds["lower"]) or (
            bounds["upper"] is not None and value > bounds["upper"]
        )

    @property
    def extra_state_attributes(self):
        if self.metric == "limit":
            return {
                "instantaneous_comparison": True,
                "testo_delay_and_hysteresis_applied": False,
                "rules": limits(self.assignment)["rules"],
            }
        if self.metric == "stale":
            return {"sample_time": self.sample.get("timestamp"), "age_minutes": self.age}
        return None
