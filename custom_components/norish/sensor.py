"""Sensors for Norish."""
from __future__ import annotations

from typing import Any

from homeassistant.components.sensor import SensorEntity, SensorEntityDescription
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import EntityCategory
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN
from .coordinator import NorishDataUpdateCoordinator

RESOURCE_SENSORS = (
    ("recipes", "Recipes"),
    ("groceries", "Grocery Items"),
    ("stores", "Stores"),
    ("households", "Households"),
    ("favorites", "Favorites"),
    ("ratings", "Ratings"),
    ("calendar", "Calendar Entries"),
    ("permissions", "Permissions"),
    ("shares", "Share Links"),
)

async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up Norish sensors."""
    coordinator: NorishDataUpdateCoordinator = hass.data[DOMAIN][entry.entry_id]
    entities: list[SensorEntity] = [
        NorishHealthSensor(coordinator, entry),
        NorishOperationCountSensor(coordinator, entry),
    ]
    entities.extend(
        NorishCollectionCountSensor(coordinator, entry, key, name) for key, name in RESOURCE_SENSORS
    )
    async_add_entities(entities)

class NorishBaseSensor(CoordinatorEntity[NorishDataUpdateCoordinator], SensorEntity):
    """Base Norish sensor."""

    _attr_has_entity_name = True

    def __init__(self, coordinator: NorishDataUpdateCoordinator, entry: ConfigEntry, suffix: str) -> None:
        super().__init__(coordinator)
        self._entry = entry
        self._attr_unique_id = f"{entry.entry_id}_{suffix}"
        self._attr_device_info = {
            "identifiers": {(DOMAIN, entry.entry_id)},
            "name": entry.title,
            "manufacturer": "Norish",
            "configuration_url": coordinator.client.base_url.rstrip("/"),
        }

class NorishHealthSensor(NorishBaseSensor):
    """Norish health status."""

    entity_description = SensorEntityDescription(
        key="health",
        translation_key="health",
        entity_category=EntityCategory.DIAGNOSTIC,
    )

    def __init__(self, coordinator: NorishDataUpdateCoordinator, entry: ConfigEntry) -> None:
        super().__init__(coordinator, entry, "health")

    @property
    def native_value(self) -> str:
        health = (self.coordinator.data or {}).get("health")
        if isinstance(health, dict):
            return str(health.get("status") or health.get("ok") or "online")
        return "online" if health is not None else "unknown"

    @property
    def extra_state_attributes(self) -> dict[str, Any] | None:
        health = (self.coordinator.data or {}).get("health")
        return health if isinstance(health, dict) else None

class NorishOperationCountSensor(NorishBaseSensor):
    """Number of OpenAPI operations advertised by Norish."""

    entity_description = SensorEntityDescription(
        key="operation_count",
        translation_key="operation_count",
        entity_category=EntityCategory.DIAGNOSTIC,
    )

    def __init__(self, coordinator: NorishDataUpdateCoordinator, entry: ConfigEntry) -> None:
        super().__init__(coordinator, entry, "operation_count")

    @property
    def native_value(self) -> int:
        return int((self.coordinator.data or {}).get("operation_count") or 0)

class NorishCollectionCountSensor(NorishBaseSensor):
    """Count sensor for an OpenAPI-discovered collection."""

    _attr_native_unit_of_measurement = "items"

    def __init__(
        self,
        coordinator: NorishDataUpdateCoordinator,
        entry: ConfigEntry,
        key: str,
        label: str,
    ) -> None:
        super().__init__(coordinator, entry, f"{key}_count")
        self._key = key
        self._attr_name = label

    @property
    def native_value(self) -> int:
        return self.coordinator.collection_count(self._key)

    @property
    def extra_state_attributes(self) -> dict[str, Any] | None:
        errors = (self.coordinator.data or {}).get("collection_errors", {})
        if self._key not in errors:
            return None
        return {"skipped_reason": errors[self._key]}
    def available(self) -> bool:
        return super().available and self.coordinator.collection_count(self._key) is not None

    @property
    def native_value(self) -> int | None:
        return self.coordinator.collection_count(self._key)
