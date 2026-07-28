"""Lightweight, dependency-free contracts for published frontend artifacts."""

from datetime import UTC, datetime
from urllib.parse import urlsplit

from models.x_report import validate_x_report_document
from sources.feed import validate_source_feed

SCHEMA_VERSION = "1.0"
SUPPORTED_EVENT_TYPES = {
    "conflict",
    "humanitarian",
    "earthquake",
    "volcano",
    "weather_alert",
    "wildfire",
    "flood",
    "tropical_cyclone",
    "natural_hazard",
    "x_report",
    "reddit_report",
}


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
        if not isinstance(event["event_id"], str) or not event["event_id"].startswith(
            "SG-"
        ):
            raise ContractError(f"{name}[{index}] has an invalid stable event ID")
        if event["event_type"] not in SUPPORTED_EVENT_TYPES:
            raise ContractError(f"{name}[{index}] has an unsupported event type")
        try:
            timestamp = datetime.fromisoformat(
                str(event["timestamp"]).replace("Z", "+00:00")
            )
            if timestamp.tzinfo is None or timestamp.utcoffset() is None:
                raise ValueError
        except (TypeError, ValueError) as error:
            raise ContractError(f"{name}[{index}] has an invalid timestamp") from error
        if event.get("event_type") in {
            "earthquake",
            "volcano",
            "weather_alert",
            "wildfire",
            "flood",
            "tropical_cyclone",
            "natural_hazard",
        }:
            provider = event.get("provider")
            if (
                not isinstance(provider, dict)
                or not provider.get("id")
                or not provider.get("name")
            ):
                raise ContractError(f"{name}[{index}] requires provider metadata")
            parsed_url = urlsplit(str(event.get("url", "")))
            if parsed_url.scheme not in {"http", "https"} or not parsed_url.netloc:
                raise ContractError(f"{name}[{index}] requires a source URL")


def validate_artifacts(artifacts):
    required_files = {
        "world_events.json",
        "intelligence_brief.json",
        "timeline.json",
        "trends.json",
        "map_events.json",
        "dashboard.json",
        "health.json",
        "x_reports.json",
        "x_report_events.json",
        "x_report_pinpoints.geojson",
        "source_feed.json",
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
    if (
        "threat_level" not in dashboard["summary"]
        or "total_events" not in dashboard["summary"]
    ):
        raise ContractError("dashboard.summary requires threat_level and total_events")

    health = artifacts["health.json"]
    _require_mapping(health, "health")
    health_fields = {
        "schema_version",
        "generated",
        "status",
        "degraded",
        "stale",
        "stale_after_minutes",
        "published_event_count",
        "freshness",
        "sources",
        "source_feed",
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
    _require_mapping(health["source_feed"], "health.source_feed")
    if health["source_feed"].get("status") not in {
        "fresh",
        "stale",
        "partial",
        "unavailable",
    }:
        raise ContractError("health.source_feed has an invalid status")
    source_fields = {
        "source",
        "enabled",
        "status",
        "event_count",
        "duration_ms",
        "checked_at",
        "last_success",
        "error",
    }
    for index, source in enumerate(health["sources"]):
        _require_mapping(source, f"health.sources[{index}]")
        missing_source = source_fields.difference(source)
        if missing_source:
            raise ContractError(
                f"health.sources[{index}] missing {sorted(missing_source)}"
            )

    map_events = artifacts["map_events.json"]
    _require_list(map_events, "map_events")
    for index, event in enumerate(map_events):
        _require_mapping(event, f"map_events[{index}]")
        missing = {
            "event_id",
            "type",
            "title",
            "description",
            "latitude",
            "longitude",
            "priority",
            "threat_level",
            "confidence",
            "timestamp",
        }.difference(event)
        if missing:
            raise ContractError(f"map_events[{index}] missing {sorted(missing)}")
        latitude = event.get("latitude")
        longitude = event.get("longitude")
        if not isinstance(latitude, (int, float)) or not -90 <= latitude <= 90:
            raise ContractError(f"map_events[{index}] has invalid latitude")
        if not isinstance(longitude, (int, float)) or not -180 <= longitude <= 180:
            raise ContractError(f"map_events[{index}] has invalid longitude")
        if latitude == 0 and longitude == 0:
            raise ContractError(
                f"map_events[{index}] cannot use placeholder coordinates"
            )
        if event.get("type") not in SUPPORTED_EVENT_TYPES:
            raise ContractError(f"map_events[{index}] has an unsupported event type")

    generated = world.get("generated")
    try:
        reference_time = datetime.fromisoformat(str(generated).replace("Z", "+00:00"))
        if reference_time.tzinfo is None:
            reference_time = reference_time.replace(tzinfo=UTC)
        validate_x_report_document(
            artifacts["x_reports.json"],
            reference_time=reference_time,
        )
    except (TypeError, ValueError) as error:
        raise ContractError(f"x_reports.json is invalid: {error}") from error

    x_events = artifacts["x_report_events.json"]
    x_geojson = artifacts["x_report_pinpoints.geojson"]
    _require_mapping(x_events, "x_report_events")
    _require_mapping(x_geojson, "x_report_pinpoints")
    _require_list(x_events.get("events"), "x_report_events.events")
    _require_list(x_geojson.get("features"), "x_report_pinpoints.features")
    if (
        x_geojson.get("type") != "FeatureCollection"
        or x_events.get("generation_id") != x_geojson.get("generation_id")
        or len(x_geojson["features"]) != len(artifacts["x_reports.json"]["reports"])
    ):
        raise ContractError("X website compatibility artifacts do not match")

    try:
        validate_source_feed(
            artifacts["source_feed.json"],
            reference_time=reference_time,
        )
    except (TypeError, ValueError) as error:
        raise ContractError(f"source_feed.json is invalid: {error}") from error

    return True
