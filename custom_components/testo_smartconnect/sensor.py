"""Measurement and diagnostic sensors, with dynamic discovery on refresh."""

from datetime import UTC, datetime

from homeassistant.components.sensor import SensorDeviceClass, SensorEntity, SensorStateClass
from homeassistant.helpers.entity import EntityCategory

from .entity import TestoEntity, context
from .model import CHANNEL_STATES, LOGGER_STATES, limits, number, observed_alarms, timestamp

SUMMARY_METRICS = {
    "logger_status": ("Measurement availability", None, SensorDeviceClass.ENUM),
    "channels_total": ("Discovered channels", None, None),
    "channels_reporting": ("Channels with samples", None, None),
    "channels_current": ("Channels with current data", None, None),
    "last_measurement": ("Latest measurement", None, SensorDeviceClass.TIMESTAMP),
}
DEVICE_METRICS = {
    **SUMMARY_METRICS,
    "battery_level_percent": ("Battery", "%", SensorDeviceClass.BATTERY),
    "radio_level_percent": ("Radio signal", "%", None),
    "battery_temperature": ("Battery temperature", "°C", SensorDeviceClass.TEMPERATURE),
    "last_communication_time": ("Last communication", None, SensorDeviceClass.TIMESTAMP),
    "next_communication_time": ("Next communication", None, SensorDeviceClass.TIMESTAMP),
    "status_time": ("Status timestamp", None, SensorDeviceClass.TIMESTAMP),
    "connection_type": ("Connection type", None, None),
    "firmware": ("Firmware", None, None),
    "measuring_interval": ("Measuring interval", "s", SensorDeviceClass.DURATION),
    "communication_interval": ("Communication interval", "s", SensorDeviceClass.DURATION),
    "observed_alarms": ("Observed active alarms (24h window)", None, None),
    "last_alarm": ("Last observed alarm", None, SensorDeviceClass.TIMESTAMP),
}
CHANNEL_METRICS = ("data_status", "measurement", "sample_time", "sample_age", "lower_limit", "upper_limit")


async def async_setup_entry(hass, entry, async_add_entities):
    coordinator = entry.runtime_data
    known = set()

    def discover():
        props, devices, assignments, _ = context(coordinator)
        new = []
        for device in devices:
            for metric, (label, _, _) in DEVICE_METRICS.items():
                uid = (device, "", metric)
                if uid not in known:
                    known.add(uid)
                    new.append(TestoSensor(coordinator, device, None, metric, label))
        for key, row in props.items():
            label = assignments.get(key, {}).get("name") or row.get("sensor_display_name") or "Channel"
            label = f"{label} · {row.get('channel_physical_property_name', 'Value')} {row['channel_no']}"
            for metric in CHANNEL_METRICS:
                uid = (row["device_uuid"], key, metric)
                if uid not in known:
                    known.add(uid)
                    suffix = {
                        "data_status": " data status",
                        "measurement": "",
                        "sample_time": " sample time",
                        "sample_age": " sample age",
                        "lower_limit": " lower limit",
                        "upper_limit": " upper limit",
                    }[metric]
                    new.append(TestoSensor(coordinator, row["device_uuid"], key, metric, label + suffix))
        if new:
            async_add_entities(new)

    discover()
    entry.async_on_unload(coordinator.async_add_listener(discover))


