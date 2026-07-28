"""Shared results and parsing helpers for official hazard collectors."""

from __future__ import annotations

import math
from dataclasses import dataclass, field
from datetime import UTC, datetime


def parse_timestamp(value: object) -> datetime | None:
    try:
        parsed = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
        if parsed.tzinfo is None or parsed.utcoffset() is None:
            return None
        return parsed.astimezone(UTC)
    except (TypeError, ValueError):
        return None


def iso_utc(value: datetime) -> str:
    return value.astimezone(UTC).isoformat()


def valid_point(longitude: object, latitude: object) -> tuple[float, float] | None:
    if (
        isinstance(longitude, bool)
        or not isinstance(longitude, (int, float))
        or not math.isfinite(longitude)
        or not -180 <= longitude <= 180
        or isinstance(latitude, bool)
        or not isinstance(latitude, (int, float))
        or not math.isfinite(latitude)
        or not -90 <= latitude <= 90
        or (longitude == 0 and latitude == 0)
    ):
        return None
    return float(longitude), float(latitude)


@dataclass(slots=True)
class CollectionResult:
    events: list[dict] = field(default_factory=list)
    status: str = "ok"
    error: str | None = None
    metrics: dict[str, object] = field(default_factory=dict)
