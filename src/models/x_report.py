"""Strict X report model and Sentinel event adapter."""

from __future__ import annotations

import hashlib
import json
import math
import re
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from urllib.parse import urlsplit

SCHEMA_VERSION = "1.0"
RETENTION_HOURS = 72
EVENT_TYPES = frozenset(
    {
        "early_report",
        "reported_attack",
        "reported_military_activity",
        "reported_strike",
        "unclassified_early_report",
    }
)
SOURCE_CLASSES = frozenset(
    {
        "official",
        "social_media_aggregator",
        "social_media_monitor",
        "social_media_osint",
        "unknown_social_media",
    }
)
LOCATION_PRECISIONS = frozenset(
    {"exact", "neighborhood", "city", "regional_approximate", "region", "country"}
)
_HANDLE = re.compile(r"^[A-Za-z0-9_]{1,15}$")
_STATUS_PATH = re.compile(r"^/([A-Za-z0-9_]{1,15})/status/([0-9]+)$")


def _aware_utc(value: datetime, label: str) -> datetime:
    if value.tzinfo is None or value.utcoffset() is None:
        raise ValueError(f"{label} must include a timezone")
    return value.astimezone(UTC)


def canonical_x_url(value: str) -> tuple[str, str, str]:
    """Return canonical URL, account, and status ID for one X status."""
    parsed = urlsplit(value.strip())
    match = _STATUS_PATH.fullmatch(parsed.path)
    if (
        parsed.scheme != "https"
        or parsed.netloc.casefold()
        not in {"x.com", "www.x.com", "twitter.com", "www.twitter.com"}
        or parsed.query
        or parsed.fragment
        or match is None
    ):
        raise ValueError("source_url must be a public X status URL")
    account, status_id = match.groups()
    return f"https://x.com/{account}/status/{status_id}", account, status_id


@dataclass(frozen=True, slots=True)
class XReport:
    """Validated production X report that can enter Sentinel processing."""

    account: str
    source_url: str
    summary: str
    published_at: datetime
    collected_at: datetime
    source_class: str
    event_type: str
    latitude: float
    longitude: float
    location_name: str
    location_precision: str = "regional_approximate"
    confidence: float = 0.65
    quoted_url: str | None = None
    reposted_url: str | None = None

    def __post_init__(self) -> None:
        canonical, url_account, _ = canonical_x_url(self.source_url)
        account = self.account.strip().lstrip("@")
        if _HANDLE.fullmatch(account) is None:
            raise ValueError("account must be a valid X handle")
        if url_account.casefold() != account.casefold():
            raise ValueError("source_url account must match report account")
        if not self.summary.strip():
            raise ValueError("summary must be non-empty")
        if self.source_class not in SOURCE_CLASSES:
            raise ValueError(f"unsupported source_class: {self.source_class}")
        if self.event_type not in EVENT_TYPES:
            raise ValueError(f"unsupported event_type: {self.event_type}")
        if self.location_precision not in LOCATION_PRECISIONS:
            raise ValueError("X report location_precision is invalid")
        if not self.location_name.strip():
            raise ValueError("location_name must be non-empty")
        for name in ("latitude", "longitude", "confidence"):
            value = getattr(self, name)
            if (
                isinstance(value, bool)
                or not isinstance(value, (int, float))
                or not math.isfinite(value)
            ):
                raise ValueError(f"{name} must be a finite number")
        if not -90 <= self.latitude <= 90 or not -180 <= self.longitude <= 180:
            raise ValueError("X report coordinates are invalid")
        if not 0 <= self.confidence <= 1:
            raise ValueError("confidence must be between 0 and 1")
        object.__setattr__(self, "account", account)
        object.__setattr__(self, "source_url", canonical)
        object.__setattr__(
            self, "published_at", _aware_utc(self.published_at, "published_at")
        )
        object.__setattr__(
            self, "collected_at", _aware_utc(self.collected_at, "collected_at")
        )
        for field in ("quoted_url", "reposted_url"):
            value = getattr(self, field)
            if value is not None:
                object.__setattr__(self, field, canonical_x_url(value)[0])

    @property
    def status_id(self) -> str:
        return canonical_x_url(self.source_url)[2]

    def to_dict(self) -> dict[str, object]:
        return {
            "schema_version": SCHEMA_VERSION,
            "status_id": self.status_id,
            "account": self.account,
            "source_url": self.source_url,
            "published_at": self.published_at.isoformat(),
            "collected_at": self.collected_at.isoformat(),
            "summary": self.summary,
            "event_type": self.event_type,
            "source_class": self.source_class,
            "verification_status": "not_independently_verified",
            "confidence": self.confidence,
            "latitude": self.latitude,
            "longitude": self.longitude,
            "location_name": self.location_name,
            "location_precision": self.location_precision,
            "quoted_url": self.quoted_url,
            "reposted_url": self.reposted_url,
        }

    def to_event(self) -> dict[str, object]:
        """Adapt the report to Sentinel's shared event model."""
        return {
            "event_type": "x_report",
            "classification": self.event_type,
            "priority": "medium",
            "title": f"X early report: {self.location_name}",
            "description": self.summary,
            "source": [f"X @{self.account}"],
            "timestamp": self.published_at.isoformat(),
            "location": {
                "country": "Unknown",
                "region": self.location_name,
                "latitude": self.latitude,
                "longitude": self.longitude,
                "precision": self.location_precision,
            },
            "confidence": round(self.confidence * 100),
            "base_confidence": round(self.confidence * 100),
            "verification": {"confirmed": False, "source_count": 1},
            "url": self.source_url,
            "x_report": self.to_dict(),
        }


