from datetime import UTC, datetime, timedelta

import pytest

from sources.cache import SourceCache
from sources.canonical import canonicalize_url
from sources.models import (
    AdapterHealth,
    AdapterStatus,
    DiscoveredItem,
    DiscoveryResult,
    HealthReason,
)
from sources.normalize import normalize_item, retain_and_deduplicate
from sources.orchestrator import run_adapters

NOW = datetime(2026, 7, 28, 12, tzinfo=UTC)


def item(**changes):
    values = {
        "source_id": "example",
        "platform": "X",
        "canonical_url": "https://twitter.com/example/status/123?utm_source=test#x",
        "platform_item_id": "123",
        "published_at": NOW,
        "discovered_at": NOW,
        "title": "<b>Title</b>",
        "text": "<script>bad()</script><p>Report</p>",
    }
    values.update(changes)
    return DiscoveredItem(**values)


def test_canonicalization_normalizes_platform_variants_and_tracking():
    assert (
        canonicalize_url(
            "https://www.twitter.com/example/status/1?utm_source=x&lang=en#fragment"
        )
        == "https://x.com/example/status/1?lang=en"
    )
    assert (
        canonicalize_url(
            "https://old.reddit.com/r/ukraine/comments/1/?utm_medium=share"
        )
        == "https://reddit.com/r/ukraine/comments/1"
    )


def test_normalization_sanitizes_text():
    value = normalize_item(item())
    assert value.title == "Title"
    assert value.text == "bad() Report"
    assert value.canonical_url == "https://x.com/example/status/123"


def test_retention_uses_published_time_with_discovery_fallback_and_deduplicates():
    boundary = item(published_at=NOW - timedelta(hours=72))
    expired = item(
        platform_item_id="old", published_at=NOW - timedelta(hours=72, seconds=1)
    )
    fallback = item(
        platform_item_id="fallback",
        canonical_url="https://x.com/example/status/456",
        published_at=None,
        discovered_at=NOW - timedelta(hours=1),
    )
    retained = retain_and_deduplicate(
        [boundary, boundary, expired, fallback], reference_time=NOW
    )
    assert {value.platform_item_id for value in retained} == {"123", "fallback"}


def test_cache_is_bounded_atomic_and_rejects_unsafe_ids(tmp_path):
    cache = SourceCache(tmp_path, max_bytes=2048, max_age_hours=1)
    value = {
        "schema_version": "1.0",
        "cached_at": NOW.isoformat(),
        "items": [],
    }
    cache.save("example", value)
    assert cache.load("example", NOW) == value
    assert cache.load("example", NOW + timedelta(hours=2)) is None
    with pytest.raises(ValueError, match="unsafe"):
        cache.path_for("../escape")
    with pytest.raises(ValueError, match="size"):
        cache.save("example", {**value, "data": "x" * 3000})


class GoodAdapter:
    def discover(self, reference_time):
        return DiscoveryResult(
            (item(),),
            AdapterHealth(
                "good",
                AdapterStatus.FRESH,
                HealthReason.SUCCESS,
                NOW.isoformat(),
                NOW.isoformat(),
                1,
                1,
                0,
            ),
        )


class BadAdapter:
    def discover(self, reference_time):
        raise RuntimeError("isolated")


def test_adapter_failure_is_isolated():
    items, health = run_adapters({"good": GoodAdapter(), "bad": BadAdapter()}, NOW)
    assert len(items) == 1
    assert [result.status for result in health] == [
        AdapterStatus.FRESH,
        AdapterStatus.UNAVAILABLE,
    ]
