"""Fixture-testable parsers for optional source discovery paths."""

from __future__ import annotations

import json
import re
from collections.abc import Iterable, Iterator, Mapping
from datetime import UTC, datetime
from email.utils import parsedate_to_datetime
from html.parser import HTMLParser
from typing import Any
from xml.etree import ElementTree

from sources.canonical import canonicalize_url
from sources.models import DiscoveredItem


def _timestamp(value: object) -> datetime | None:
    if not isinstance(value, str) or not value.strip():
        return None
    try:
        parsed = datetime.fromisoformat(value.strip().replace("Z", "+00:00"))
    except ValueError:
        try:
            parsed = parsedate_to_datetime(value.strip())
        except (TypeError, ValueError):
            return None
    if parsed.tzinfo is None or parsed.utcoffset() is None:
        return None
    return parsed.astimezone(UTC)


def manual_items(
    source_id: str,
    platform: str,
    values: Iterable[Mapping[str, object]],
    discovered_at: datetime,
) -> list[DiscoveredItem]:
    items = []
    for value in values:
        url = canonicalize_url(str(value.get("url", "")))
        items.append(
            DiscoveredItem(
                source_id=source_id,
                platform=platform,
                canonical_url=url,
                platform_item_id=(
                    str(value["platform_item_id"])
                    if value.get("platform_item_id") is not None
                    else None
                ),
                published_at=_timestamp(value.get("published_at")),
                discovered_at=discovered_at,
                title=str(value["title"]) if value.get("title") else None,
                text=str(value.get("text", "")),
                media_type=str(value.get("media_type", "external")),
            )
        )
    return items


def parse_rss(
    source_id: str,
    payload: str,
    discovered_at: datetime,
) -> list[DiscoveredItem]:
    try:
        root = ElementTree.fromstring(payload)
    except ElementTree.ParseError as error:
        raise ValueError("RSS or Atom response is malformed") from error
    items = []
    candidates = root.findall(".//item")
    if not candidates:
        candidates = root.findall(".//{*}entry")
    for entry in candidates:
        link = entry.findtext("link")
        if not link:
            link_node = entry.find("{*}link")
            link = link_node.get("href") if link_node is not None else None
        if not link:
            continue
        title = entry.findtext("title") or entry.findtext("{*}title")
        text = (
            entry.findtext("description")
            or entry.findtext("{*}summary")
            or entry.findtext("{*}content")
            or title
            or ""
        )
        published = (
            entry.findtext("pubDate")
            or entry.findtext("{*}published")
            or entry.findtext("{*}updated")
        )
        identifier = entry.findtext("guid") or entry.findtext("{*}id")
        items.extend(
            manual_items(
                source_id,
                "rss",
                [
                    {
                        "url": link,
                        "platform_item_id": identifier,
                        "published_at": published,
                        "title": title,
                        "text": text,
                        "media_type": "article",
                    }
                ],
                discovered_at,
            )
        )
    return items


class _LinkParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.links: list[tuple[str, str]] = []
        self._href: str | None = None
        self._parts: list[str] = []

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        if tag.casefold() == "a":
            values = dict(attrs)
            self._href = values.get("href")
            self._parts = []

    def handle_data(self, data: str) -> None:
        if self._href is not None:
            self._parts.append(data)

    def handle_endtag(self, tag: str) -> None:
        if tag.casefold() == "a" and self._href is not None:
            self.links.append((self._href, " ".join(self._parts)))
            self._href = None
            self._parts = []


def parse_website_links(
    source_id: str,
    payload: str,
    discovered_at: datetime,
    *,
    allowed_host: str,
) -> list[DiscoveredItem]:
    parser = _LinkParser()
    parser.feed(payload)
    values = []
    for href, text in parser.links:
        try:
            url = canonicalize_url(href)
        except ValueError:
            continue
        if allowed_host.casefold() not in url.casefold() or not text.strip():
            continue
        values.append(
            {"url": url, "title": text, "text": text, "media_type": "article"}
        )
    return manual_items(source_id, "website", values, discovered_at)


def parse_reddit_listing(
    source_id: str,
    payload: str,
    discovered_at: datetime,
) -> list[DiscoveredItem]:
    value = json.loads(payload)
    children = value.get("data", {}).get("children", [])
    values = []
    for child in children:
        data = child.get("data", {}) if isinstance(child, dict) else {}
        permalink = data.get("permalink")
        if not isinstance(permalink, str):
            continue
        values.append(
            {
                "url": f"https://reddit.com{permalink}",
                "platform_item_id": data.get("id"),
                "published_at": datetime.fromtimestamp(
                    float(data.get("created_utc", 0)), tz=UTC
                ).isoformat(),
                "title": data.get("title"),
                "text": data.get("selftext") or data.get("title") or "",
                "media_type": "video" if data.get("is_video") else "external",
            }
        )
    return manual_items(source_id, "reddit", values, discovered_at)


def _walk(value: object) -> Iterator[Mapping[str, Any]]:
    if isinstance(value, dict):
        yield value
        for child in value.values():
            yield from _walk(child)
    elif isinstance(value, list):
        for child in value:
            yield from _walk(child)


def parse_x_syndication(
    source_id: str,
    account: str,
    payload: str,
    discovered_at: datetime,
) -> list[DiscoveredItem]:
    match = re.search(r"__NEXT_DATA__[^>]*>(.*?)</script>", payload, re.DOTALL)
    if match is None:
        raise ValueError("X syndication response has no embedded timeline data")
    value = json.loads(match.group(1))
    values: list[dict[str, object]] = []
    seen: set[str] = set()
    for candidate in _walk(value):
        status_id = candidate.get("id_str") or candidate.get("rest_id")
        text = candidate.get("full_text") or candidate.get("text")
        created = candidate.get("created_at")
        if (
            not isinstance(status_id, str)
            or not status_id.isdigit()
            or status_id in seen
            or not isinstance(text, str)
            or not isinstance(created, str)
        ):
            continue
        seen.add(status_id)
        values.append(
            {
                "url": f"https://x.com/{account}/status/{status_id}",
                "platform_item_id": status_id,
                "published_at": created,
                "text": text,
                "media_type": "external",
            }
        )
    return manual_items(source_id, "x", values, discovered_at)