def validate_x_report_document(
    document: object,
    *,
    reference_time: datetime,
    retention_hours: int = RETENTION_HOURS,
) -> None:
    """Validate the dedicated X artifact against one shared clock."""
    if not isinstance(document, dict) or set(document) != {"schema_version", "reports"}:
        raise ValueError("x_reports.json has an unexpected shape")
    if document["schema_version"] != SCHEMA_VERSION or not isinstance(
        document["reports"], list
    ):
        raise ValueError("x_reports.json has an unsupported schema")
    reference = _aware_utc(reference_time, "reference_time")
    cutoff = reference - timedelta(hours=retention_hours)
    status_ids: set[str] = set()
    urls: set[str] = set()
    for index, value in enumerate(document["reports"]):
        if not isinstance(value, dict):
            raise TypeError(f"x_reports.json.reports[{index}] must be an object")
        required = {
            "schema_version",
            "status_id",
            "account",
            "source_url",
            "published_at",
            "collected_at",
            "summary",
            "event_type",
            "source_class",
            "verification_status",
            "confidence",
            "latitude",
            "longitude",
            "location_name",
            "location_precision",
            "quoted_url",
            "reposted_url",
        }
        if set(value) != required:
            raise ValueError(f"x_reports.json.reports[{index}] has unexpected fields")
        if value["schema_version"] != SCHEMA_VERSION:
            raise ValueError("X report schema_version is invalid")
        canonical, account, status_id = canonical_x_url(str(value["source_url"]))
        if (
            canonical != value["source_url"]
            or account.casefold() != str(value["account"]).casefold()
        ):
            raise ValueError("source_url account must match report account")
        if (
            status_id != value["status_id"]
            or status_id in status_ids
            or canonical in urls
        ):
            raise ValueError("X report identity is invalid or duplicated")
        try:
            published = datetime.fromisoformat(
                str(value["published_at"]).replace("Z", "+00:00")
            )
            collected = datetime.fromisoformat(
                str(value["collected_at"]).replace("Z", "+00:00")
            )
        except ValueError as error:
            raise ValueError("X report timestamp is invalid") from error
        published = _aware_utc(published, "published_at")
        collected = _aware_utc(collected, "collected_at")
        if not cutoff <= published <= reference or collected > reference:
            raise ValueError("X report is outside the 72-hour publication window")
        if (
            value["event_type"] not in EVENT_TYPES
            or value["source_class"] not in SOURCE_CLASSES
        ):
            raise ValueError("X report classification is invalid")
        if (
            value["verification_status"] != "not_independently_verified"
            or value["location_precision"] not in LOCATION_PRECISIONS
            or not isinstance(value["summary"], str)
            or not value["summary"].strip()
            or not isinstance(value["location_name"], str)
            or not value["location_name"].strip()
        ):
            raise ValueError("X report metadata is invalid")
        confidence = value["confidence"]
        if (
            isinstance(confidence, bool)
            or not isinstance(confidence, (int, float))
            or not math.isfinite(confidence)
            or not 0 <= confidence <= 1
        ):
            raise ValueError("X report confidence is invalid")
        for field, limit in (("latitude", 90), ("longitude", 180)):
            coordinate = value[field]
            if (
                isinstance(coordinate, bool)
                or not isinstance(coordinate, (int, float))
                or not math.isfinite(coordinate)
                or abs(coordinate) > limit
            ):
                raise ValueError(f"X report {field} is invalid")
        status_ids.add(status_id)
        urls.add(canonical)


def build_x_report_document(
    events: list[dict], reference_time: datetime
) -> dict[str, object]:
    """Extract retained X metadata from Sentinel's shared event collection."""
    reports = [
        event["x_report"]
        for event in events
        if event.get("event_type") == "x_report"
        and isinstance(event.get("x_report"), dict)
    ]
    reports.sort(
        key=lambda item: (str(item["published_at"]), str(item["status_id"])),
        reverse=True,
    )
    document: dict[str, object] = {"schema_version": SCHEMA_VERSION, "reports": reports}
    validate_x_report_document(document, reference_time=reference_time)
    return document


def _stable_report_id(report: dict[str, object]) -> str:
    payload = json.dumps(
        [
            report.get("source_url"),
            report.get("account"),
            report.get("summary"),
            report.get("published_at"),
        ],
        ensure_ascii=False,
        separators=(",", ":"),
    )
    return f"x-report-{hashlib.sha256(payload.encode('utf-8')).hexdigest()[:20]}"


def build_x_website_artifacts(
    document: dict[str, object],
    reference_time: datetime,
) -> tuple[dict[str, object], dict[str, object]]:
    """Build the website's existing metadata and pinpoint compatibility layers."""
    generation = (
        reference_time.astimezone(UTC)
        .replace(microsecond=0)
        .isoformat()
        .replace("+00:00", "Z")
    )
    generation_id = f"sentinel-{generation.replace(':', '').replace('-', '')}"
    reports = document["reports"]
    assert isinstance(reports, list)
    features = []
    events = []
    for report in reports:
        assert isinstance(report, dict)
        normalized_report = {**report, "id": _stable_report_id(report)}
        events.append(
            {
                "id": f"x-event-{report['status_id']}",
                "title": f"Early report: {report['location_name']}",
                "summary": report["summary"],
                "reports": [normalized_report],
            }
        )
        features.append(
            {
                "type": "Feature",
                "id": normalized_report["id"],
                "geometry": {
                    "type": "Point",
                    "coordinates": [report["longitude"], report["latitude"]],
                },
                "properties": {
                    **normalized_report,
                    "layer": "Social Media Early Reports",
                },
            }
        )
    metadata = {
        "schema_version": SCHEMA_VERSION,
        "generation_id": generation_id,
        "generated_at": generation,
    }
    return (
        {**metadata, "events": events},
        {
            **metadata,
            "type": "FeatureCollection",
            "features": features,
        },
    )
