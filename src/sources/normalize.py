"""Sanitization, retention, and deduplication for discovered source items."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

from sources.canonical import canonicalize_url
from sources.models import DiscoveredItem
from utils.sanitization import plain_text


def normalize_item(item: DiscoveredItem) -> DiscoveredItem:
    return DiscoveredItem(
        source_id=item.source_id,
        platform=plain_text(item.platform, 32).casefold(),
        canonical_url=canonicalize_url(item.canonical_url),
        platform_item_id=plain_text(item.platform_item_id, 128) or None,
        published_at=item.published_at,
        discovered_at=item.discovered_at,
        title=plain_text(item.title, 300) or None,
        text=plain_text(item.text, 5000),
        media_type=plain_text(item.media_type, 32).casefold() or "external",
    )


def retain_and_deduplicate(
    items: list[DiscoveredItem],
    *,
    reference_time: datetime,
    retention_hours: int = 72,
) -> list[DiscoveredItem]:
    reference = reference_time.astimezone(UTC)
    cutoff = reference - timedelta(hours=retention_hours)
    retained: dict[str, DiscoveredItem] = {}
    for raw in items:
        item = normalize_item(raw)
        timestamp = (item.published_at or item.discovered_at).astimezone(UTC)
        if timestamp < cutoff or timestamp > reference:
            continue
        retained.setdefault(item.stable_id, item)
    return sorted(
        retained.values(),
        key=lambda item: item.published_at or item.discovered_at,
        reverse=True,
    )
