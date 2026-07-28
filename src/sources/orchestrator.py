"""Failure-isolated execution of controlled discovery adapters."""

from __future__ import annotations

from datetime import datetime

from sources.models import (
    AdapterHealth,
    AdapterStatus,
    DiscoveryResult,
    HealthReason,
    SourceAdapter,
    utc_iso,
)


def run_adapters(
    adapters: dict[str, SourceAdapter],
    reference_time: datetime,
) -> tuple[list[object], list[AdapterHealth]]:
    items: list[object] = []
    health: list[AdapterHealth] = []
    checked_at = utc_iso(reference_time)
    for source_id, adapter in adapters.items():
        try:
            result: DiscoveryResult = adapter.discover(reference_time)
            items.extend(result.items)
            health.append(result.health)
        except Exception:
            health.append(
                AdapterHealth(
                    source_id=source_id,
                    status=AdapterStatus.UNAVAILABLE,
                    reason=HealthReason.INVALID_RESPONSE,
                    last_success_at=None,
                    last_attempt_at=checked_at,
                    items_discovered=0,
                    items_published=0,
                    cache_age_seconds=None,
                )
            )
    return items, health
