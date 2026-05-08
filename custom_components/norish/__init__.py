"""Home Assistant integration for Norish."""
from __future__ import annotations

import logging
from datetime import timedelta

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_URL, Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from .api import NorishApiClient
from .const import (
    CONF_API_KEY,
    CONF_OPENAPI_PATH,
    CONF_POLL_INTERVAL,
    CONF_VERIFY_SSL,
    DEFAULT_OPENAPI_PATH,
    DEFAULT_POLL_INTERVAL,
    DOMAIN,
    PLATFORMS,
)
from .coordinator import NorishDataUpdateCoordinator
from .services import async_setup_services, async_unload_services

_LOGGER = logging.getLogger(__name__)

PLATFORM_ENUMS = [Platform(platform) for platform in PLATFORMS]

async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up Norish from a config entry."""
    session = async_get_clientsession(
        hass,
        verify_ssl=entry.options.get(CONF_VERIFY_SSL, entry.data.get(CONF_VERIFY_SSL, True)),
    )
    client = NorishApiClient(
        session=session,
        base_url=entry.data[CONF_URL],
        api_key=entry.data[CONF_API_KEY],
        openapi_path=entry.options.get(
            CONF_OPENAPI_PATH,
            entry.data.get(CONF_OPENAPI_PATH, DEFAULT_OPENAPI_PATH),
        ),
    )
    interval = entry.options.get(CONF_POLL_INTERVAL, entry.data.get(CONF_POLL_INTERVAL, DEFAULT_POLL_INTERVAL))
    coordinator = NorishDataUpdateCoordinator(
        hass,
        _LOGGER,
        client=client,
        update_interval=timedelta(seconds=interval),
    )
    await coordinator.async_config_entry_first_refresh()

    hass.data.setdefault(DOMAIN, {})[entry.entry_id] = coordinator
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORM_ENUMS)
    async_setup_services(hass)
    return True

async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a Norish config entry."""
    unloaded = await hass.config_entries.async_unload_platforms(entry, PLATFORM_ENUMS)
    if unloaded:
        hass.data[DOMAIN].pop(entry.entry_id, None)
        if not hass.data[DOMAIN]:
            async_unload_services(hass)
    return unloaded
