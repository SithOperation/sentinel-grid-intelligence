"""Configuration loading for the Sentinel Grid pipeline."""

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
        "maritime": {"aisstream": {"enabled": False}},
        "satellite": {"nasa_eonet": {"enabled": True}},
        "cyber": {"enabled": True},
        "humanitarian": {"gdacs": {"enabled": True}},
        "x": {
            "enabled": True,
            "connection_timeout_seconds": 5,
            "request_timeout_seconds": 10,
            "request_interval_seconds": 2,
            "max_response_bytes": 1_000_000,
            "max_urls_per_run": 25,
            "cache_file": "data/cache/x_public_posts.json",
            "urls": [],
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
    for key in ("max_response_bytes", "max_urls_per_run"):
        value = x_config[key]
        if not isinstance(value, int) or isinstance(value, bool):
            raise TypeError(f"sources.x.{key} must be an integer")
    if x_config["max_response_bytes"] < 1024 or x_config["max_urls_per_run"] < 1:
        raise ValueError("sources.x size and URL limits are invalid")
    for key in (
        "connection_timeout_seconds",
        "request_timeout_seconds",
        "request_interval_seconds",
    ):
        value = x_config[key]
        if isinstance(value, bool) or not isinstance(value, (int, float)):
            raise TypeError(f"sources.x.{key} must be numeric")
    if (
        x_config["connection_timeout_seconds"] <= 0
        or x_config["request_timeout_seconds"] <= 0
        or x_config["request_interval_seconds"] < 0
    ):
        raise ValueError("sources.x request timing is invalid")
    if (
        not isinstance(x_config["cache_file"], str)
        or not x_config["cache_file"].strip()
    ):
        raise TypeError("sources.x.cache_file must be a path string")
    if not isinstance(x_config["urls"], list):
        raise TypeError("sources.x.urls must be an array")
    return config


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
