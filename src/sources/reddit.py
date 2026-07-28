"""Failure-isolated discovery and conservative scoring for Reddit sources."""

from __future__ import annotations

import os
import re
from dataclasses import replace
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import requests

from processors.event_deduplication import create_event_hash
from processors.geolocation import LOCATION_DATABASE
from sources.adapters import parse_reddit_atom
from sources.models import (
    AdapterHealth,
    AdapterStatus,
    DiscoveredItem,
    HealthReason,
    LocationStatus,
    utc_iso,
)
from sources.registry import SourceDefinition

USER_AGENT = "SentinelGridIntelligence/1.0 (public Reddit source monitor)"
INDICATORS = {
    "equipment": ("patriot", "s-400", "b-2", "f-35"),
    "event": (
        "explosion",
        "strike",
        "intercept",
        "evacuation",
        "mobilization",
        "missile",
        "rocket",
        "drone",
        "air raid",
        "nuclear",
        "nuke",
    ),
    "disaster": ("earthquake", "wildfire", "flood"),
    "cyber": ("ransomware", "zero-day", "apt", "ddos"),
}
ACTORS = (
    "iran",
    "israel",
    "idf",
    "irgc",
    "hezbollah",
    "hamas",
    "houthi",
)
SEARCH_TERMS = (
    *ACTORS,
    "missile",
    "rocket",
    "drone",
    "strike",
    "intercept",
    '"air raid"',
    "evacuation",
    "explosion",
    "nuclear",
    "nuke",
    "tehran",
    '"tel aviv"',
    "haifa",
    "jerusalem",
    "beirut",
    "kharkiv",
    "taipei",
    "hormuz",
)


def _location(text: str) -> tuple[float, float, str, str] | None:
    lowered = text.casefold()
    for key in sorted(LOCATION_DATABASE, key=len, reverse=True):
        if re.search(rf"(?<!\w){re.escape(key)}(?!\w)", lowered):
            value = LOCATION_DATABASE[key]
            precision = "city" if value.get("city") else "country"
            return (
                float(value["latitude"]),
                float(value["longitude"]),
                key.title(),
                precision,
            )
    return None


def _score(item: DiscoveredItem, source: SourceDefinition) -> DiscoveredItem:
    text = f"{item.title or ''} {item.text}".casefold()
    location = _location(text)
    indicator_count = sum(
        1 for values in INDICATORS.values() if any(value in text for value in values)
    )
    baseline = (
        0.35 if source.source_tier == 1 else 0.25 if source.source_tier == 2 else 0.15
    )
    external_link = bool(re.search(r"https?://(?!www\.reddit\.com|reddit\.com)", text))
    confidence = min(
        0.8,
        baseline
        + (0.2 if location else 0)
        + (0.15 if external_link else 0)
        + min(0.2, indicator_count * 0.1),
    )
    precise_enough = bool(location and location[3] == "city")
    return replace(
        item,
        latitude=location[0] if location else None,
        longitude=location[1] if location else None,
        location_label=location[2] if location else None,
        location_status=LocationStatus.SOURCE_REPORTED
        if location
        else LocationStatus.MISSING,
        location_confidence=0.72 if precise_enough else 0.5 if location else 0.0,
        claim_confidence=confidence,
        map_eligible=bool(precise_enough and indicator_count and confidence >= 0.55),
    )


def _relevant(item: DiscoveredItem) -> bool:
    text = f"{item.title or ''} {item.text}".casefold()
    return bool(
        _location(text)
        or any(term in text for term in ACTORS)
        or any(term in text for values in INDICATORS.values() for term in values)
    )


