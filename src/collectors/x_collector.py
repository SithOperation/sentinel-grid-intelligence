"""Explicit-public-URL X collector integrated with Sentinel events."""

from __future__ import annotations

import json
import os
import time
from collections import Counter
from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Protocol

from api.x_public import (
    PublicPage,
    PublicPost,
    XCollectionError,
    XMetadataError,
    XUnavailableError,
    extract_public_post,
)
from models.x_report import (
    EVENT_TYPES,
    LOCATION_PRECISIONS,
    SOURCE_CLASSES,
    XReport,
    canonical_x_url,
)


class Transport(Protocol):
    def fetch(self, url: str) -> PublicPage: ...


@dataclass(frozen=True, slots=True)
class XStatusURL:
    url: str
    source_class: str
    location_name: str
    latitude: float
    longitude: float
    location_precision: str
    event_type: str

    def __post_init__(self) -> None:
        canonical, _, _ = canonical_x_url(self.url)
        if self.source_class not in SOURCE_CLASSES:
            raise ValueError(f"unsupported X source class: {self.source_class}")
        if self.event_type not in EVENT_TYPES:
            raise ValueError(f"unsupported X event type: {self.event_type}")
        if self.location_precision not in LOCATION_PRECISIONS:
            raise ValueError(
                f"unsupported X location precision: {self.location_precision}"
            )
        if not self.location_name.strip():
            raise ValueError("X location_name must be non-empty")
        if (
            isinstance(self.latitude, bool)
            or not isinstance(self.latitude, (int, float))
            or not -90 <= self.latitude <= 90
            or isinstance(self.longitude, bool)
            or not isinstance(self.longitude, (int, float))
            or not -180 <= self.longitude <= 180
        ):
            raise ValueError("X configured coordinates are invalid")
        object.__setattr__(self, "url", canonical)

    @property
    def status_id(self) -> str:
        return canonical_x_url(self.url)[2]


@dataclass(frozen=True, slots=True)
class URLResult:
    url: str
    status: str
    reason: str | None = None


@dataclass(frozen=True, slots=True)
class XCollectionResult:
    events: tuple[dict[str, object], ...]
    urls: tuple[URLResult, ...]
    configured_count: int
    fetched_count: int
    accepted_count: int
    rejected_count: int
    unavailable_count: int
    cached_count: int
    failure_reasons: Mapping[str, int]

    @property
    def partial(self) -> bool:
        return bool(self.events) and any(
            item.status in {"rejected", "unavailable"} for item in self.urls
        )

    @property
    def total_failure(self) -> bool:
        return bool(self.urls) and not self.events

    def health_metrics(self) -> dict[str, object]:
        return {
            "configured_url_count": self.configured_count,
            "fetched_count": self.fetched_count,
            "accepted_count": self.accepted_count,
            "rejected_count": self.rejected_count,
            "unavailable_count": self.unavailable_count,
            "cached_count": self.cached_count,
            "failure_reasons": dict(self.failure_reasons),
        }


def load_x_urls(values: Sequence[Mapping[str, object]]) -> list[XStatusURL]:
    urls: list[XStatusURL] = []
    for value in values:
        if value.get("enabled", True) is False:
            continue
        required = {
            "url": str,
            "source_class": str,
            "location_name": str,
            "latitude": (int, float),
            "longitude": (int, float),
            "location_precision": str,
            "event_type": str,
        }
        for key, expected in required.items():
            if (
                key not in value
                or isinstance(value[key], bool)
                or not isinstance(value[key], expected)
            ):
                raise TypeError(f"X URL configuration field {key!r} is invalid")
        latitude = value["latitude"]
        longitude = value["longitude"]
        assert isinstance(latitude, (int, float))
        assert isinstance(longitude, (int, float))
        urls.append(
            XStatusURL(
                url=str(value["url"]),
                source_class=str(value["source_class"]),
                location_name=str(value["location_name"]),
                latitude=float(latitude),
                longitude=float(longitude),
                location_precision=str(value["location_precision"]),
                event_type=str(value["event_type"]),
            )
        )
    status_ids = [item.status_id for item in urls]
    if len(set(status_ids)) != len(status_ids):
        raise ValueError("configured X status IDs must be unique")
    return urls


