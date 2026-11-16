"""Quota-aware scheduling, persisted counters/cache and independent endpoint health."""

from __future__ import annotations

import logging
from datetime import UTC, datetime, timedelta

from homeassistant.exceptions import ConfigEntryAuthFailed
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.storage import Store
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .api import ApiError, AuthenticationError, TestoApi
from .const import CONF_INTERVAL, CONF_REGION, DEFAULT_INTERVAL, DOMAIN
from .model import latest_measurements, timestamp

_LOGGER = logging.getLogger(__name__)


class TestoCoordinator(DataUpdateCoordinator):
    """Fetch all six documented data domains without a request per logger."""

    def __init__(self, hass, entry):
        self.entry = entry
        self.store = Store(hass, 1, f"{DOMAIN}.{entry.entry_id}")
        self.cache = {}
        self.fetched = {}
        self.budget = {}
        self.errors = {}
        self.latest = {}
        self.api = None
        super().__init__(
            hass,
            _LOGGER,
            name=DOMAIN,
            update_interval=timedelta(minutes=entry.options.get(CONF_INTERVAL, DEFAULT_INTERVAL)),
        )

    async def prepare(self):
        saved = await self.store.async_load() or {}
        self.cache = saved.get("cache", {})
        self.fetched = saved.get("fetched", {})
        self.latest = saved.get("latest", {})
        self.budget = saved.get("budget", {})
        self.api = TestoApi(
            async_get_clientsession(self.hass),
            self.entry.data["api_key"],
            self.entry.data[CONF_REGION],
            self.budget,
            self.save,
        )

    async def save(self):
        await self.store.async_save(
            {"cache": self.cache, "fetched": self.fetched, "budget": self.budget, "latest": self.latest}
        )

    async def _async_update_data(self):
        now = datetime.now(UTC)
        successful = 0
        periods = {
            "properties": 86400,
            "objects": 86400,
            "locations": 86400,
            "status": 1800,
            "alarms": 1800,
            "measurements": self.update_interval.total_seconds(),
        }
        for kind, period in periods.items():
            last = timestamp(self.fetched.get(kind))
            if last and (now - last).total_seconds() < period and kind not in self.errors:
                continue
            try:
                start = now - timedelta(hours=24)
                if kind == "measurements" and last:
                    # One-hour overlap accommodates late processing; restart gap capped at 24h.
                    start = max(start, last - timedelta(hours=1))
                rows = await self.api.query(kind, start.isoformat(), now.isoformat())
                self.cache[kind] = rows
                self.fetched[kind] = now.isoformat()
                self.errors.pop(kind, None)
                if kind == "measurements":
                    self.latest = latest_measurements(rows, self.latest)
                    keys = {f"{p['sensor_uuid']}:{p['channel_no']}" for p in self.cache.get("properties", [])}
                    self.latest = {k: v for k, v in self.latest.items() if k in keys}
                    self.cache[kind] = []  # Persist only newest samples, not full history.
                successful += 1
            except AuthenticationError as err:
                raise ConfigEntryAuthFailed(str(err)) from err
            except ApiError as err:
                self.errors[kind] = str(err)
                _LOGGER.warning("Testo %s: %s", kind, err)
        await self.save()
        if not self.cache.get("properties"):
            raise UpdateFailed("No device properties available; check API access")
        if successful == 0 and len(self.errors) == len(periods):
            raise UpdateFailed("All Testo API endpoints failed")
        return {
            "cache": self.cache,
            "latest": self.latest,
            "fetched": self.fetched,
            "errors": self.errors,
            "budget": self.budget,
        }

    def healthy(self, kind):
        return kind in self.fetched and kind not in self.errors
