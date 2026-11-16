"""Structural diagnostics only: never export raw account/device data or credentials."""


async def async_get_config_entry_diagnostics(hass, entry):
    coordinator = entry.runtime_data
    return {
        "integration_version": "0.1.0",
        "region": entry.data["region"],
        "options": dict(entry.options),
        "endpoint_rows": {k: len(v) for k, v in coordinator.cache.items()},
        "latest_channel_count": len(coordinator.latest),
        "fields": {k: sorted({field for row in rows for field in row}) for k, rows in coordinator.cache.items()},
        "endpoint_errors": dict(coordinator.errors),
        "last_fetch": dict(coordinator.fetched),
        "local_budget": dict(coordinator.budget),
        "budget_excludes_other_clients_and_setup": True,
    }
