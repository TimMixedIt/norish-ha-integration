"""Async client for the Norish API."""
from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from typing import Any
from urllib.parse import urljoin

from aiohttp import ClientError, ClientResponse, ClientSession

from homeassistant.exceptions import HomeAssistantError

from .const import DEFAULT_OPENAPI_PATH, DEFAULT_TIMEOUT


class NorishApiError(HomeAssistantError):
    """Raised when Norish returns an error."""


@dataclass(frozen=True)
class NorishOperation:
    """A single OpenAPI operation exposed by Norish."""

    operation_id: str
    method: str
    path: str
    summary: str | None = None
    tags: tuple[str, ...] = ()


class NorishApiClient:
    """HTTP client for Norish's OpenAPI backed REST API."""

    def __init__(
        self,
        *,
        session: ClientSession,
        base_url: str,
        api_key: str,
        openapi_path: str = DEFAULT_OPENAPI_PATH,
        timeout: int = DEFAULT_TIMEOUT,
    ) -> None:
        """Initialize the client."""
        self._session = session
        self.base_url = base_url.rstrip("/") + "/"
        self.api_key = api_key
        self.openapi_path = openapi_path if openapi_path.startswith("/") else f"/{openapi_path}"
        self.timeout = timeout
        self._openapi: dict[str, Any] | None = None

    @property
    def headers(self) -> dict[str, str]:
        """Return authentication and JSON headers."""
        return {
            "Accept": "application/json",
            "Content-Type": "application/json",
            "x-api-key": self.api_key,
        }

    def _url(self, path: str) -> str:
        path = path.lstrip("/")
        return urljoin(self.base_url, path)

    async def _decode_response(self, response: ClientResponse) -> Any:
        if response.status == 204:
            return None
        content_type = response.headers.get("content-type", "")
        if "json" in content_type:
            return await response.json()
        return await response.text()

    async def request(
        self,
        method: str,
        path: str,
        *,
        json: Any | None = None,
        params: Mapping[str, Any] | None = None,
    ) -> Any:
        """Call a Norish API endpoint."""
        try:
            async with self._session.request(
                method.upper(),
                self._url(path),
                headers=self.headers,
                json=json,
                params=params,
                timeout=self.timeout,
            ) as response:
                payload = await self._decode_response(response)
                if response.status >= 400:
                    message = payload.get("message") if isinstance(payload, dict) else payload
                    raise NorishApiError(f"Norish API {response.status}: {message}")
                return payload
        except TimeoutError as exc:
            raise NorishApiError("Timed out while talking to Norish") from exc
        except ClientError as exc:
            raise NorishApiError(f"Could not talk to Norish: {exc}") from exc

    async def health(self) -> Any:
        """Fetch the health endpoint."""
        return await self.request("GET", "/api/v1/health")

    async def openapi(self, *, force: bool = False) -> dict[str, Any]:
        """Fetch and cache the OpenAPI document."""
        if self._openapi is None or force:
            document = await self.request("GET", self.openapi_path)
            if not isinstance(document, dict):
                raise NorishApiError("Norish OpenAPI response is not a JSON object")
            self._openapi = document
        return self._openapi

    async def discover_operations(self) -> dict[str, NorishOperation]:
        """Return all operations from the OpenAPI document keyed by operation id."""
        document = await self.openapi()
        operations: dict[str, NorishOperation] = {}
        for path, path_item in (document.get("paths") or {}).items():
            if not isinstance(path_item, dict):
                continue
            for method, operation in path_item.items():
                if method.upper() not in {"GET", "POST", "PUT", "PATCH", "DELETE"}:
                    continue
                if not isinstance(operation, dict):
                    continue
                operation_id = str(operation.get("operationId") or f"{method}_{path}".replace("/", "_"))
                operations[operation_id] = NorishOperation(
                    operation_id=operation_id,
                    method=method.upper(),
                    path=path,
                    summary=operation.get("summary") or operation.get("description"),
                    tags=tuple(operation.get("tags") or ()),
                )
        return operations

    async def find_operation(self, *tokens: str, method: str | None = None) -> NorishOperation | None:
        """Find the best operation containing all tokens in id/path/summary."""
        wanted = [token.casefold() for token in tokens if token]
        for operation in (await self.discover_operations()).values():
            if method and operation.method != method.upper():
                continue
            haystack = " ".join(
                [operation.operation_id, operation.path, operation.summary or "", *operation.tags]
            ).casefold()
            if all(token in haystack for token in wanted):
                return operation
        return None

    async def get_collection(self, *tokens: str) -> Any:
        """Fetch a collection endpoint discovered from OpenAPI."""
        operation = await self.find_operation(*tokens, method="GET")
        if operation is None or "{" in operation.path:
            return None
        return await self.request(operation.method, operation.path)

    async def create_recipe(self, payload: Mapping[str, Any]) -> Any:
        """Create a recipe via the first matching Norish endpoint."""
        operation = await self.find_operation("recipe", "create", method="POST")
        if operation is None:
            operation = await self.find_operation("recipes", method="POST")
        if operation is None:
            raise NorishApiError("No recipe creation endpoint was advertised by Norish")
        return await self.request(operation.method, operation.path, json=dict(payload))

    async def import_recipe(self, payload: Mapping[str, Any]) -> Any:
        """Import a recipe via URL/text/image/video if Norish advertises such an endpoint."""
        operation = await self.find_operation("recipe", "import", method="POST")
        if operation is None:
            raise NorishApiError("No recipe import endpoint was advertised by Norish")
        return await self.request(operation.method, operation.path, json=dict(payload))

    async def add_grocery_item(self, payload: Mapping[str, Any]) -> Any:
        """Add a grocery item via the first matching Norish endpoint."""
        operation = await self.find_operation("grocery", "create", method="POST")
        if operation is None:
            operation = await self.find_operation("groceries", method="POST")
        if operation is None:
            raise NorishApiError("No grocery creation endpoint was advertised by Norish")
        return await self.request(operation.method, operation.path, json=dict(payload))
