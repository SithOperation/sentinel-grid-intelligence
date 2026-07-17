"""Build the public collection-health and freshness contract."""

from datetime import datetime, timezone

from output.contracts import SCHEMA_VERSION


def _parse_timestamp(value):
    try:
        parsed = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
        return parsed.replace(tzinfo=timezone.utc) if parsed.tzinfo is None else parsed
    except (TypeError, ValueError):
        return None


def build_health(events, source_health, generated, stale_after_minutes):
    generated_at = _parse_timestamp(generated) or datetime.now(timezone.utc)
    timestamps = [
        parsed
        for parsed in (_parse_timestamp(event.get("timestamp")) for event in events)
        if parsed is not None
    ]
    oldest = min(timestamps) if timestamps else None
    newest = max(timestamps) if timestamps else None
    age_minutes = round((generated_at - newest).total_seconds() / 60, 2) if newest else None
    stale = age_minutes is None or age_minutes > stale_after_minutes
    degraded = stale or any(item["status"] != "ok" for item in source_health)

    return {
        "schema_version": SCHEMA_VERSION,
        "generated": generated,
        "status": "degraded" if degraded else "healthy",
        "degraded": degraded,
        "stale": stale,
        "stale_after_minutes": stale_after_minutes,
        "published_event_count": len(events),
        "freshness": {
            "oldest_event": oldest.isoformat() if oldest else None,
            "newest_event": newest.isoformat() if newest else None,
            "age_minutes": age_minutes,
        },
        "sources": source_health,
    }