class TestoSensor(TestoEntity, SensorEntity):
    def __init__(self, coordinator, device_id, channel, metric, label):
        super().__init__(coordinator, device_id, channel, metric, label)
        self._attr_entity_category = None if metric in ("measurement", "logger_status") else EntityCategory.DIAGNOSTIC
        if metric in SUMMARY_METRICS or metric == "data_status":
            self._attr_name = None
            self._attr_translation_key = metric
            if metric == "data_status":
                self._attr_translation_placeholders = {"channel": label.removesuffix(" data status")}
        if metric in ("logger_status", "data_status"):
            self._attr_options = list(LOGGER_STATES if metric == "logger_status" else CHANNEL_STATES)
            self._attr_icon = "mdi:clipboard-pulse-outline"
        self._attr_entity_registry_enabled_default = metric not in (
            "battery_temperature",
            "status_time",
            "next_communication_time",
            "lower_limit",
            "upper_limit",
        )
        self._attr_suggested_display_precision = 1 if metric in ("measurement", "sample_age") else None

    @property
    def device_class(self):
        if self.metric == "data_status":
            return SensorDeviceClass.ENUM
        if self.metric in ("sample_time",):
            return SensorDeviceClass.TIMESTAMP
        if self.metric == "sample_age":
            return SensorDeviceClass.DURATION
        if self.channel and self.metric in ("measurement", "lower_limit", "upper_limit"):
            return {"Temperature": SensorDeviceClass.TEMPERATURE, "Humidity": SensorDeviceClass.HUMIDITY}.get(
                self.props.get("channel_physical_property_name")
            )
        return DEVICE_METRICS.get(self.metric, ("", None, None))[2]

    @property
    def native_unit_of_measurement(self):
        if self.metric == "sample_age":
            return "min"
        if self.channel and self.metric in ("measurement", "lower_limit", "upper_limit"):
            unit = self.sample.get("physical_unit") or self.props.get("channel_physical_unit")
            return "%" if unit in ("%rF", "%RH") else unit
        return DEVICE_METRICS.get(self.metric, ("", None, None))[1]

    @property
    def state_class(self):
        if self.metric == "measurement":
            return SensorStateClass.MEASUREMENT
        return None

    @property
    def available(self):
        if self.metric in SUMMARY_METRICS:
            return bool(self.props)
        if not super().available:
            return False
        if self.channel:
            if self.metric == "measurement":
                return (
                    self.coordinator.healthy("measurements")
                    and not self.stale
                    and number(self.sample.get("measurement")) is not None
                )
            if self.metric.endswith("_limit"):
                return self.coordinator.healthy("objects")
            return True
        if self.metric in ("observed_alarms", "last_alarm"):
            return self.coordinator.healthy("alarms")
        if self.metric in ("firmware", "measuring_interval", "communication_interval"):
            return self.coordinator.healthy("properties")
        return self.coordinator.healthy("status")

    def device_alarms(self):
        grouped = getattr(self.coordinator, "alarms_by_device", None)
        if isinstance(grouped, dict):
            return grouped.get(self.device_id, [])
        props = context(self.coordinator)[0]
        ids = {self.device_id} | {p["sensor_uuid"] for p in props.values() if p["device_uuid"] == self.device_id}
        return [
            a for a in observed_alarms(self.coordinator.cache.get("alarms", [])) if a.get("alarm_source_uuid") in ids
        ]

    @property
    def data_status(self):
        if not self.coordinator.healthy("measurements"):
            return "api_error"
        if not self.sample:
            return "no_data"
        if number(self.sample.get("measurement")) is None:
            return "invalid_value"
        if self.stale:
            return "stale"
        return "ok"

    @property
    def native_value(self):
        metric = self.metric
        if metric in SUMMARY_METRICS:
            return self.logger_summary.get(metric)
        if metric == "data_status":
            return self.data_status
        if metric == "measurement":
            return number(self.sample.get("measurement"))  # Already scaled by Testo.
        if metric == "sample_time":
            return timestamp(self.sample.get("timestamp"))
        if metric == "sample_age":
            return self.age
        if metric.endswith("_limit"):
            return limits(self.assignment).get(metric.split("_")[0])
        if metric == "firmware":
            return self.props.get("device_firmware_version") or None
        if metric in ("measuring_interval", "communication_interval"):
            field = (
                "device_measuring_cycle_effective"
                if metric == "measuring_interval"
                else "device_communication_log_time"
            )
            value = number(self.props.get(field))
            return value / 1000 if value is not None else None
        if metric == "observed_alarms":
            return sum(a.get("alarm_status") == "Alarm" for a in self.device_alarms())
        if metric == "last_alarm":
            dates = [timestamp(a.get("alarm_time")) for a in self.device_alarms()]
            return max((d for d in dates if d), default=None)
        value = self.status.get(metric)
        if self.device_class == SensorDeviceClass.TIMESTAMP:
            return timestamp(value)
        if self.native_unit_of_measurement:
            return number(value)
        return value or None

    @property
    def extra_state_attributes(self):
        if self.metric in SUMMARY_METRICS:
            return {
                **self.logger_summary,
                "discovered_in_api": bool(self.props),
                "last_successful_measurement_fetch": self.coordinator.fetched.get("measurements"),
                "measurement_error": self.coordinator.errors.get("measurements"),
                "no_data_is_not_a_connection_failure": True,
            }
        if self.channel:
            result = {
                "data_status": self.data_status,
                "last_successful_measurement_fetch": self.coordinator.fetched.get("measurements"),
                "measurement_error": self.coordinator.errors.get("measurements"),
                "channel_no": self.props.get("channel_no"),
                "physical_property": self.props.get("channel_physical_property_name"),
                "physical_extension": self.props.get("channel_physical_extension"),
                "sample_time": self.sample.get("timestamp"),
                "stale": self.stale,
                "sensor_connected_reported": self.props.get("sensor_is_connected"),
                "sample_unit": self.sample.get("physical_unit"),
                "external_channel": self.props.get("channel_is_external"),
                "calibration_possible": self.props.get("channel_is_calibration_possible"),
                "sensor_model": self.props.get("sensor_model_code"),
                "sensor_firmware": self.props.get("sensor_firmware_version"),
                "sensor_measuring_interval_ms": number(self.props.get("sensor_measuring_cycle_effective")),
                "processed_at": self.sample.get("processed_at"),
            }
            if self.metric.endswith("_limit"):
                result["rules"] = limits(self.assignment)["rules"]
            return result
        if self.metric in ("observed_alarms", "last_alarm"):
            return {
                "window_hours": 24,
                "complete_global_alarm_state": False,
                "last_fetch": self.coordinator.fetched.get("alarms"),
                "events": [
                    {
                        k: a.get(k)
                        for k in (
                            "alarm_type",
                            "alarm_status",
                            "alarm_condition_type",
                            "alarm_severity",
                            "alarm_time",
                            "last_status_change_time",
                            "alarm_value",
                            "physical_unit",
                        )
                    }
                    for a in self.device_alarms()
                ][:20],
            }
        if self.metric == "firmware":
            return {
                k: self.props.get(k)
                for k in ("device_model_code", "device_category", "device_supported_battery_types", "device_is_active")
            }
        return {
            "status_time": self.status.get("status_time"),
            "last_fetch": self.coordinator.fetched.get("status"),
            "fetched_age_minutes": max(
                0, (datetime.now(UTC) - timestamp(self.coordinator.fetched["status"])).total_seconds() / 60
            )
            if self.coordinator.fetched.get("status")
            else None,
        }
