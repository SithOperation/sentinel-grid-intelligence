"""Normalize active NASA EONET volcano events into Sentinel events."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

from api.bounded_json import JSONResponse, ProviderError
from api.nasa_eonet import fetch
from collectors.hazard_common import (
    CollectionResult,
    iso_utc,
    parse_timestamp,
    valid_point,
)
from models.event_model import create_event


def _is_volcano(event: dict) -> bool:
    return any(
        str(category.get("id", "")).casefold() == "volcanoes"
        or "volcano" in str(category.get("title", "")).casefold()
        for category in event.get("categories", [])
        if isinstance(category, dict)
    )


def collect_volcanoes(
    config: dict,
    reference_time: datetime,
    transport=None,
    response: JSONResponse | None = None,
) -> CollectionResult:
    metrics: dict[str, object] = {
        "records_received": 0,
        "records_accepted": 0,
        "records_rejected": 0,
        "missing_geometry": 0,
    }
    endpoint = config["endpoint_url"]
    separator = "&" if "?" in endpoint else "?"
    url = f"{endpoint}{separator}category=volcanoes&status=open&limit=200"
    try:
        provider_response = response or fetch(
            url,
            connection_timeout_seconds=config["connection_timeout_seconds"],
            request_timeout_seconds=config["request_timeout_seconds"],
            max_response_bytes=config["max_response_bytes"],
            transport=transport,
        )
    except ProviderError as error:
        return CollectionResult(status="error", error=str(error), metrics=metrics)
    metrics["response_size_bytes"] = provider_response.size_bytes
    events_payload = (
        provider_response.data.get("events")
        if isinstance(provider_response.data, dict)
        else None
    )
    if not isinstance(events_payload, list):
        return CollectionResult(
            status="error", error="EONET payload has no events array", metrics=metrics
        )
    metrics["records_received"] = len(events_payload)
    cutoff = reference_time.astimezone(UTC) - timedelta(hours=72)
    events = []
    seen = set()
    for item in events_payload:
        try:
            provider_id = str(item["id"]).strip()
            if (
                not provider_id
                or provider_id in seen
                or not _is_volcano(item)
                or item.get("closed")
            ):
                raise ValueError("not an active unique volcano")
            history = []
            for geometry in item.get("geometry", []):
                if not isinstance(geometry, dict) or geometry.get("type") != "Point":
                    continue
                coords = geometry.get("coordinates")
                date = parse_timestamp(geometry.get("date"))
                point = (
                    valid_point(coords[0], coords[1])
                    if isinstance(coords, list) and len(coords) >= 2
                    else None
                )
                if date and point:
                    history.append((date, point, geometry))
            if not history:
                missing = metrics["missing_geometry"]
                assert isinstance(missing, int)
                metrics["missing_geometry"] = missing + 1
                raise ValueError("no valid point geometry")
            date, (longitude, latitude), _ = max(history, key=lambda value: value[0])
            if not cutoff <= date <= reference_time:
                raise ValueError("stale geometry")
            title = str(item.get("title") or "Active volcano event")
            event = create_event(
                "volcano",
                "volcanic_activity",
                title,
                description=str(
                    item.get("description")
                    or "Active volcano event reported by NASA EONET"
                ),
                source=["NASA EONET"],
                priority="medium",
                location={
                    "country": "Unknown",
                    "region": "Unknown",
                    "latitude": latitude,
                    "longitude": longitude,
                },
                confidence=85,
            )
            event["timestamp"] = iso_utc(date)
            event["url"] = str(item.get("link") or "")
            event["provider"] = {"name": "NASA EONET", "id": provider_id}
            event["volcano"] = {
                "categories": item.get("categories", []),
                "sources": item.get("sources", []),
                "closed": item.get("closed"),
                "geometry_type": "Point",
                "geometry_history": [
                    {
                        "date": iso_utc(value[0]),
                        "type": "Point",
                        "coordinates": list(value[1]),
                    }
                    for value in sorted(history, key=lambda value: value[0])
                ],
            }
            event["verification"] = {"confirmed": True, "source_count": 1}
            events.append(event)
            seen.add(provider_id)
        except (KeyError, TypeError, ValueError):
            rejected = metrics["records_rejected"]
            assert isinstance(rejected, int)
            metrics["records_rejected"] = rejected + 1
    metrics["records_accepted"] = len(events)
    return CollectionResult(events, "ok" if events else "no_data", metrics=metrics)
