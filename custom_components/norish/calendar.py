"""Calendar platform for Norish meal planning entries."""
from __future__ import annotations

from datetime import date, datetime, time, timedelta
from typing import Any

from homeassistant.components.calendar import CalendarEntity, CalendarEvent
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN
from .coordinator import NorishDataUpdateCoordinator

async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up Norish meal plan calendar."""
    coordinator: NorishDataUpdateCoordinator = hass.data[DOMAIN][entry.entry_id]
    async_add_entities([NorishMealPlanCalendar(coordinator, entry)])

class NorishMealPlanCalendar(CoordinatorEntity[NorishDataUpdateCoordinator], CalendarEntity):
    """Calendar entity showing Norish meal planning data."""

    _attr_has_entity_name = True
    _attr_name = "Meal Plan"

    def __init__(self, coordinator: NorishDataUpdateCoordinator, entry: ConfigEntry) -> None:
        super().__init__(coordinator)
        self._attr_unique_id = f"{entry.entry_id}_meal_plan"
        self._attr_device_info = {
            "identifiers": {(DOMAIN, entry.entry_id)},
            "name": entry.title,
            "manufacturer": "Norish",
            "configuration_url": coordinator.client.base_url.rstrip("/"),
        }

    @property
    def event(self) -> CalendarEvent | None:
        now = datetime.now().astimezone()
        events = [event for event in _events(self.coordinator.collection("calendar")) if event.end >= now]
        return min(events, key=lambda event: event.start, default=None)

    async def async_get_events(
        self,
        hass: HomeAssistant,
        start_date: datetime,
        end_date: datetime,
    ) -> list[CalendarEvent]:
        """Return Norish calendar events in the requested range."""
        return [
            event
            for event in _events(self.coordinator.collection("calendar"))
            if event.end >= start_date and event.start <= end_date
        ]

def _events(value: Any) -> list[CalendarEvent]:
    raw_items = _unwrap_items(value) or []
    events: list[CalendarEvent] = []
    for item in raw_items:
        if not isinstance(item, dict):
            continue
        start = _parse_dt(item.get("start") or item.get("date") or item.get("plannedAt") or item.get("plannedDate"))
        if start is None:
            continue
        end = _parse_dt(item.get("end")) or (start + timedelta(hours=1))
        summary = str(
            item.get("summary")
            or item.get("title")
            or item.get("recipeName")
            or item.get("name")
            or (item.get("recipe") or {}).get("name")
            or (item.get("recipe") or {}).get("title")
            or "Norish meal"
        )
        events.append(CalendarEvent(start=start, end=end, summary=summary, description=item.get("description")))
    return events

def _unwrap_items(value: Any) -> list[Any] | None:
    if isinstance(value, list):
        return value
    if isinstance(value, dict):
        for key in ("items", "data", "results", "events", "calendar", "plannedRecipes", "planned_recipes"):
            nested = value.get(key)
            if isinstance(nested, list):
                return nested
    return None

def _parse_dt(value: Any) -> datetime | None:
    if isinstance(value, datetime):
        return value.astimezone() if value.tzinfo else value.replace(tzinfo=datetime.now().astimezone().tzinfo)
    if isinstance(value, date):
        return datetime.combine(value, time.min).astimezone()
    if not isinstance(value, str):
        return None
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        try:
            parsed = datetime.combine(date.fromisoformat(value), time.min)
        except ValueError:
            return None
    return parsed.astimezone() if parsed.tzinfo else parsed.replace(tzinfo=datetime.now().astimezone().tzinfo)
