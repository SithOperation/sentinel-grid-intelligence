"""
Sentinel Grid Event Deduplication

Creates stable event fingerprints.

Features:
- Location awareness
- Source aggregation
- Duplicate tracking
"""

import hashlib
from datetime import datetime


def clean(value):

    if value is None:
        return ""

    return str(value).strip().lower()


def create_event_hash(event):

    event_type = clean(event.get("event_type"))

    if event_type in {"wildfire", "flood", "tropical_cyclone", "natural_hazard"}:
        observation_id = event.get("observation", {}).get("event_id")
        if observation_id:
            return hashlib.sha256(clean(observation_id).encode()).hexdigest()

    if event_type == "x_report":
        status_id = event.get("x_report", {}).get("status_id")
        if status_id:
            return hashlib.sha256(f"x:{clean(status_id)}".encode()).hexdigest()

    if event_type in {"earthquake", "volcano", "weather_alert"}:
        provider_id = event.get("provider", {}).get("id")
        provider_name = event.get("provider", {}).get("name")
        if provider_id:
            return hashlib.sha256(
                f"{event_type}:{clean(provider_name)}:{clean(provider_id)}".encode()
            ).hexdigest()

    location = event.get("location", {})

    location_key = clean(location.get("country")) + clean(location.get("region"))

    identity = event_type + clean(event.get("title")) + location_key

    return hashlib.sha256(identity.encode()).hexdigest()


def _cross_provider_key(event):
    """Conservative hazard key used only for obvious GDACS overlap."""
    event_type = clean(event.get("event_type"))
    if event_type not in {"earthquake", "volcano", "weather_alert", "humanitarian"}:
        return None
    text = f"{clean(event.get('title'))} {clean(event.get('description'))}"
    hazard = next(
        (
            name
            for name in ("earthquake", "volcano", "cyclone", "hurricane", "flood")
            if name in text
        ),
        None,
    )
    location = event.get("location", {})
    latitude, longitude = location.get("latitude"), location.get("longitude")
    try:
        timestamp = datetime.fromisoformat(
            str(event.get("timestamp")).replace("Z", "+00:00")
        )
    except (TypeError, ValueError):
        return None
    if (
        hazard is None
        or not isinstance(latitude, (int, float))
        or not isinstance(longitude, (int, float))
    ):
        return None
    # Half-degree geography and six-hour time buckets avoid merging nearby,
    # distinct emergencies while catching clearly mirrored provider records.
    return (
        hazard,
        round(latitude * 2),
        round(longitude * 2),
        int(timestamp.timestamp() // 21_600),
    )


def remove_duplicates(events):

    seen = {}

    results = []
    cross_provider = {}

    for event in events:
        event_hash = create_event_hash(event)
        overlap_key = _cross_provider_key(event)
        if overlap_key in cross_provider:
            event_hash = cross_provider[overlap_key]

        if event_hash in seen:
            existing = seen[event_hash]

            existing_sources = existing.get("source", [])
            if not isinstance(existing_sources, list):
                existing_sources = [existing_sources]
            new_sources = event.get("source", [])
            if not isinstance(new_sources, list):
                new_sources = [new_sources]
            duplicate_count = existing.get("duplicate_count", 1) + event.get(
                "duplicate_count", 1
            )
            if event.get("event_type") in {
                "earthquake",
                "volcano",
                "weather_alert",
            }:
                try:
                    existing_time = datetime.fromisoformat(
                        str(existing.get("timestamp")).replace("Z", "+00:00")
                    )
                    new_time = datetime.fromisoformat(
                        str(event.get("timestamp")).replace("Z", "+00:00")
                    )
                    if new_time > existing_time:
                        preserved_hash = existing["event_hash"]
                        preserved_id = existing["event_id"]
                        existing.clear()
                        existing.update(event)
                        existing["event_hash"] = preserved_hash
                        existing["event_id"] = preserved_id
                except (TypeError, ValueError):
                    pass
            existing["duplicate_count"] = duplicate_count
            verification = existing.setdefault("verification", {})
            existing["source"] = list(dict.fromkeys(existing_sources + new_sources))
            verification["source_count"] = len(existing["source"])

            continue

        event["event_hash"] = event_hash

        event["event_id"] = f"SG-{event_hash[:12]}"

        event["duplicate_count"] = 1

        seen[event_hash] = event
        if overlap_key:
            cross_provider[overlap_key] = event_hash

        results.append(event)

    return results
