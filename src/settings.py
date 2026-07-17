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
        "maritime": {"aisstream": {"enabled": True}},
        "satellite": {"nasa_eonet": {"enabled": True}},
        "cyber": {"enabled": True},
        "humanitarian": {"gdacs": {"enabled": True}},
    },
    "output": {
        "directory": "data/output",
        "max_map_events": 2000,
        "max_file_size_mb": 25,
    },
    "retention": {"max_age_days": 30, "max_events": 5000},
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
        raise ValueError("config.yaml must contain a YAML mapping")
    config = _merge(config, loaded)
    for section, key in (
        ("output", "max_map_events"),
        ("output", "max_file_size_mb"),
        ("retention", "max_age_days"),
        ("retention", "max_events"),
    ):
        value = config[section][key]
        if not isinstance(value, int) or isinstance(value, bool) or value <= 0:
            raise ValueError(f"{section}.{key} must be a positive integer")
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
