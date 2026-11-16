"""Quota-aware scheduling, persisted counters/cache and independent endpoint health."""

from __future__ import annotations

import logging
from datetime import UTC, datetime, timedelta

from homeassistant.exceptions import ConfigEntryAuthFailed
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.storage import Store
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .api import ApiError, AuthenticationError, TestoApi
from .const import CONF_INTERVAL, CONF_REGION, CONF_STALE, DEFAULT_INTERVAL, DEFAULT_STALE, DOMAIN
from .entity import build_context
from .model import channel_key, latest_measurements, telemetry_indexes, timestamp

_LOGGER = logging.getLogger(__name__)


class TestoCoordinator(DataUpdateCoordinator):
    """Fetch all six documented data domains without a request per logger."""

    def __init__(self, hass, entry):
        self.entry = entry
        self.store = Store(hass, 1, f"{DOMAIN}.{entry.entry_id}")
        self.budget_store = Store(hass, 1, f"{DOMAIN}.{entry.entry_id}.budget")
        self.cache = {}
        self.fetched = {}
        self.budget = {}
        self.errors = {}
        self.latest = {}
        self.indexes = build_context({})
        self.row_counts = {}
        self.summaries = {}
        self.alarms_by_device = {}
        self.api = None
        super().__init__(
            hass,
            _LOGGER,
            name=DOMAIN,
            config_entry=entry,
            update_interval=timedelta(minutes=entry.options.get(CONF_INTERVAL, DEFAULT_INTERVAL)),
        )

    async def prepare(self):
        saved = await self.store.async_load() or {}
        self.cache = saved.get("cache", {})
        self.fetched = saved.get("fetched", {})
        self.latest = saved.get("latest", {})
        self.budget = await self.budget_store.async_load() or saved.get("budget", {})
        self.row_counts = saved.get("row_counts", {})
        self.indexes = build_context(self.cache)
        self.api = TestoApi(
            async_get_clientsession(self.hass),
            self.entry.data["api_key"],
            self.entry.data[CONF_REGION],
            self.budget,
            self.save_budget,
        )

    async def save_budget(self):
        await self.budget_store.async_save(self.budget)

    async def save(self):
        await self.store.async_save(
            {
                "cache": self.cache,
                "fetched": self.fetched,
                "budget": self.budget,
                "latest": self.latest,
                "row_counts": self.row_counts,
            }
        )

    async def _async_update_data(self):
        now = datetime.now(UTC)
        successful = 0
        context_changed = False
        periods = {
            "properties": 86400,
            "measurements": self.update_interval.total_seconds(),
            "objects": 86400,
            "locations": 86400,
            "status": 1800,
            "alarms": 1800,
        }
        for kind, period in periods.items():
            last = timestamp(self.fetched.get(kind))
            if last and (now - last).total_seconds() < period and kind not in self.errors:
                continue
            try:
                start = now - timedelta(hours=24)
                if kind == "measurements" and last and self.latest:
                    # One-hour overlap accommodates late processing; restart gap capped at 24h.
                    start = max(start, last - timedelta(hours=1))
                rows = await self.api.query(kind, start.isoformat(), now.isoformat())
                context_changed |= kind in ("properties", "objects", "locations", "status")
                self.row_counts[kind] = len(rows)
                self.cache[kind] = rows
                self.fetched[kind] = now.isoformat()
                self.errors.pop(kind, None)
                if kind == "measurements":
                    self.latest = latest_measurements(rows, self.latest)
                    keys = {channel_key(p) for p in self.cache.get("properties", [])}
                    self.latest = {k: v for k, v in self.latest.items() if k in keys}
                    self.cache[kind] = []  # Persist only newest samples, not full history.
                successful += 1
            except AuthenticationError as err:
                raise ConfigEntryAuthFailed(str(err)) from err
            except ApiError as err:
                self.errors[kind] = str(err)
                _LOGGER.warning("Testo %s: %s", kind, err)
        if context_changed:
            self.indexes = build_context(self.cache)
        if successful:
            await self.save()
        self.summaries, self.alarms_by_device = telemetry_indexes(
            self.indexes[0],
            self.latest,
            self.cache.get("alarms", []),
            self.healthy("measurements"),
            now,
            self.entry.options.get(CONF_STALE, DEFAULT_STALE),
        )
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
