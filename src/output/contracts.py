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
    dashboard = artifacts["dashboard.json"]
    _require_mapping(dashboard.get("summary"), "dashboard.summary")
    if "threat_level" not in dashboard["summary"] or "total_events" not in dashboard["summary"]:
        raise ContractError("dashboard.summary requires threat_level and total_events")

    health = artifacts["health.json"]
    _require_mapping(health, "health")
    health_fields = {
        "schema_version", "generated", "status", "degraded", "stale",
        "stale_after_minutes", "published_event_count", "freshness", "sources",
    }
    missing_health = health_fields.difference(health)
    if missing_health:
        raise ContractError(f"health missing {sorted(missing_health)}")
    if health["schema_version"] != SCHEMA_VERSION:
        raise ContractError("health has an unsupported schema version")
    if health["status"] not in {"healthy", "degraded"}:
        raise ContractError("health has an invalid status")
    _require_mapping(health["freshness"], "health.freshness")
    _require_list(health["sources"], "health.sources")
    source_fields = {
        "source", "enabled", "status", "event_count", "duration_ms",
        "checked_at", "last_success", "error",
    }
    for index, source in enumerate(health["sources"]):
        _require_mapping(source, f"health.sources[{index}]")
        missing_source = source_fields.difference(source)
        if missing_source:
            raise ContractError(f"health.sources[{index}] missing {sorted(missing_source)}")

    map_events = artifacts["map_events.json"]
    _require_list(map_events, "map_events")
    for index, event in enumerate(map_events):
        _require_mapping(event, f"map_events[{index}]")
        missing = {
            "event_id", "type", "title", "description", "latitude", "longitude",
            "priority", "threat_level", "confidence", "timestamp",
        }.difference(event)
        if missing:
            raise ContractError(f"map_events[{index}] missing {sorted(missing)}")
        latitude = event.get("latitude")
        longitude = event.get("longitude")
        if not isinstance(latitude, (int, float)) or not -90 <= latitude <= 90:
            raise ContractError(f"map_events[{index}] has invalid latitude")
        if not isinstance(longitude, (int, float)) or not -180 <= longitude <= 180:
            raise ContractError(f"map_events[{index}] has invalid longitude")

    return True
