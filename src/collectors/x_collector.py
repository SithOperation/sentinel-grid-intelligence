"""Production X API v2 collector integrated with Sentinel events."""

from __future__ import annotations

import os
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from typing import Any, Protocol
from urllib.parse import urlencode

from api.x_api import (
    XApiTransport,
    XAuthenticationError,
    XCollectionError,
    XProviderError,
)
from models.x_report import EVENT_TYPES, SOURCE_CLASSES, XReport

API_ROOT = "https://api.x.com/2"


class Transport(Protocol):
    def get(self, url: str, bearer_token: str) -> Mapping[str, Any]: ...


@dataclass(frozen=True, slots=True)
class XAccount:
    handle: str
    source_class: str

    def __post_init__(self) -> None:
        normalized = self.handle.strip().lstrip("@")
        if (
            not normalized
            or len(normalized) > 15
            or not normalized.replace("_", "").isalnum()
        ):
            raise ValueError(f"invalid X account handle: {self.handle!r}")
        if self.source_class not in SOURCE_CLASSES:
            raise ValueError(f"unsupported X source class: {self.source_class}")
        object.__setattr__(self, "handle", normalized)


@dataclass(frozen=True, slots=True)
class AccountResult:
    account: str
    status: str
    posts_received: int
    reports_accepted: int
    error: str | None = None


@dataclass(frozen=True, slots=True)
class XCollectionResult:
    events: tuple[dict[str, object], ...]
    accounts: tuple[AccountResult, ...]

    @property
    def partial(self) -> bool:
        return any(item.status == "failed" for item in self.accounts)


def load_x_accounts(values: Sequence[Mapping[str, object]]) -> list[XAccount]:
    accounts: list[XAccount] = []
    for value in values:
        if value.get("enabled", True) is False:
            continue
        handle, source_class = value.get("handle"), value.get("source_class")
        if not isinstance(handle, str) or not isinstance(source_class, str):
            raise TypeError("X account configuration is invalid")
        accounts.append(XAccount(handle, source_class))
    if len({item.handle.casefold() for item in accounts}) != len(accounts):
        raise ValueError("X account handles must be unique")
    return accounts


