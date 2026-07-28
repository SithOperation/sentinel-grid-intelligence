"""Normalize official USGS earthquakes into Sentinel events."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

from api.bounded_json import ProviderError
from api.usgs_earthquakes import fetch
from collectors.hazard_common import CollectionResult, iso_utc, valid_point
from models.event_model import create_event


def collect_earthquakes(
    config: dict, reference_time: datetime, transport=None
) -> CollectionResult:
    metrics: dict[str, object] = {
        "records_received": 0,
        "records_accepted": 0,
        "records_rejected": 0,
    }
    try:
        response = fetch(
            config["feed_url"],
            connection_timeout_seconds=config["connection_timeout_seconds"],
            request_timeout_seconds=config["request_timeout_seconds"],
            max_response_bytes=config["max_response_bytes"],
            transport=transport,
        )
    except ProviderError as error:
        return CollectionResult(status="error", error=str(error), metrics=metrics)
    metrics["response_size_bytes"] = response.size_bytes
    payload = response.data
    features = payload.get("features") if isinstance(payload, dict) else None
    if not isinstance(features, list):
        return CollectionResult(
            status="error", error="USGS payload has no features array", metrics=metrics
        )
    metrics["records_received"] = len(features)
    generated = payload.get("metadata", {}).get("generated")
    if isinstance(generated, (int, float)):
        metrics["provider_generated"] = iso_utc(
            datetime.fromtimestamp(generated / 1000, UTC)
        )
    cutoff = reference_time.astimezone(UTC) - timedelta(hours=72)
    events = []
    seen = set()
    for feature in features:
        try:
            properties = feature["properties"]
            coordinates = feature["geometry"]["coordinates"]
            provider_id = str(feature["id"]).strip()
            point = valid_point(coordinates[0], coordinates[1])
            timestamp = datetime.fromtimestamp(properties["time"] / 1000, UTC)
            if (
                not provider_id
                or feature.get("type") != "Feature"
                or not isinstance(properties, dict)
                or not isinstance(coordinates, list)
                or len(coordinates) < 3
                or point is None
                or not cutoff <= timestamp <= reference_time
                or str(properties.get("type", "earthquake")).casefold() != "earthquake"
                or provider_id in seen
            ):
                raise ValueError("invalid or duplicate record")
            longitude, latitude = point
            magnitude = properties.get("mag")
            place = str(properties.get("place") or "Unknown location")
            event = create_event(
                "earthquake",
                "seismic_event",
                f"M{magnitude:g} earthquake — {place}"
                if isinstance(magnitude, (int, float))
                else f"Earthquake — {place}",
                description=str(properties.get("title") or place),
                source=["USGS Earthquake Hazards Program"],
                priority="high"
                if isinstance(magnitude, (int, float)) and magnitude >= 6
                else "medium",
                location={
                    "country": "Unknown",
                    "region": place,
                    "latitude": latitude,
                    "longitude": longitude,
                },
                confidence=90,
            )
            event["timestamp"] = iso_utc(timestamp)
            event["url"] = str(properties.get("url") or "")
            event["provider"] = {
                "name": "USGS Earthquake Hazards Program",
                "id": provider_id,
                "updated": iso_utc(
                    datetime.fromtimestamp(properties["updated"] / 1000, UTC)
                )
                if isinstance(properties.get("updated"), (int, float))
                else None,
            }
            event["earthquake"] = {
                "magnitude": magnitude,
                "magnitude_type": properties.get("magType"),
                "depth_km": coordinates[2],
                "alert": properties.get("alert"),
                "tsunami": bool(properties.get("tsunami")),
                "felt_reports": properties.get("felt"),
                "significance": properties.get("sig"),
                "status": properties.get("status"),
                "detail_url": properties.get("detail"),
            }
            event["verification"] = {"confirmed": True, "source_count": 1}
            events.append(event)
            seen.add(provider_id)
        except (KeyError, TypeError, ValueError, OverflowError, OSError):
            rejected = metrics["records_rejected"]
            assert isinstance(rejected, int)
            metrics["records_rejected"] = rejected + 1
    metrics["records_accepted"] = len(events)
    return CollectionResult(events, "ok" if events else "no_data", metrics=metrics)
