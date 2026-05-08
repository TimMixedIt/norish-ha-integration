"""Config flow for Norish."""
from __future__ import annotations

from typing import Any

import voluptuous as vol

from homeassistant import config_entries
from homeassistant.const import CONF_URL
from homeassistant.helpers.aiohttp_client import async_create_clientsession

from .api import NorishApiClient, NorishApiError
from .const import (
    CONF_API_KEY,
    CONF_OPENAPI_PATH,
    CONF_POLL_INTERVAL,
    CONF_VERIFY_SSL,
    DEFAULT_OPENAPI_PATH,
    DEFAULT_POLL_INTERVAL,
    DOMAIN,
)

class ConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle a Norish config flow."""

    VERSION = 1

    async def async_step_user(self, user_input: dict[str, Any] | None = None):
        """Handle the initial step."""
        errors: dict[str, str] = {}
        if user_input is not None:
            url = user_input[CONF_URL].rstrip("/")
            await self.async_set_unique_id(url)
            self._abort_if_unique_id_configured()
            session = async_create_clientsession(
                self.hass,
                verify_ssl=user_input.get(CONF_VERIFY_SSL, True),
            )
            client = NorishApiClient(
                session=session,
                base_url=url,
                api_key=user_input[CONF_API_KEY],
                openapi_path=user_input.get(CONF_OPENAPI_PATH, DEFAULT_OPENAPI_PATH),
            )
            try:
                await client.health()
            except NorishApiError:
                errors["base"] = "cannot_connect"
            else:
                return self.async_create_entry(title="Norish", data={**user_input, CONF_URL: url})

        return self.async_show_form(
            step_id="user",
            data_schema=vol.Schema(
                {
                    vol.Required(CONF_URL): str,
                    vol.Required(CONF_API_KEY): str,
                    vol.Optional(CONF_OPENAPI_PATH, default=DEFAULT_OPENAPI_PATH): str,
                    vol.Optional(CONF_VERIFY_SSL, default=True): bool,
                    vol.Optional(CONF_POLL_INTERVAL, default=DEFAULT_POLL_INTERVAL): vol.All(
                        vol.Coerce(int), vol.Range(min=30, max=86400)
                    ),
                }
            ),
            errors=errors,
        )
