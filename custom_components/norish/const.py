"""Constants for the Norish integration."""
from __future__ import annotations

DOMAIN = "norish"

CONF_API_KEY = "api_key"
CONF_VERIFY_SSL = "verify_ssl"
CONF_OPENAPI_PATH = "openapi_path"
CONF_POLL_INTERVAL = "poll_interval"

DEFAULT_NAME = "Norish"
DEFAULT_OPENAPI_PATH = "/api/openapi.json"
DEFAULT_POLL_INTERVAL = 300
DEFAULT_TIMEOUT = 30

PLATFORMS = ["sensor", "todo", "calendar"]

ATTR_METHOD = "method"
ATTR_PATH = "path"
ATTR_BODY = "body"
ATTR_QUERY = "query"
ATTR_RESPONSE = "response"

SERVICE_CALL_API = "call_api"
SERVICE_REFRESH_OPENAPI = "refresh_openapi"
SERVICE_CREATE_RECIPE = "create_recipe"
SERVICE_IMPORT_RECIPE = "import_recipe"
SERVICE_ADD_GROCERY_ITEM = "add_grocery_item"