class XCollector:
    """Collect only explicitly configured public status URLs."""

    def __init__(
        self,
        urls: Sequence[XStatusURL],
        *,
        reference_time: datetime,
        transport: Transport,
        cache_path: Path,
        request_interval_seconds: float = 2,
        max_urls_per_run: int = 25,
        sleeper: Callable[[float], None] = time.sleep,
    ) -> None:
        if reference_time.tzinfo is None or reference_time.utcoffset() is None:
            raise ValueError("reference_time must be timezone-aware")
        if request_interval_seconds < 0:
            raise ValueError("X request interval cannot be negative")
        if max_urls_per_run < 1:
            raise ValueError("X maximum URLs per run must be positive")
        self.urls = tuple(urls[:max_urls_per_run])
        self.configured_count = len(urls)
        self.reference_time = reference_time.astimezone(UTC)
        self.transport = transport
        self.cache_path = cache_path
        self.request_interval_seconds = request_interval_seconds
        self.sleeper = sleeper

    def collect(self) -> XCollectionResult:
        cache = self._load_cache()
        events: list[dict[str, object]] = []
        outcomes: list[URLResult] = []
        failures: Counter[str] = Counter()
        fetched = accepted = rejected = unavailable = cached = 0
        fetch_number = 0
        cutoff = self.reference_time - timedelta(hours=72)

        for configured in self.urls:
            try:
                post = self._cached_post(cache, configured)
                fetched_post = False
                if post is not None:
                    cached += 1
                    outcome_status = "cached"
                else:
                    if fetch_number:
                        self.sleeper(self.request_interval_seconds)
                    fetch_number += 1
                    fetched += 1
                    page = self.transport.fetch(configured.url)
                    post = extract_public_post(page)
                    fetched_post = True
                    outcome_status = "accepted"
                report = self._to_report(configured, post)
                if (
                    report.published_at < cutoff
                    or report.published_at > self.reference_time
                ):
                    raise XMetadataError("post is outside the rolling 72-hour window")
                if fetched_post:
                    cache[configured.status_id] = {
                        "canonical_url": post.canonical_url,
                        "account": post.account,
                        "text": post.text,
                        "published_at": post.published_at,
                        "fetched_at": self.reference_time.isoformat(),
                    }
                events.append(report.to_event())
                accepted += 1
                outcomes.append(URLResult(configured.url, outcome_status))
            except XUnavailableError as error:
                unavailable += 1
                failures[str(error)] += 1
                outcomes.append(URLResult(configured.url, "unavailable", str(error)))
            except (XCollectionError, OSError, TypeError, ValueError) as error:
                rejected += 1
                failures[str(error)] += 1
                outcomes.append(URLResult(configured.url, "rejected", str(error)))

        if accepted:
            self._save_cache(cache)
        return XCollectionResult(
            events=tuple(events),
            urls=tuple(outcomes),
            configured_count=self.configured_count,
            fetched_count=fetched,
            accepted_count=accepted,
            rejected_count=rejected,
            unavailable_count=unavailable,
            cached_count=cached,
            failure_reasons=dict(sorted(failures.items())),
        )

    def _to_report(self, configured: XStatusURL, post: PublicPost) -> XReport:
        try:
            published = datetime.fromisoformat(post.published_at.replace("Z", "+00:00"))
        except ValueError as error:
            raise XMetadataError("public metadata timestamp is invalid") from error
        if published.tzinfo is None or published.utcoffset() is None:
            raise XMetadataError("public metadata timestamp must include a timezone")
        return XReport(
            account=post.account,
            source_url=post.canonical_url,
            summary=post.text,
            published_at=published,
            collected_at=self.reference_time,
            source_class=configured.source_class,
            event_type=configured.event_type,
            latitude=configured.latitude,
            longitude=configured.longitude,
            location_name=configured.location_name,
            location_precision=configured.location_precision,
        )

    def _load_cache(self) -> dict[str, dict[str, object]]:
        try:
            value = json.loads(self.cache_path.read_text(encoding="utf-8"))
        except FileNotFoundError:
            return {}
        except (json.JSONDecodeError, OSError):
            return {}
        if not isinstance(value, dict) or not isinstance(value.get("posts"), dict):
            return {}
        return {
            str(key): item
            for key, item in value["posts"].items()
            if isinstance(item, dict)
        }

    @staticmethod
    def _cached_post(
        cache: Mapping[str, Mapping[str, object]], configured: XStatusURL
    ) -> PublicPost | None:
        item = cache.get(configured.status_id)
        if not item or item.get("canonical_url") != configured.url:
            return None
        fields = ("canonical_url", "account", "text", "published_at")
        if not all(isinstance(item.get(field), str) for field in fields):
            return None
        canonical_url = item["canonical_url"]
        account = item["account"]
        text = item["text"]
        published_at = item["published_at"]
        assert isinstance(canonical_url, str)
        assert isinstance(account, str)
        assert isinstance(text, str)
        assert isinstance(published_at, str)
        try:
            canonical, url_account, status_id = canonical_x_url(canonical_url)
        except ValueError:
            return None
        if (
            canonical != configured.url
            or status_id != configured.status_id
            or url_account.casefold() != account.casefold()
            or not text.strip()
            or not published_at.strip()
        ):
            return None
        return PublicPost(
            status_id=status_id,
            canonical_url=canonical,
            account=account,
            text=text,
            published_at=published_at,
        )

    def _save_cache(self, cache: Mapping[str, Mapping[str, object]]) -> None:
        self.cache_path.parent.mkdir(parents=True, exist_ok=True)
        temporary = self.cache_path.with_name(
            f".{self.cache_path.name}.{os.getpid()}.tmp"
        )
        payload = {"schema_version": "1.0", "posts": cache}
        try:
            temporary.write_text(
                json.dumps(payload, ensure_ascii=False, indent=2) + "\n",
                encoding="utf-8",
            )
            os.replace(temporary, self.cache_path)
        finally:
            try:
                temporary.unlink()
            except FileNotFoundError:
                pass
