"""Lightweight, dependency-free contracts for published frontend artifacts."""

SCHEMA_VERSION = "1.0"


class ContractError(ValueError):
    pass


def _require_mapping(value, name):
    if not isinstance(value, dict):
        raise ContractError(f"{name} must be a JSON object")


def _require_list(value, name):
    if not isinstance(value, list):
        raise ContractError(f"{name} must be a JSON array")


def _validate_events(events, name):
    _require_list(events, name)
    required = {"event_id", "event_type", "title", "timestamp", "confidence"}
    for index, event in enumerate(events):
        _require_mapping(event, f"{name}[{index}]")
        missing = required.difference(event)
        if missing:
            raise ContractError(f"{name}[{index}] missing {sorted(missing)}")


def validate_artifacts(artifacts):
    required_files = {
        "world_events.json",
        "intelligence_brief.json",
        "timeline.json",
        "trends.json",
        "map_events.json",
        "dashboard.json",
        "health.json",
    }
    missing = required_files.difference(artifacts)
    if missing:
        raise ContractError(f"Missing artifacts: {sorted(missing)}")

    world = artifacts["world_events.json"]
    _require_mapping(world, "world_events")
    if world.get("schema_version") != SCHEMA_VERSION:
        raise ContractError("world_events has an unsupported schema version")
    _validate_events(world.get("events"), "world_events.events")
    if world.get("total_events") != len(world["events"]):
        raise ContractError("world_events total_events does not match events")

    _require_mapping(artifacts["intelligence_brief.json"], "intelligence_brief")
    _require_list(artifacts["timeline.json"], "timeline")
    _require_mapping(artifacts["trends.json"], "trends")
    _require_mapping(artifacts["dashboard.json"], "dashboard")
    _require_mapping(artifacts["health.json"], "health")

    map_events = artifacts["map_events.json"]
    _require_list(map_events, "map_events")
    for index, event in enumerate(map_events):
        _require_mapping(event, f"map_events[{index}]")
        latitude = event.get("latitude")
        longitude = event.get("longitude")
        if not isinstance(latitude, (int, float)) or not -90 <= latitude <= 90:
            raise ContractError(f"map_events[{index}] has invalid latitude")
        if not isinstance(longitude, (int, float)) or not -180 <= longitude <= 180:
            raise ContractError(f"map_events[{index}] has invalid longitude")

    return True
