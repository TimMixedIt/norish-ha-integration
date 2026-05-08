"""Todo platform backed by Norish groceries."""
from __future__ import annotations

from typing import Any

from homeassistant.components.todo import TodoItem, TodoListEntity, TodoListEntityFeature, TodoItemStatus
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
    """Set up Norish grocery todo list."""
    coordinator: NorishDataUpdateCoordinator = hass.data[DOMAIN][entry.entry_id]
    async_add_entities([NorishGroceryTodoList(coordinator, entry)])

class NorishGroceryTodoList(CoordinatorEntity[NorishDataUpdateCoordinator], TodoListEntity):
    """A grocery todo list using Norish grocery endpoints when available."""

    _attr_has_entity_name = True
    _attr_name = "Groceries"
    _attr_supported_features = (
        TodoListEntityFeature.CREATE_TODO_ITEM
        | TodoListEntityFeature.UPDATE_TODO_ITEM
        | TodoListEntityFeature.DELETE_TODO_ITEM
    )

    def __init__(self, coordinator: NorishDataUpdateCoordinator, entry: ConfigEntry) -> None:
        super().__init__(coordinator)
        self._entry = entry
        self._attr_unique_id = f"{entry.entry_id}_groceries_todo"
        self._attr_device_info = {
            "identifiers": {(DOMAIN, entry.entry_id)},
            "name": entry.title,
            "manufacturer": "Norish",
            "configuration_url": coordinator.client.base_url.rstrip("/"),
        }

    @property
    def todo_items(self) -> list[TodoItem] | None:
        groceries = self.coordinator.collection("groceries")
        items = _unwrap_items(groceries)
        if items is None:
            return None
        return [_todo_item(item) for item in items if isinstance(item, dict)]

    async def async_create_todo_item(self, item: TodoItem) -> None:
        """Create a grocery item in Norish."""
        await self.coordinator.client.add_grocery_item(
            {"name": item.summary, "checked": item.status == TodoItemStatus.COMPLETED}
        )
        await self.coordinator.async_request_refresh()

    async def async_update_todo_item(self, item: TodoItem) -> None:
        """Update a grocery item in Norish."""
        uid = item.uid
        if not uid:
            return
        operation = await self.coordinator.client.find_operation("grocery", "update", method="PATCH")
        if operation is None:
            operation = await self.coordinator.client.find_operation("grocery", "update", method="PUT")
        if operation is None:
            return
        path = operation.path.replace("{id}", uid).replace("{itemId}", uid).replace("{groceryId}", uid)
        await self.coordinator.client.request(
            operation.method,
            path,
            json={"id": uid, "name": item.summary, "checked": item.status == TodoItemStatus.COMPLETED},
        )
        await self.coordinator.async_request_refresh()

    async def async_delete_todo_items(self, uids: list[str]) -> None:
        """Delete grocery items in Norish."""
        operation = await self.coordinator.client.find_operation("grocery", "delete", method="DELETE")
        if operation is None:
            return
        for uid in uids:
            path = operation.path.replace("{id}", uid).replace("{itemId}", uid).replace("{groceryId}", uid)
            await self.coordinator.client.request(operation.method, path)
        await self.coordinator.async_request_refresh()

def _unwrap_items(value: Any) -> list[Any] | None:
    if isinstance(value, list):
        return value
    if isinstance(value, dict):
        for key in ("items", "data", "results", "groceries"):
            nested = value.get(key)
            if isinstance(nested, list):
                return nested
    return None

def _todo_item(item: dict[str, Any]) -> TodoItem:
    uid = str(item.get("id") or item.get("uid") or item.get("key") or item.get("name") or item)
    summary = str(item.get("name") or item.get("title") or item.get("label") or uid)
    done = bool(item.get("checked") or item.get("completed") or item.get("done") or item.get("isCompleted"))
    return TodoItem(
        uid=uid,
        summary=summary,
        status=TodoItemStatus.COMPLETED if done else TodoItemStatus.NEEDS_ACTION,
    )
