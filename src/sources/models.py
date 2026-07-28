"""Normalized source-feed contracts with independent confidence dimensions."""

from __future__ import annotations

import hashlib
from dataclasses import asdict, dataclass
from datetime import UTC, datetime
from enum import StrEnum
from typing import Protocol


class AdapterStatus(StrEnum):
    FRESH = "fresh"
    STALE = "stale"
    PARTIAL = "partial"
    UNAVAILABLE = "unavailable"


class HealthReason(StrEnum):
    SUCCESS = "success"
    EMPTY_VALID_RESPONSE = "empty_valid_response"
    TIMEOUT = "timeout"
    RATE_LIMITED = "rate_limited"
    AUTHENTICATION_REQUIRED = "authentication_required"
    BLOCKED = "blocked"
    INVALID_RESPONSE = "invalid_response"
    PARSE_FAILURE = "parse_failure"
    CACHE_USED = "cache_used"
    CACHE_EXPIRED = "cache_expired"
    DISABLED = "disabled"
    CONFIGURATION_ERROR = "configuration_error"


class LocationStatus(StrEnum):
    VERIFIED = "verified"
    SOURCE_REPORTED = "source_reported"
    APPROXIMATE = "approximate"
    INFERRED = "inferred"
    MISSING = "missing"
    CONFLICTING = "conflicting"


class ClaimStatus(StrEnum):
    VERIFIED = "verified"
    CORROBORATED = "corroborated"
    SOURCE_REPORTED = "source_reported"
    UNVERIFIED = "unverified"
    DISPUTED = "disputed"
    FALSE = "false"


class AssociationStatus(StrEnum):
    CONFIRMED = "confirmed"
    CORROBORATED = "corroborated"
    CANDIDATE = "candidate"
    REJECTED = "rejected"
    UNASSOCIATED = "unassociated"


@dataclass(frozen=True, slots=True)
class AdapterHealth:
    source_id: str
    status: AdapterStatus
    reason: HealthReason
    last_success_at: str | None
    last_attempt_at: str
    items_discovered: int
    items_published: int
    cache_age_seconds: int | None

    def to_dict(self) -> dict[str, object]:
        return asdict(self)


@dataclass(frozen=True, slots=True)
class DiscoveredItem:
    source_id: str
    platform: str
    canonical_url: str
    platform_item_id: str | None
    published_at: datetime | None
    discovered_at: datetime
    title: str | None
    text: str
    media_type: str = "external"
    latitude: float | None = None
    longitude: float | None = None
    location_label: str | None = None
    location_status: LocationStatus = LocationStatus.MISSING
    location_confidence: float = 0.0
    claim_confidence: float = 0.0
    map_eligible: bool = False

    @property
    def stable_id(self) -> str:
        identity = self.platform_item_id or self.canonical_url
        digest = hashlib.sha256(f"{self.source_id}\0{identity}".encode()).hexdigest()[
            :24
        ]
        return f"src_{digest}"


@dataclass(frozen=True, slots=True)
class DiscoveryResult:
    items: tuple[DiscoveredItem, ...]
    health: AdapterHealth


class SourceAdapter(Protocol):
    def discover(self, reference_time: datetime) -> DiscoveryResult: ...


def utc_iso(value: datetime) -> str:
    if value.tzinfo is None or value.utcoffset() is None:
        raise ValueError("timestamp must include a timezone")
    return value.astimezone(UTC).isoformat()
