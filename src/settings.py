"""Configuration loading for the Sentinel Grid pipeline."""

import json
from copy import deepcopy
from pathlib import Path

import yaml

PROJECT_ROOT = Path(__file__).resolve().parent.parent
CONFIG_PATH = PROJECT_ROOT / "config.yaml"

DEFAULT_CONFIG = {
    "sources": {
        "news": {"enabled": True},
        "conflict": {"enabled": True},
        "aircraft": {"opensky": {"enabled": True}},
        "maritime": {"aisstream": {"enabled": True}},
        "satellite": {"nasa_eonet": {"enabled": True}},
        "cyber": {"enabled": True},
        "humanitarian": {"gdacs": {"enabled": True}},
        "x": {
            "enabled": True,
            "accounts_file": "config/x_accounts.json",
            "keywords_file": "config/x_keywords.json",
            "max_pages": 5,
            "page_size": 100,
            "retries": 3,
            "backoff_seconds": 1.0,
            "timeout_seconds": 30.0,
        },
    },
    "output": {
        "directory": "data/output",
        "max_map_events": 2000,
        "max_file_size_mb": 25,
        "stale_after_minutes": 390,
    },
    "retention": {"max_age_hours": 48, "max_events": 5000},
    "confidence": {"verified": 90, "high": 70, "medium": 40},
}


def _merge(base, override):
    for key, value in override.items():
        if isinstance(value, dict) and isinstance(base.get(key), dict):
            _merge(base[key], value)
        else:
            base[key] = value
    return base


def load_config(path=CONFIG_PATH):
    config = deepcopy(DEFAULT_CONFIG)
    if not Path(path).exists():
        return config

    with Path(path).open("r", encoding="utf-8") as file:
        loaded = yaml.safe_load(file) or {}

    if not isinstance(loaded, dict):
        raise TypeError("config.yaml must contain a YAML mapping")
    config = _merge(config, loaded)
    for section, key in (
        ("output", "max_map_events"),
        ("output", "max_file_size_mb"),
        ("output", "stale_after_minutes"),
        ("retention", "max_age_hours"),
        ("retention", "max_events"),
    ):
        value = config[section][key]
        if not isinstance(value, int) or isinstance(value, bool) or value <= 0:
            raise ValueError(f"{section}.{key} must be a positive integer")
    x_config = config["sources"]["x"]
    for key in ("max_pages", "page_size", "retries"):
        value = x_config[key]
        if not isinstance(value, int) or isinstance(value, bool):
            raise TypeError(f"sources.x.{key} must be an integer")
    if x_config["max_pages"] < 1 or not 5 <= x_config["page_size"] <= 100:
        raise ValueError("sources.x page limits are invalid")
    if x_config["retries"] < 0:
        raise ValueError("sources.x.retries cannot be negative")
    for key in ("backoff_seconds", "timeout_seconds"):
        value = x_config[key]
        if isinstance(value, bool) or not isinstance(value, (int, float)):
            raise TypeError(f"sources.x.{key} must be numeric")
    if x_config["backoff_seconds"] < 0 or x_config["timeout_seconds"] <= 0:
        raise ValueError("sources.x retry timing is invalid")
    return config


def load_json_mapping(path):
    """Load a repository-relative JSON object."""
    resolved = resolve_project_path(path)
    with resolved.open("r", encoding="utf-8") as stream:
        value = json.load(stream)
    if not isinstance(value, dict):
        raise TypeError(f"{resolved} must contain a JSON object")
    return value


def source_enabled(config, *keys):
    value = config.get("sources", {})
    for key in keys:
        if not isinstance(value, dict):
            return False
        value = value.get(key, {})
    return bool(value.get("enabled", False)) if isinstance(value, dict) else False


def resolve_project_path(path):
    candidate = Path(path)
    return candidate if candidate.is_absolute() else PROJECT_ROOT / candidate
