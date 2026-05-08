"""DataUpdateCoordinator for Norish."""
from __future__ import annotations

import logging
from collections.abc import Mapping
from datetime import timedelta
from typing import Any

from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .api import NorishApiClient, NorishApiError, NorishCollectionEndpoint, NorishOperation
from .const import DOMAIN

COLLECTIONS: tuple[NorishCollectionEndpoint, ...] = (
    NorishCollectionEndpoint(
        "recipes",
        "POST",
        "/api/v1/recipes/search",
        body={"cursor": 0, "limit": 50},
        tokens=("recipes", "search"),
    ),
    NorishCollectionEndpoint("groceries", "GET", "/api/v1/groceries", tokens=("groceries",)),
    NorishCollectionEndpoint("stores", "GET", "/api/v1/stores", tokens=("stores",)),
    NorishCollectionEndpoint(
        "calendar",
        "GET",
        "/api/v1/planned-recipes/week",
        tokens=("planned", "recipes", "week"),
    ),
    NorishCollectionEndpoint("households", "GET", "/api/v1/households", tokens=("households",)),
    NorishCollectionEndpoint("favorites", "GET", "/api/v1/favorites", tokens=("favorites",)),
    NorishCollectionEndpoint("ratings", "GET", "/api/v1/ratings", tokens=("ratings",)),
    NorishCollectionEndpoint("permissions", "GET", "/api/v1/permissions", tokens=("permissions",)),
    NorishCollectionEndpoint("shares", "GET", "/api/v1/shares", tokens=("share",)),
)


from .api import NorishApiClient, NorishApiError, NorishOperation
from .const import DOMAIN

COLLECTIONS: tuple[tuple[str, tuple[str, ...]], ...] = (
    ("recipes", ("recipes",)),
    ("groceries", ("groceries",)),
    ("stores", ("stores",)),
    ("households", ("households",)),
    ("favorites", ("favorites",)),
    ("ratings", ("ratings",)),
    ("calendar", ("calendar",)),
    ("permissions", ("permissions",)),
    ("shares", ("share",)),
)

class NorishDataUpdateCoordinator(DataUpdateCoordinator[dict[str, Any]]):
    """Keep Norish API state fresh."""

    def __init__(
        self,
        hass: HomeAssistant,
        logger: logging.Logger,
        *,
        client: NorishApiClient,
        update_interval: timedelta,
    ) -> None:
        """Initialize the coordinator."""
        super().__init__(hass, logger, name=DOMAIN, update_interval=update_interval)
        self.client = client
        self.operations: dict[str, NorishOperation] = {}

    async def _async_update_data(self) -> dict[str, Any]:
        """Fetch health, schema, and read-only collections."""
        self.logger.debug(
            "Updating Norish data from base URL %s using OpenAPI path %s",
            self.client.base_url.rstrip("/"),
            self.client.openapi_path,
        )
        try:
            health = await self.client.health()
            openapi_error = None
            try:
                self.operations = await self.client.discover_operations()
            except NorishApiError as exc:
                self.operations = {}
                openapi_error = str(exc)
                self.logger.debug("Skipping Norish OpenAPI discovery: %s", openapi_error)
            collections: dict[str, Any] = {}
            skipped: dict[str, str] = {}
            for endpoint in COLLECTIONS:
                try:
                    collections[endpoint.key] = await self.client.get_collection(endpoint)
                except NorishApiError as exc:
                    reason = str(exc)
                    self.logger.debug("Skipping Norish %s collection: %s", endpoint.key, reason)
                    collections[endpoint.key] = []
                    skipped[endpoint.key] = reason
            return {
                "health": health,
                "collections": collections,
                "collection_errors": skipped,
                "openapi_error": openapi_error,
        try:
            health = await self.client.health()
            self.operations = await self.client.discover_operations()
            collections: dict[str, Any] = {}
            for key, tokens in COLLECTIONS:
                try:
                    collections[key] = await self.client.get_collection(*tokens)
                except NorishApiError as exc:
                    self.logger.debug("Skipping Norish %s collection: %s", key, exc)
                    collections[key] = None
            return {
                "health": health,
                "collections": collections,
                "operation_count": len(self.operations),
            }
        except NorishApiError as exc:
            raise UpdateFailed(str(exc)) from exc

    def collection(self, key: str) -> Any:
        """Return a cached collection by key."""
        return (self.data or {}).get("collections", {}).get(key)

    def collection_count(self, key: str) -> int:
    def collection_count(self, key: str) -> int | None:
        """Return a count for a cached collection."""
        value = self.collection(key)
        return count_items(value)


def count_items(value: Any) -> int:
    """Count items in common API collection shapes."""
    if value is None:
        return 0
    if isinstance(value, list):
        return len(value)
    if isinstance(value, Mapping):
        for key in (
            "items",
            "data",
            "results",
            "recipes",
            "groceries",
            "stores",
            "events",
            "plannedRecipes",
            "planned_recipes",
        ):
def count_items(value: Any) -> int | None:
    """Count items in common API collection shapes."""
    if value is None:
        return None
    if isinstance(value, list):
        return len(value)
    if isinstance(value, Mapping):
        for key in ("items", "data", "results", "recipes", "groceries", "stores", "events"):
            nested = value.get(key)
            if isinstance(nested, list):
                return len(nested)
        for key in ("count", "total", "totalCount"):
            nested = value.get(key)
            if isinstance(nested, int):
                return nested
    return 0
    return None