class XCollector:
    """Collect configured accounts independently through official endpoints."""

    def __init__(
        self,
        accounts: Sequence[XAccount],
        keywords: Mapping[str, Sequence[str]],
        *,
        reference_time: datetime,
        bearer_token: str | None = None,
        transport: Transport | None = None,
        max_pages: int = 5,
        page_size: int = 100,
    ) -> None:
        if reference_time.tzinfo is None or reference_time.utcoffset() is None:
            raise ValueError("reference_time must be timezone-aware")
        if set(keywords) - EVENT_TYPES:
            raise ValueError("X keyword configuration contains unsupported event types")
        if any(
            not isinstance(words, (list, tuple))
            or not all(isinstance(word, str) and word.strip() for word in words)
            for words in keywords.values()
        ):
            raise TypeError("X keyword groups must contain non-empty strings")
        self.accounts = tuple(accounts)
        self.keywords = {
            event_type: tuple(word.casefold() for word in words)
            for event_type, words in keywords.items()
        }
        self.reference_time = reference_time.astimezone(UTC)
        self.token = (
            bearer_token
            if bearer_token is not None
            else os.environ.get("X_API_BEARER_TOKEN")
        )
        self.transport = transport or XApiTransport()
        self.max_pages = max_pages
        self.page_size = page_size

    def collect(self) -> XCollectionResult:
        if not self.token:
            raise XAuthenticationError(
                "X_API_BEARER_TOKEN is required for X collection"
            )
        events: list[dict[str, object]] = []
        outcomes: list[AccountResult] = []
        for account in self.accounts:
            try:
                reports, received = self._collect_account(account)
                events.extend(report.to_event() for report in reports)
                outcomes.append(
                    AccountResult(account.handle, "success", received, len(reports))
                )
            except XCollectionError as error:
                outcomes.append(
                    AccountResult(account.handle, "failed", 0, 0, str(error))
                )
            except (KeyError, TypeError, ValueError) as error:
                # All provider-shaped validation failures become source-specific
                # errors so a malformed account cannot abort other accounts.
                outcomes.append(
                    AccountResult(
                        account.handle,
                        "failed",
                        0,
                        0,
                        f"malformed X provider response: {error}",
                    )
                )
        if not outcomes or not any(item.status == "success" for item in outcomes):
            details = "; ".join(
                f"@{item.account}: {item.error}" for item in outcomes if item.error
            )
            raise XProviderError(
                f"X collection failed for all accounts{': ' + details if details else ''}"
            )
        return XCollectionResult(tuple(events), tuple(outcomes))

    def _collect_account(self, account: XAccount) -> tuple[list[XReport], int]:
        assert self.token is not None
        user = self.transport.get(
            f"{API_ROOT}/users/by/username/{account.handle}", self.token
        )
        user_data = user.get("data")
        if not isinstance(user_data, dict) or not isinstance(user_data.get("id"), str):
            raise XProviderError("user lookup response is missing data.id")
        cutoff = self.reference_time - timedelta(hours=48)
        parameters = {
            "max_results": str(self.page_size),
            "start_time": cutoff.isoformat().replace("+00:00", "Z"),
            "tweet.fields": "created_at,geo,referenced_tweets",
            "expansions": "geo.place_id,referenced_tweets.id,referenced_tweets.id.author_id",
            "place.fields": "full_name,geo",
            "user.fields": "username",
        }
        reports: list[XReport] = []
        received = 0
        next_token: str | None = None
        for _ in range(self.max_pages):
            query = dict(parameters)
            if next_token:
                query["pagination_token"] = next_token
            response = self.transport.get(
                f"{API_ROOT}/users/{user_data['id']}/tweets?{urlencode(query)}",
                self.token,
            )
            posts = response.get("data", [])
            if not isinstance(posts, list):
                raise XProviderError("timeline data must be an array")
            received += len(posts)
            reports.extend(self._reports_from_page(account, response, cutoff))
            meta = response.get("meta", {})
            if not isinstance(meta, dict):
                raise XProviderError("timeline meta must be an object")
            token = meta.get("next_token")
            if token is None:
                break
            if not isinstance(token, str) or not token:
                raise XProviderError("timeline next_token must be a non-empty string")
            next_token = token
        return reports, received

    def _reports_from_page(
        self,
        account: XAccount,
        response: Mapping[str, Any],
        cutoff: datetime,
    ) -> list[XReport]:
        posts, includes = response.get("data", []), response.get("includes", {})
        if not isinstance(posts, list) or not isinstance(includes, dict):
            raise XProviderError("timeline response has malformed data or includes")
        places = self._indexed_objects(includes.get("places", []), "places")
        users = self._indexed_objects(includes.get("users", []), "users")
        referenced = self._indexed_objects(includes.get("tweets", []), "tweets")
        reports = []
        for post in posts:
            if not isinstance(post, dict):
                raise XProviderError("timeline post must be an object")
            report = self._post_to_report(
                account, post, places, users, referenced, cutoff
            )
            if report is not None:
                reports.append(report)
        return reports

    @staticmethod
    def _indexed_objects(value: object, label: str) -> dict[str, Mapping[str, Any]]:
        if not isinstance(value, list):
            raise XProviderError(f"timeline includes.{label} must be an array")
        return {
            item["id"]: item
            for item in value
            if isinstance(item, dict) and isinstance(item.get("id"), str)
        }

    def _post_to_report(
        self,
        account: XAccount,
        post: Mapping[str, Any],
        places: Mapping[str, Mapping[str, Any]],
        users: Mapping[str, Mapping[str, Any]],
        referenced: Mapping[str, Mapping[str, Any]],
        cutoff: datetime,
    ) -> XReport | None:
        post_id, text, created_at = (
            post.get("id"),
            post.get("text"),
            post.get("created_at"),
        )
        if not isinstance(post_id, str) or not post_id:
            raise XProviderError("post is missing id, text, or created_at")
        if not isinstance(text, str) or not text:
            raise XProviderError("post is missing id, text, or created_at")
        if not isinstance(created_at, str) or not created_at:
            raise XProviderError("post is missing id, text, or created_at")
        try:
            published = datetime.fromisoformat(created_at.replace("Z", "+00:00"))
        except ValueError as error:
            raise XProviderError("post created_at is invalid") from error
        if published.tzinfo is None or published.utcoffset() is None:
            raise XProviderError("post created_at must include a timezone")
        published = published.astimezone(UTC)
        if published < cutoff or published > self.reference_time:
            return None
        geo = post.get("geo")
        place_id = geo.get("place_id") if isinstance(geo, dict) else None
        place = places.get(place_id) if isinstance(place_id, str) else None
        location = self._location_from_place(place)
        if location is None:
            return None
        quoted_url = reposted_url = None
        references = post.get("referenced_tweets", [])
        if not isinstance(references, list):
            raise XProviderError("referenced_tweets must be an array")
        for reference in references:
            if not isinstance(reference, dict):
                raise XProviderError("referenced tweet must be an object")
            ref_id, ref_type = reference.get("id"), reference.get("type")
            expanded = referenced.get(ref_id) if isinstance(ref_id, str) else None
            author_id = expanded.get("author_id") if expanded else None
            user = users.get(author_id) if isinstance(author_id, str) else None
            username = user.get("username") if user else None
            if not (isinstance(ref_id, str) and isinstance(username, str)):
                continue
            url = f"https://x.com/{username}/status/{ref_id}"
            if ref_type == "quoted":
                quoted_url = url
            elif ref_type == "retweeted":
                reposted_url = url
        return XReport(
            account=account.handle,
            source_url=f"https://x.com/{account.handle}/status/{post_id}",
            summary=text,
            published_at=published,
            collected_at=self.reference_time,
            source_class=account.source_class,
            event_type=self._classify(text),
            latitude=location[1],
            longitude=location[2],
            location_name=location[0],
            quoted_url=quoted_url,
            reposted_url=reposted_url,
        )

    def _classify(self, text: str) -> str:
        normalized = text.casefold()
        for event_type, keywords in self.keywords.items():
            if any(keyword in normalized for keyword in keywords):
                return event_type
        return "unclassified_early_report"

    @staticmethod
    def _location_from_place(
        place: Mapping[str, Any] | None,
    ) -> tuple[str, float, float] | None:
        if place is None or not isinstance(place.get("full_name"), str):
            return None
        geo = place.get("geo")
        bbox = geo.get("bbox") if isinstance(geo, dict) else None
        if (
            not isinstance(bbox, list)
            or len(bbox) != 4
            or any(
                isinstance(value, bool) or not isinstance(value, (int, float))
                for value in bbox
            )
        ):
            raise XProviderError("X place bounding box is invalid")
        west, south, east, north = (float(value) for value in bbox)
        if not (
            -180 <= west <= 180 and -180 <= east <= 180 and -90 <= south <= north <= 90
        ):
            raise XProviderError("X place bounding box is outside coordinate bounds")
        latitude = (south + north) / 2
        if west <= east:
            longitude = (west + east) / 2
        else:
            longitude = ((west + east + 360) / 2 + 180) % 360 - 180
        return place["full_name"], latitude, longitude
