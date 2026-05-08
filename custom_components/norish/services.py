"""Home Assistant services for Norish."""
from __future__ import annotations

from typing import Any

import voluptuous as vol

from homeassistant.core import HomeAssistant, ServiceCall, SupportsResponse
from homeassistant.helpers import config_validation as cv

from .const import (
    ATTR_BODY,
    ATTR_METHOD,
    ATTR_PATH,
    ATTR_QUERY,
    ATTR_RESPONSE,
    DOMAIN,
    SERVICE_ADD_GROCERY_ITEM,
    SERVICE_CALL_API,
    SERVICE_CREATE_RECIPE,
    SERVICE_IMPORT_RECIPE,
    SERVICE_REFRESH_OPENAPI,
)
from .coordinator import NorishDataUpdateCoordinator

CALL_API_SCHEMA = vol.Schema(
    {
        vol.Required(ATTR_METHOD): vol.In(["GET", "POST", "PUT", "PATCH", "DELETE"]),
        vol.Required(ATTR_PATH): str,
        vol.Optional(ATTR_BODY): object,
        vol.Optional(ATTR_QUERY): dict,
    }
)
PAYLOAD_SCHEMA = vol.Schema({vol.Required(ATTR_BODY): dict})

def async_setup_services(hass: HomeAssistant) -> None:
    """Register Norish services once."""
    if hass.services.has_service(DOMAIN, SERVICE_CALL_API):
        return

    async def call_api(call: ServiceCall) -> dict[str, Any]:
        coordinator = _first_coordinator(hass)
        response = await coordinator.client.request(
            call.data[ATTR_METHOD],
            call.data[ATTR_PATH],
            json=call.data.get(ATTR_BODY),
            params=call.data.get(ATTR_QUERY),
        )
        await coordinator.async_request_refresh()
        return {ATTR_RESPONSE: response}

    async def refresh_openapi(call: ServiceCall) -> dict[str, Any]:
        coordinator = _first_coordinator(hass)
        await coordinator.client.openapi(force=True)
        coordinator.operations = await coordinator.client.discover_operations()
        await coordinator.async_request_refresh()
        return {
            "operation_count": len(coordinator.operations),
            "operations": [operation.__dict__ for operation in coordinator.operations.values()],
        }

    async def create_recipe(call: ServiceCall) -> dict[str, Any]:
        coordinator = _first_coordinator(hass)
        response = await coordinator.client.create_recipe(call.data[ATTR_BODY])
        await coordinator.async_request_refresh()
        return {ATTR_RESPONSE: response}

    async def import_recipe(call: ServiceCall) -> dict[str, Any]:
        coordinator = _first_coordinator(hass)
        response = await coordinator.client.import_recipe(call.data[ATTR_BODY])
        await coordinator.async_request_refresh()
        return {ATTR_RESPONSE: response}

    async def add_grocery_item(call: ServiceCall) -> dict[str, Any]:
        coordinator = _first_coordinator(hass)
        response = await coordinator.client.add_grocery_item(call.data[ATTR_BODY])
        await coordinator.async_request_refresh()
        return {ATTR_RESPONSE: response}

    hass.services.async_register(
        DOMAIN,
        SERVICE_CALL_API,
        call_api,
        schema=CALL_API_SCHEMA,
        supports_response=SupportsResponse.ONLY,
    )
    hass.services.async_register(
        DOMAIN,
        SERVICE_REFRESH_OPENAPI,
        refresh_openapi,
        schema=cv.empty_config_schema,
        supports_response=SupportsResponse.ONLY,
    )
    hass.services.async_register(
        DOMAIN,
        SERVICE_CREATE_RECIPE,
        create_recipe,
        schema=PAYLOAD_SCHEMA,
        supports_response=SupportsResponse.ONLY,
    )
    hass.services.async_register(
        DOMAIN,
        SERVICE_IMPORT_RECIPE,
        import_recipe,
        schema=PAYLOAD_SCHEMA,
        supports_response=SupportsResponse.ONLY,
    )
    hass.services.async_register(
        DOMAIN,
        SERVICE_ADD_GROCERY_ITEM,
        add_grocery_item,
        schema=PAYLOAD_SCHEMA,
        supports_response=SupportsResponse.ONLY,
    )

def async_unload_services(hass: HomeAssistant) -> None:
    """Remove Norish services."""
    for service in (
        SERVICE_CALL_API,
        SERVICE_REFRESH_OPENAPI,
        SERVICE_CREATE_RECIPE,
        SERVICE_IMPORT_RECIPE,
        SERVICE_ADD_GROCERY_ITEM,
    ):
        hass.services.async_remove(DOMAIN, service)

def _first_coordinator(hass: HomeAssistant) -> NorishDataUpdateCoordinator:
    coordinators = hass.data.get(DOMAIN, {})
    if not coordinators:
        raise RuntimeError("No Norish integration instance is configured")
    return next(iter(coordinators.values()))
