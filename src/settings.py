"""Configuration loading for the Sentinel Grid pipeline."""

from copy import deepcopy
from pathlib import Path

import yaml

PROJECT_ROOT = Path(__file__).resolve().parent.parent
CONFIG_PATH = PROJECT_ROOT / "config.yaml"

DEFAULT_CONFIG = {
    "sources": {
        "conflict": {"enabled": True},
        "europe_security": {
            "enabled": True,
            "config_file": "config/europe_security.yaml",
            "state_file": "data/cache/europe_security_state.json",
        },
        "eonet": {
            "enabled": True,
            "collect_natural_events": True,
            "collect_volcanoes": True,
            "endpoint_url": "https://eonet.gsfc.nasa.gov/api/v3/events",
            "connection_timeout_seconds": 5,
            "request_timeout_seconds": 15,
            "max_response_bytes": 5_000_000,
        },
        "earthquake": {
            "usgs": {
                "enabled": True,
                "feed_url": "https://earthquake.usgs.gov/earthquakes/feed/v1.0/summary/2.5_day.geojson",
                "connection_timeout_seconds": 5,
                "request_timeout_seconds": 15,
                "max_response_bytes": 5_000_000,
            }
        },
        "weather": {
            "nws": {
                "enabled": True,
                "alerts_url": "https://api.weather.gov/alerts/active",
                "connection_timeout_seconds": 5,
                "request_timeout_seconds": 20,
                "max_response_bytes": 15_000_000,
            }
        },
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
    "retention": {"max_age_hours": 72, "max_events": 5000},
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
    europe_config = config["sources"]["europe_security"]
    if not isinstance(europe_config["enabled"], bool):
        raise TypeError("sources.europe_security.enabled must be boolean")
    for key in ("config_file", "state_file"):
        if not isinstance(europe_config[key], str) or not europe_config[key].strip():
            raise TypeError(f"sources.europe_security.{key} must be a path string")
    for family, provider, url_key in (
        ("earthquake", "usgs", "feed_url"),
        ("eonet", None, "endpoint_url"),
        ("weather", "nws", "alerts_url"),
    ):
        provider_config = (
            config["sources"][family][provider]
            if provider is not None
            else config["sources"][family]
        )
        path = f"sources.{family}.{provider}" if provider else f"sources.{family}"
        if not isinstance(provider_config["enabled"], bool):
            raise TypeError(f"{path}.enabled must be boolean")
        if family == "eonet":
            for flag in ("collect_natural_events", "collect_volcanoes"):
                if not isinstance(provider_config[flag], bool):
                    raise TypeError(f"{path}.{flag} must be boolean")
        url = provider_config[url_key]
        if not isinstance(url, str) or not url.strip().startswith("https://"):
            raise ValueError(f"{path}.{url_key} must be a nonempty HTTPS URL")
        for key in ("connection_timeout_seconds", "request_timeout_seconds"):
            value = provider_config[key]
            if (
                isinstance(value, bool)
                or not isinstance(value, (int, float))
                or value <= 0
            ):
                raise ValueError(f"{path}.{key} must be positive")
        limit = provider_config["max_response_bytes"]
        if isinstance(limit, bool) or not isinstance(limit, int) or limit <= 0:
            raise ValueError(f"{path}.max_response_bytes must be positive")
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
