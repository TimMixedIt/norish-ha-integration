# GitHub repository settings for HACS

The HACS validation action can validate files in this repository, but a few HACS
checks depend on GitHub repository metadata or binary image assets that should be
managed directly in GitHub instead of through the Codex text-only PR flow.

## Required GitHub metadata

Set these values on the GitHub repository before removing the corresponding
ignored checks from `.github/workflows/validate.yml` or before submitting the
repository for inclusion in the default HACS store.

### Description

```text
Home Assistant integration for Norish recipes, groceries, and meal planning
```

### Topics

```text
home-assistant
home-assistant-integration
hacs
hacs-integration
norish
recipes
meal-planning
```

## Brand assets

HACS requires integration repositories to provide brand assets. Home Assistant
2026.3 and later support local custom integration brand images in:

```text
custom_components/norish/brand/icon.png
```

Codex cannot create PRs containing binary files in this environment, so the
binary `icon.png` is intentionally not committed here. To enable the HACS brand
check later, add a real square PNG icon directly in GitHub or from a local clone,
then remove `brands` from the ignored checks in `.github/workflows/validate.yml`.
