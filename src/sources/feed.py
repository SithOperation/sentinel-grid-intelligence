"""Build and validate the mandatory versioned source-feed artifact."""

from __future__ import annotations

import hashlib
import json
import re
from datetime import UTC, datetime, timedelta

from sources.models import AdapterHealth, AdapterStatus, DiscoveredItem, utc_iso
from sources.normalize import retain_and_deduplicate

SCHEMA_VERSION = "1.0"
_PUBLICATION_ID = re.compile(r"^[0-9a-f]{32}$")


def aggregate_status(health: list[AdapterHealth], item_count: int) -> str:
    if not health:
        return AdapterStatus.UNAVAILABLE
    statuses = {item.status for item in health}
    if statuses == {AdapterStatus.FRESH}:
        return AdapterStatus.FRESH
    if AdapterStatus.FRESH in statuses or item_count:
        return AdapterStatus.PARTIAL
    if AdapterStatus.STALE in statuses:
        return AdapterStatus.STALE
    return AdapterStatus.UNAVAILABLE


def build_source_feed(
    items: list[DiscoveredItem],
    health: list[AdapterHealth],
    *,
    publication_id: str,
    generated_at: datetime,
) -> dict[str, object]:
    if _PUBLICATION_ID.fullmatch(publication_id) is None:
        raise ValueError("source feed publication ID is invalid")
    retained = retain_and_deduplicate(items, reference_time=generated_at)
    public_items = []
    for item in retained:
        timestamp = item.published_at or item.discovered_at
        expires = timestamp.astimezone(UTC) + timedelta(hours=72)
        content_hash = hashlib.sha256(
            json.dumps(
                {
                    "source_id": item.source_id,
                    "url": item.canonical_url,
                    "title": item.title,
                    "text": item.text,
                    "media_type": item.media_type,
                },
                ensure_ascii=False,
                sort_keys=True,
                separators=(",", ":"),
            ).encode()
        ).hexdigest()
        public_items.append(
            {
                "id": item.stable_id,
                "platform": item.platform,
                "source_id": item.source_id,
                "source_name": item.source_id,
                "source_handle": None,
                "source_url": item.canonical_url,
                "published_at": utc_iso(item.published_at)
                if item.published_at
                else None,
                "discovered_at": utc_iso(item.discovered_at),
                "last_seen_at": utc_iso(item.discovered_at),
                "cached_at": None,
                "expires_at": utc_iso(expires),
                "title": item.title,
                "text": item.text,
                "media_type": item.media_type,
                "feed_eligible": True,
                "map_eligible": False,
                "embed_eligible": item.platform == "x",
                "map_exclusion_reason": "missing_location",
                "embed_exclusion_reason": None
                if item.platform == "x"
                else "unsupported",
                "latitude": None,
                "longitude": None,
                "location_label": None,
                "location_status": "missing",
                "location_confidence": 0.0,
                "claim_status": "unverified",
                "claim_confidence": 0.0,
                "event_id": None,
                "association_status": "unassociated",
                "association_method": None,
                "association_confidence": 0.0,
                "content_hash": f"sha256:{content_hash}",
                "sanitization_status": "passed",
                "retention_status": "active",
            }
        )
    document = {
        "schema_version": SCHEMA_VERSION,
        "publication_id": publication_id,
        "generated_at": utc_iso(generated_at),
        "count": len(public_items),
        "health": {
            "status": aggregate_status(health, len(public_items)),
            "sources": [item.to_dict() for item in health],
        },
        "items": public_items,
    }
    validate_source_feed(document, reference_time=generated_at)
    return document


def validate_source_feed(value: object, *, reference_time: datetime) -> None:
    if not isinstance(value, dict):
        raise TypeError("source_feed.json must be an object")
    required = {
        "schema_version",
        "publication_id",
        "generated_at",
        "count",
        "health",
        "items",
    }
    if set(value) != required or value["schema_version"] != SCHEMA_VERSION:
        raise ValueError("source_feed.json has an unexpected shape")
    if (
        not isinstance(value["publication_id"], str)
        or _PUBLICATION_ID.fullmatch(value["publication_id"]) is None
    ):
        raise ValueError("source_feed.json publication ID is invalid")
    if not isinstance(value["items"], list) or value["count"] != len(value["items"]):
        raise ValueError("source_feed.json count does not match items")
    if not isinstance(value["health"], dict) or value["health"].get("status") not in {
        status.value for status in AdapterStatus
    }:
        raise ValueError("source_feed.json health is invalid")
    reference = reference_time.astimezone(UTC)
    ids: set[str] = set()
    item_fields = {
        "id",
        "platform",
        "source_id",
        "source_name",
        "source_handle",
        "source_url",
        "published_at",
        "discovered_at",
        "last_seen_at",
        "cached_at",
        "expires_at",
        "title",
        "text",
        "media_type",
        "feed_eligible",
        "map_eligible",
        "embed_eligible",
        "map_exclusion_reason",
        "embed_exclusion_reason",
        "latitude",
        "longitude",
        "location_label",
        "location_status",
        "location_confidence",
        "claim_status",
        "claim_confidence",
        "event_id",
        "association_status",
        "association_method",
        "association_confidence",
        "content_hash",
        "sanitization_status",
        "retention_status",
    }
    for index, item in enumerate(value["items"]):
        if (
            not isinstance(item, dict)
            or set(item) != item_fields
            or not item.get("feed_eligible")
        ):
            raise ValueError(f"source_feed.json item {index} is invalid")
        item_id = item.get("id")
        if not isinstance(item_id, str):
            raise TypeError("source_feed.json item ID is invalid")
        if item_id in ids:
            raise ValueError("source_feed.json item IDs must be unique")
        ids.add(item_id)
        expires = datetime.fromisoformat(str(item.get("expires_at")))
        if expires.tzinfo is None or expires.astimezone(UTC) < reference:
            raise ValueError("source_feed.json cannot publish expired items")
        for field in (
            "location_confidence",
            "claim_confidence",
            "association_confidence",
        ):
            confidence = item.get(field)
            if (
                isinstance(confidence, bool)
                or not isinstance(confidence, (int, float))
                or not 0 <= confidence <= 1
            ):
                raise ValueError(f"source_feed.json {field} is invalid")
        content_hash = item.get("content_hash")
        if (
            not isinstance(content_hash, str)
            or re.fullmatch(r"sha256:[0-9a-f]{64}", content_hash) is None
        ):
            raise ValueError("source_feed.json content hash is invalid")
        if item.get("map_eligible") and (
            not isinstance(item.get("latitude"), (int, float))
            or not isinstance(item.get("longitude"), (int, float))
        ):
            raise ValueError("map-eligible source item requires coordinates")
