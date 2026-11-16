"""Testo Smart Connect integration."""

from homeassistant.const import Platform

from .coordinator import TestoCoordinator

PLATFORMS = [Platform.SENSOR, Platform.BINARY_SENSOR]


async def async_setup_entry(hass, entry):
    coordinator = TestoCoordinator(hass, entry)
    await coordinator.prepare()
    await coordinator.async_config_entry_first_refresh()
    entry.runtime_data = coordinator
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    entry.async_on_unload(entry.add_update_listener(async_reload_entry))
    return True


async def async_reload_entry(hass, entry):
    await hass.config_entries.async_reload(entry.entry_id)


async def async_unload_entry(hass, entry):
    return await hass.config_entries.async_unload_platforms(entry, PLATFORMS)


async def async_remove_entry(hass, entry):
    from homeassistant.helpers.storage import Store

    from .const import DOMAIN

    await Store(hass, 1, f"{DOMAIN}.{entry.entry_id}").async_remove()

    await Store(hass, 1, f"{DOMAIN}.{entry.entry_id}.budget").async_remove()
