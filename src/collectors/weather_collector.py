"""Normalize active NWS alerts, including safe representative geometry points."""

from __future__ import annotations

from datetime import UTC, datetime

from api.bounded_json import ProviderError
from api.nws_alerts import fetch
from collectors.hazard_common import (
    CollectionResult,
    iso_utc,
    parse_timestamp,
    valid_point,
)
from models.event_model import create_event


def representative_point(geometry: object) -> tuple[float, float] | None:
    if not isinstance(geometry, dict):
        return None
    kind = geometry.get("type")
    coordinates = geometry.get("coordinates")
    if kind == "Point" and isinstance(coordinates, list) and len(coordinates) >= 2:
        return valid_point(coordinates[0], coordinates[1])
    rings = []
    if kind == "Polygon" and isinstance(coordinates, list):
        rings = coordinates[:1]
    elif kind == "MultiPolygon" and isinstance(coordinates, list):
        rings = [
            polygon[0]
            for polygon in coordinates
            if isinstance(polygon, list) and polygon
        ]
    points = []
    for ring in rings:
        if not isinstance(ring, list):
            continue
        for coordinate in ring:
            point = (
                valid_point(coordinate[0], coordinate[1])
                if isinstance(coordinate, list) and len(coordinate) >= 2
                else None
            )
            if point:
                points.append(point)
    if not points:
        return None
    # A bounded vertex mean is deterministic and adequate for a map representative point.
    return sum(p[0] for p in points) / len(points), sum(p[1] for p in points) / len(
        points
    )


def collect_weather_alerts(
    config: dict, reference_time: datetime, transport=None
) -> CollectionResult:
    metrics: dict[str, object] = {
        "records_received": 0,
        "records_accepted": 0,
        "records_rejected": 0,
        "missing_geometry": 0,
        "expired_alerts": 0,
        "test_messages": 0,
    }
    try:
        response = fetch(
            config["alerts_url"],
            connection_timeout_seconds=config["connection_timeout_seconds"],
            request_timeout_seconds=config["request_timeout_seconds"],
            max_response_bytes=config["max_response_bytes"],
            transport=transport,
        )
    except ProviderError as error:
        return CollectionResult(status="error", error=str(error), metrics=metrics)
    metrics["response_size_bytes"] = response.size_bytes
    features = (
        response.data.get("features") if isinstance(response.data, dict) else None
    )
    if not isinstance(features, list):
        return CollectionResult(
            status="error", error="NWS payload has no features array", metrics=metrics
        )
    metrics["records_received"] = len(features)
    events = []
    seen = set()
    valid_severity = {"Extreme", "Severe", "Moderate", "Minor", "Unknown"}
    for feature in features:
        try:
            props = feature["properties"]
            provider_id = str(props.get("id") or feature.get("id") or "").strip()
            expires = parse_timestamp(props.get("ends") or props.get("expires"))
            if (
                not provider_id
                or provider_id in seen
                or expires is None
                or expires < reference_time.astimezone(UTC)
            ):
                expired = metrics["expired_alerts"]
                assert isinstance(expired, int)
                metrics["expired_alerts"] = expired + 1
                raise ValueError("expired or invalid alert")
            severity = str(props.get("severity") or "Unknown")
            if severity not in valid_severity:
                raise ValueError("invalid severity")
            status = str(props.get("status") or "").strip()
            message_type = str(props.get("messageType") or "").strip()
            title = str(props.get("event") or "Weather alert").strip()
            if (
                status.lower() == "test"
                or message_type.lower() == "test"
                or title.lower() in {"test message", "required weekly test", "required monthly test"}
            ):
                test_messages = metrics["test_messages"]
                assert isinstance(test_messages, int)
                metrics["test_messages"] = test_messages + 1
                raise ValueError("test weather message")
            point = representative_point(feature.get("geometry"))
            if point is None:
                missing = metrics["missing_geometry"]
                assert isinstance(missing, int)
                metrics["missing_geometry"] = missing + 1
                location = {
                    "country": "United States",
                    "region": str(props.get("areaDesc") or "Unknown"),
                    "latitude": None,
                    "longitude": None,
                }
                geometry_derived = False
            else:
                longitude, latitude = point
                location = {
                    "country": "United States",
                    "region": str(props.get("areaDesc") or "Unknown"),
                    "latitude": latitude,
                    "longitude": longitude,
                }
                geometry_derived = feature.get("geometry", {}).get("type") != "Point"
            priority = (
                "critical"
                if severity == "Extreme"
                else "high"
                if severity == "Severe"
                else "medium"
            )
            event = create_event(
                "weather_alert",
                "severe_weather_alert",
                title,
                description=str(
                    props.get("description") or props.get("headline") or ""
                ),
                source=["National Weather Service"],
                priority=priority,
                location=location,
                confidence=90,
            )
            # Active alerts use collection time so long-duration hazards remain visible;
            # provider lifecycle timestamps remain intact below.
            event["timestamp"] = iso_utc(reference_time)
            event["url"] = str(props.get("@id") or props.get("id") or "")
            event["provider"] = {"name": "National Weather Service", "id": provider_id}
            event["weather"] = {
                key: props.get(key)
                for key in (
                    "event",
                    "severity",
                    "certainty",
                    "urgency",
                    "status",
                    "messageType",
                    "headline",
                    "description",
                    "instruction",
                    "effective",
                    "onset",
                    "expires",
                    "ends",
                    "areaDesc",
                    "senderName",
                    "sender",
                    "response",
                    "geocode",
                    "references",
                )
            }
            event["weather"]["geometry_type"] = (
                feature.get("geometry", {}).get("type")
                if isinstance(feature.get("geometry"), dict)
                else None
            )
            event["weather"]["geometry_derived_point"] = geometry_derived
            event["verification"] = {"confirmed": True, "source_count": 1}
            events.append(event)
            seen.add(provider_id)
        except (KeyError, TypeError, ValueError):
            rejected = metrics["records_rejected"]
            assert isinstance(rejected, int)
            metrics["records_rejected"] = rejected + 1
    metrics["records_accepted"] = len(events)
    return CollectionResult(events, "ok" if events else "no_data", metrics=metrics)
