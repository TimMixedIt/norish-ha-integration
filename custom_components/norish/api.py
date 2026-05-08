"""Async client for the Norish API."""
from __future__ import annotations

import logging
from collections.abc import Iterable, Mapping
from dataclasses import dataclass
from typing import Any
from urllib.parse import urljoin

from aiohttp import ClientError, ClientResponse, ClientSession

from homeassistant.exceptions import HomeAssistantError

from .const import DEFAULT_OPENAPI_PATH, DEFAULT_TIMEOUT

_LOGGER = logging.getLogger(__name__)

OPENAPI_PATH_CANDIDATES = (DEFAULT_OPENAPI_PATH, "/api/v1/openapi.json")


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


@dataclass(frozen=True)
class NorishCollectionEndpoint:
    """A known Norish collection endpoint."""

    key: str
    method: str
    path: str
    body: Mapping[str, Any] | None = None
    tokens: tuple[str, ...] = ()


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
        self._default_household_id: str | None = None

    @property
    def headers(self) -> dict[str, str]:
        """Return authentication and JSON headers."""
        return {
            "Accept": "application/json",
            "Content-Type": "application/json",
            "Authorization": f"Bearer {self.api_key}",
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
        method = method.upper()
        _LOGGER.debug("Norish request: %s %s", method, path)
        try:
            async with self._session.request(
                method,
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
            errors: list[str] = []
            for path in self._openapi_paths():
                _LOGGER.debug("Fetching Norish OpenAPI schema from %s%s", self.base_url.rstrip("/"), path)
                try:
                    document = await self.request("GET", path)
                except NorishApiError as exc:
                    errors.append(f"{path}: {exc}")
                    continue
                if not isinstance(document, dict):
                    errors.append(f"{path}: response is not a JSON object")
                    continue
                self.openapi_path = path
                self._openapi = document
                return self._openapi
            raise NorishApiError("Could not fetch Norish OpenAPI schema: " + "; ".join(errors))
        return self._openapi

    def _openapi_paths(self) -> Iterable[str]:
        """Yield configured and known Norish OpenAPI paths."""
        seen: set[str] = set()
        for path in (self.openapi_path, *OPENAPI_PATH_CANDIDATES):
            if path not in seen:
                seen.add(path)
                yield path

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
        _LOGGER.debug(
            "Discovered Norish operations: %s",
            ", ".join(
                f"{operation.operation_id}={operation.method} {operation.path}"
                for operation in operations.values()
            ),
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

    async def operation_exists(self, method: str, path: str) -> bool:
        """Return whether OpenAPI advertises a matching method/path pair."""
        method = method.upper()
        return any(
            operation.method == method and _paths_match(operation.path, path)
            for operation in (await self.discover_operations()).values()
        )

    async def get_collection(self, endpoint: NorishCollectionEndpoint) -> Any:
        """Fetch a collection endpoint from known Norish routes or OpenAPI."""
        try:
            return await self.request(endpoint.method, endpoint.path, json=endpoint.body)
        except NorishApiError as direct_exc:
            operation = await self.find_operation(*endpoint.tokens, method=endpoint.method)
            if operation is None:
                raise NorishApiError(
                    f"{endpoint.method} {endpoint.path} failed and no matching OpenAPI "
                    f"operation was found: {direct_exc}"
                ) from direct_exc
            path = await self._resolve_path_parameters(operation.path)
            if "{" in path:
                raise NorishApiError(f"Matched unresolved parameterized path {operation.path}") from direct_exc
            return await self.request(operation.method, path, json=endpoint.body)

    async def _resolve_path_parameters(self, path: str) -> str:
        """Resolve known Norish scope parameters such as household ids."""
        if "{" not in path:
            return path
        household_id = await self.default_household_id()
        if household_id is None:
            return path
        for placeholder in ("{householdId}", "{household_id}", "{household}"):
            path = path.replace(placeholder, household_id)
        return path

    async def default_household_id(self) -> str | None:
        """Return the first household id visible to the API key, if exposed."""
        if self._default_household_id is not None:
            return self._default_household_id
        try:
            households = await self.request("GET", "/api/v1/households")
        except NorishApiError as exc:
            _LOGGER.debug("Could not resolve Norish default household: %s", exc)
            return None
        for item in _unwrap_items(households):
            if isinstance(item, Mapping):
                household_id = item.get("id") or item.get("householdId") or item.get("household_id")
                if household_id is not None:
                    self._default_household_id = str(household_id)
                    _LOGGER.debug("Resolved Norish default household id: %s", self._default_household_id)
                    return self._default_household_id
        _LOGGER.debug("Norish household endpoint returned no household id")
        return None

    async def create_recipe(self, payload: Mapping[str, Any]) -> Any:
        """Create a recipe via the first matching Norish endpoint."""
        try:
            return await self.request("POST", "/api/v1/recipes", json=dict(payload))
        except NorishApiError as direct_exc:
            operation = await self.find_operation("recipe", "create", method="POST")
            if operation is None:
                operation = await self.find_operation("recipes", method="POST")
            if operation is None:
                raise NorishApiError("No recipe creation endpoint was advertised by Norish") from direct_exc
            return await self.request(operation.method, operation.path, json=dict(payload))

    async def import_recipe(self, payload: Mapping[str, Any]) -> Any:
        """Import a recipe via URL/text/image/video if Norish advertises such an endpoint."""
        import_type = "paste" if payload.get("text") or payload.get("content") else "url"
        try:
            return await self.request("POST", f"/api/v1/recipes/import/{import_type}", json=dict(payload))
        except NorishApiError as direct_exc:
            operation = await self.find_operation("recipe", "import", import_type, method="POST")
            if operation is None:
                operation = await self.find_operation("recipe", "import", method="POST")
            if operation is None:
                raise NorishApiError("No recipe import endpoint was advertised by Norish") from direct_exc
            return await self.request(operation.method, operation.path, json=dict(payload))

    async def add_grocery_item(self, payload: Mapping[str, Any]) -> Any:
        """Add a grocery item via the first matching Norish endpoint."""
        try:
            return await self.request("POST", "/api/v1/groceries", json=dict(payload))
        except NorishApiError as direct_exc:
            operation = await self.find_operation("grocery", "create", method="POST")
            if operation is None:
                operation = await self.find_operation("groceries", method="POST")
            if operation is None:
                raise NorishApiError("No grocery creation endpoint was advertised by Norish") from direct_exc
            return await self.request(operation.method, operation.path, json=dict(payload))


def _paths_match(openapi_path: str, requested_path: str) -> bool:
    """Match concrete paths against OpenAPI paths that may contain parameters."""
    openapi_parts = openapi_path.strip("/").split("/")
    requested_parts = requested_path.strip("/").split("/")
    if len(openapi_parts) != len(requested_parts):
        return False
    return all(
        openapi_part == requested_part
        or (openapi_part.startswith("{") and openapi_part.endswith("}"))
        for openapi_part, requested_part in zip(openapi_parts, requested_parts, strict=True)
    )


def _unwrap_items(value: Any) -> list[Any]:
    """Return list items from common Norish response envelopes."""
    if isinstance(value, list):
        return value
    if isinstance(value, Mapping):
        for key in ("items", "data", "results", "households"):
            nested = value.get(key)
            if isinstance(nested, list):
                return nested
    return []
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
