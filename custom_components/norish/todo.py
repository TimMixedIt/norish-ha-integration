"""Todo platform backed by Norish groceries."""
from __future__ import annotations

from typing import Any

from homeassistant.components.todo import TodoItem, TodoListEntity, TodoListEntityFeature, TodoItemStatus
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .api import NorishApiError
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
    def todo_items(self) -> list[TodoItem]:
        groceries = self.coordinator.collection("groceries")
        items = _unwrap_items(groceries) or []
        return [_todo_item(item) for item in items if isinstance(item, dict)]

    async def async_create_todo_item(self, item: TodoItem) -> None:
        """Create a grocery item in Norish."""
        await self.coordinator.client.add_grocery_item({"name": item.summary})
        await self.coordinator.async_request_refresh()

    async def async_update_todo_item(self, item: TodoItem) -> None:
        """Update a grocery item in Norish."""
        uid = item.uid
        if not uid:
            return
        item_data = _find_item(self.coordinator.collection("groceries"), uid)
        body: dict[str, Any] = {}
        if isinstance(item_data, dict) and item_data.get("version") is not None:
            body["version"] = item_data["version"]
        action = "done" if item.status == TodoItemStatus.COMPLETED else "undone"
        path = f"/api/v1/groceries/{uid}/{action}"
        try:
            await self.coordinator.client.request("PATCH", path, json=body)
        except NorishApiError:
            operation = await self.coordinator.client.find_operation("grocery", action, method="PATCH")
            if operation is None:
                return
            await self.coordinator.client.request(
                operation.method,
                _replace_path_id(operation.path, uid),
                json=body,
            )
        await self.coordinator.async_request_refresh()

    async def async_delete_todo_items(self, uids: list[str]) -> None:
        """Delete grocery items in Norish."""
        for uid in uids:
            item_data = _find_item(self.coordinator.collection("groceries"), uid)
            body: dict[str, Any] = {}
            if isinstance(item_data, dict) and item_data.get("version") is not None:
                body["version"] = item_data["version"]
            path = f"/api/v1/groceries/{uid}"
            try:
                await self.coordinator.client.request("DELETE", path, json=body or None)
                continue
            except NorishApiError:
                operation = await self.coordinator.client.find_operation("grocery", "delete", method="DELETE")
            if operation is not None:
                await self.coordinator.client.request(
                    operation.method,
                    _replace_path_id(operation.path, uid),
                    json=body or None,
                )
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

def _find_item(value: Any, uid: str) -> dict[str, Any] | None:
    for item in _unwrap_items(value) or []:
        if isinstance(item, dict) and str(item.get("id") or item.get("uid") or item.get("key")) == uid:
            return item
    return None


def _replace_path_id(path: str, uid: str) -> str:
    return path.replace("{id}", uid).replace("{itemId}", uid).replace("{groceryId}", uid)


def _todo_item(item: dict[str, Any]) -> TodoItem:
    uid = str(item.get("id") or item.get("uid") or item.get("key") or item.get("name") or item)
    summary = str(item.get("name") or item.get("title") or item.get("label") or uid)
    done = bool(
        item.get("checked")
        or item.get("completed")
        or item.get("done")
        or item.get("isCompleted")
        or item.get("completedAt")
        or item.get("doneAt")
    )
    return TodoItem(
        uid=uid,
        summary=summary,
        status=TodoItemStatus.COMPLETED if done else TodoItemStatus.NEEDS_ACTION,
    )
