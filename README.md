# Norish Home Assistant Integration

Custom integration for [Norish](https://github.com/norish-recipes/norish), a self-hosted recipe, grocery, and meal-planning app.

## Features

- Config flow for a Norish base URL and Site/API token.
- Health and OpenAPI discovery sensors.
- Count sensors for OpenAPI-discovered collections such as recipes, groceries, stores, households, favorites, ratings, calendar entries, permissions, and share links.
- Grocery todo entity backed by Norish grocery endpoints when the installed Norish version exposes them.
- Meal-plan calendar entity backed by Norish calendar endpoints when available.
- Services for creating/importing recipes and adding grocery items through discovered endpoints.
- Generic `norish.call_api` service for every Norish API function exposed by the server OpenAPI document, so newly added API endpoints are available immediately.

## Installation

### HACS (recommended)

This repository is structured for HACS as a Home Assistant integration repository:

- `hacs.json` is in the repository root.
- The integration lives in `custom_components/norish`.
- The integration manifest includes the custom-integration `version` field required by HACS.

Until the repository is accepted as a default HACS repository, add it once as a custom repository:

1. Open **HACS → Integrations → ⋮ → Custom repositories**.
2. Paste the GitHub URL of this repository: `https://github.com/norish-recipes/norish-ha-integration`.
3. Select **Integration** as the category and add it.
4. Search for **Norish** in HACS, download it, and restart Home Assistant.
5. Add the integration via **Settings → Devices & services → Add integration → Norish**.

To make Norish searchable in the default HACS store without adding a custom repository first, publish this repository on GitHub, keep the HACS and Hassfest checks green, create a GitHub release, and submit it to the HACS default repositories list.

### Manual

Copy `custom_components/norish` into your Home Assistant `custom_components` directory and restart Home Assistant.

## Configuration

1. In Norish, create a site/API token for Home Assistant.
2. In Home Assistant, go to **Settings → Devices & services → Add integration → Norish**.
3. Enter:
   - Norish URL, for example `http://norish.local:3000`
   - API key/token
   - OpenAPI path, normally `/api/openapi.json`

## Services

- `norish.refresh_openapi`: refresh the OpenAPI schema and return discovered operations.
- `norish.call_api`: call any endpoint by HTTP method, path, optional query parameters, and optional JSON body.
- `norish.create_recipe`: call the recipe creation endpoint discovered from OpenAPI.
- `norish.import_recipe`: call the recipe import endpoint discovered from OpenAPI.
- `norish.add_grocery_item`: call the grocery creation endpoint discovered from OpenAPI.

Norish is evolving quickly; this integration intentionally discovers endpoint paths from the running server instead of hard-coding a single release's routes.