def discover_reddit_sources(
    sources: list[SourceDefinition],
    reference_time: datetime,
    *,
    session: Any | None = None,
    timeout: tuple[float, float] = (5, 15),
    cache_path: Path | None = None,
) -> tuple[list[DiscoveredItem], list[AdapterHealth]]:
    client = session or requests.Session()
    checked_at = utc_iso(reference_time)
    items: list[DiscoveredItem] = []
    health: list[AdapterHealth] = []
    enabled = [
        value for value in sources if value.enabled and value.adapter == "reddit"
    ]
    if not enabled:
        return [], []
    names = [source.url.rstrip("/").rsplit("/", 1)[-1] for source in enabled]
    combined_url = f"https://www.reddit.com/r/{'+'.join(names)}/search.rss"
    reason: HealthReason | None = None
    try:
        response = client.get(
            combined_url,
            headers={"User-Agent": USER_AGENT, "Accept": "application/atom+xml"},
            params={
                "q": " OR ".join(SEARCH_TERMS),
                "restrict_sr": 1,
                "sort": "new",
                "limit": 100,
            },
            timeout=timeout,
        )
        if response.status_code == 429:
            reason = HealthReason.RATE_LIMITED
            raise RuntimeError
        if response.status_code in {401, 403}:
            reason = HealthReason.BLOCKED
            raise RuntimeError
        response.raise_for_status()
        response.encoding = "utf-8"
        if cache_path is not None:
            cache_path.parent.mkdir(parents=True, exist_ok=True)
            temporary = cache_path.with_name(f".{cache_path.name}.{os.getpid()}.tmp")
            try:
                temporary.write_text(response.text, encoding="utf-8")
                os.replace(temporary, cache_path)
            finally:
                temporary.unlink(missing_ok=True)
        parsed = parse_reddit_atom(response.text, reference_time)
    except requests.Timeout:
        reason = HealthReason.TIMEOUT
        parsed = []
    except (requests.RequestException, RuntimeError):
        reason = reason or HealthReason.INVALID_RESPONSE
        parsed = []
    except (TypeError, ValueError):
        reason = HealthReason.PARSE_FAILURE
        parsed = []
    if not parsed and cache_path is not None:
        try:
            parsed = parse_reddit_atom(
                cache_path.read_text(encoding="utf-8"), reference_time
            )
        except (OSError, TypeError, ValueError):
            pass
        else:
            reason = HealthReason.CACHE_USED

    by_name = {
        source.url.rstrip("/").rsplit("/", 1)[-1].casefold(): source
        for source in enabled
    }
    counts = {source.id: 0 for source in enabled}
    for item in parsed:
        subreddit = item.source_id.removeprefix("reddit_")
        source = by_name.get(subreddit)
        if source is None or counts[source.id] >= source.maximum_items:
            continue
        if not _relevant(item):
            continue
        scored = _score(replace(item, source_id=source.id), source)
        items.append(scored)
        counts[source.id] += 1

    for source in enabled:
        count = counts[source.id]
        health.append(
            AdapterHealth(
                source.id,
                AdapterStatus.FRESH
                if reason is None
                else AdapterStatus.STALE
                if reason == HealthReason.CACHE_USED
                else AdapterStatus.UNAVAILABLE,
                HealthReason.SUCCESS
                if count
                else reason or HealthReason.EMPTY_VALID_RESPONSE,
                checked_at if reason is None else None,
                checked_at,
                count,
                count,
                None,
            )
        )
    return items, health


def reddit_map_events(items: list[DiscoveredItem]) -> list[dict[str, object]]:
    events = []
    for item in items:
        if not item.map_eligible or item.latitude is None or item.longitude is None:
            continue
        event: dict[str, object] = {
            "event_id": "",
            "event_type": "reddit_report",
            "classification": "source_reported",
            "priority": "medium",
            "title": item.title or f"Reddit report: {item.location_label}",
            "description": item.text,
            "source": [f"Reddit {item.source_id}"],
            "timestamp": (item.published_at or item.discovered_at)
            .astimezone(UTC)
            .isoformat(),
            "location": {
                "country": "Unknown",
                "region": item.location_label,
                "city": item.location_label,
                "latitude": item.latitude,
                "longitude": item.longitude,
                "precision": "source_reported",
            },
            "confidence": round(item.claim_confidence * 100),
            "base_confidence": round(item.claim_confidence * 100),
            "verification": {"confirmed": False, "source_count": 1},
            "url": item.canonical_url,
        }
        event["event_id"] = f"SG-{create_event_hash(event)[:12]}"
        events.append(event)
    return events


def reddit_event_id(item: DiscoveredItem) -> str | None:
    events = reddit_map_events([item])
    return str(events[0]["event_id"]) if events else None
