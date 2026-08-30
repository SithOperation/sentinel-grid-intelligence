"""Public European security RSS/Atom correlation collector.

Feed text is treated as untrusted reporting, never as executable content or as
proof of a claim. Locations come only from the controlled table below.
"""

from __future__ import annotations

import hashlib
import html
import json
import os
import re
import xml.etree.ElementTree as ET
from dataclasses import dataclass, field
from datetime import UTC, datetime
from difflib import SequenceMatcher
from html.parser import HTMLParser
from pathlib import Path
from urllib.parse import urlsplit

import requests
import yaml

from collectors.hazard_common import CollectionResult
from models.event_model import create_event
from sources.canonical import canonicalize_url

USER_AGENT = "SentinelGrid/1.0 (+public OSINT RSS collector)"
ALLOWED_STATUSES = {
    "unverified",
    "single_source",
    "developing",
    "corroborated",
    "officially_reported",
    "confirmed",
    "disputed",
    "retracted",
}
RELIABILITY_BASE = {
    "low_medium": 0.25,
    "medium": 0.35,
    "medium_high": 0.45,
    "high": 0.55,
    "very_high": 0.65,
}
LOCATIONS = {
    "warsaw": ("Poland", "Warsaw", 52.2297, 21.0122, "city"),
    "kaliningrad": ("Russia", "Kaliningrad", 54.7104, 20.4522, "city"),
    "suwalki gap": ("Poland/Lithuania", "Suwalki Gap", 54.10, 23.20, "region"),
    "suwałki": ("Poland", "Suwalki", 54.1115, 22.9308, "city"),
    "baltic sea": ("International", "Baltic Sea", 57.0, 19.0, "region"),
    "black sea": ("International", "Black Sea", 43.5, 34.0, "region"),
    "belarus": ("Belarus", "Country-level", 53.7, 27.9, "country"),
    "lithuania": ("Lithuania", "Country-level", 55.2, 23.9, "country"),
    "latvia": ("Latvia", "Country-level", 56.9, 24.6, "country"),
    "estonia": ("Estonia", "Country-level", 58.6, 25.0, "country"),
    "finland": ("Finland", "Country-level", 64.0, 26.0, "country"),
    "sweden": ("Sweden", "Country-level", 62.0, 15.0, "country"),
    "poland": ("Poland", "Country-level", 52.1, 19.4, "country"),
    "ukraine": ("Ukraine", "Country-level", 49.0, 31.4, "country"),
}


class _TextAndLinks(HTMLParser):
    def __init__(self):
        super().__init__()
        self.text: list[str] = []
        self.links: list[str] = []

    def handle_data(self, data):
        self.text.append(data)

    def handle_starttag(self, tag, attrs):
        if tag.casefold() == "a":
            href = dict(attrs).get("href")
            if href:
                self.links.append(href)


def sanitize(value: object, limit: int = 2000) -> str:
    parser = _TextAndLinks()
    parser.feed(html.unescape(str(value or "")))
    return re.sub(r"\s+", " ", " ".join(parser.text)).strip()[:limit]


def _tag(element, name):
    return next(
        (child for child in element if child.tag.rsplit("}", 1)[-1] == name), None
    )


def _text(element, *names):
    for name in names:
        child = _tag(element, name)
        if child is not None and child.text:
            return child.text.strip()
    return ""


def parse_date(value: str, fallback: datetime) -> datetime:
    from email.utils import parsedate_to_datetime

    try:
        parsed = parsedate_to_datetime(value)
    except (TypeError, ValueError, OverflowError):
        try:
            parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
        except (TypeError, ValueError):
            return fallback
    return (
        parsed.replace(tzinfo=UTC) if parsed.tzinfo is None else parsed.astimezone(UTC)
    )


@dataclass
class Observation:
    source_id: str
    source_name: str
    source_type: str
    source_perspective: str
    reliability: str
    title: str
    description: str
    post_url: str
    external_url: str
    canonical_source_url: str
    published: datetime
    subreddit: str | None = None
    author: str | None = None
    flair: str | None = None
    score: int | None = None
    comment_count: int | None = None
    category: str = "unknown"
    actor_reporting: str = "UNKNOWN"
    actor_subject: str = "UNKNOWN"
    location: dict | None = None
    matched_terms: dict = field(default_factory=dict)


def parse_feed(
    payload: bytes | str, source: dict, reference_time: datetime
) -> list[Observation]:
    root = ET.fromstring(payload)
    entries = [
        node for node in root.iter() if node.tag.rsplit("}", 1)[-1] in {"item", "entry"}
    ]
    observations = []
    for entry in entries[: int(source.get("max_items", 50))]:
        title = sanitize(_text(entry, "title"), 500)
        raw_content = _text(entry, "description", "summary", "content")
        description = sanitize(raw_content)
        link_node = _tag(entry, "link")
        post_url = ""
        if link_node is not None:
            post_url = link_node.attrib.get("href", "") or (link_node.text or "")
        post_url = post_url or _text(entry, "guid", "id")
        parser = _TextAndLinks()
        parser.feed(html.unescape(raw_content))
        is_reddit = source.get("source_type") == "reddit"
        external = post_url
        if is_reddit:
            external = next(
                (
                    url
                    for url in parser.links
                    if "reddit.com" not in urlsplit(url).netloc.casefold()
                ),
                post_url,
            )
        try:
            post_url = canonicalize_url(post_url)
            external = canonicalize_url(external)
        except ValueError:
            continue
        published = parse_date(
            _text(entry, "pubDate", "published", "updated"), reference_time
        )
        author = sanitize(_text(entry, "author"), 100) or None
        observations.append(
            Observation(
                source_id=str(source["id"]),
                source_name=str(source["name"]),
                source_type=str(source["source_type"]),
                source_perspective=str(source["source_perspective"]),
                reliability=str(source["reliability"]),
                title=title,
                description=description,
                post_url=post_url,
                external_url=external,
                canonical_source_url=external,
                published=published,
                subreddit=source.get("subreddit"),
                author=author,
                flair=sanitize(_text(entry, "category"), 100) or None,
            )
        )
    return observations


def classify(observation: Observation, terms: dict) -> bool:
    text = f"{observation.title} {observation.description}".casefold()
    matched = {
        group: [term for term in values if term.casefold() in text]
        for group, values in terms.items()
    }
    observation.matched_terms = {key: value for key, value in matched.items() if value}
    if (
        not matched.get("geography")
        and not matched.get("nato")
        and not matched.get("russia")
    ):
        return False
    if not matched.get("military_activity") and not any(
        term in text for term in ("security", "defence", "defense", "war")
    ):
        return False
    rules = [
        ("airspace_incident", ("airspace violation", "airspace incursion")),
        ("missile_activity", ("missile", "rocket")),
        ("drone_activity", ("drone", "uav")),
        ("naval_activity", ("naval", "fleet", "warship", "baltic sea", "black sea")),
        (
            "air_activity",
            ("aircraft", "bomber", "fighter", "awacs", "intercept", "scrambled"),
        ),
        ("military_exercise", ("exercise", "drill", "war game")),
        ("mobilization", ("mobilization", "mobilisation")),
        ("military_deployment", ("deployment", "troop movement", "military convoy")),
        ("border_incident", ("border incident", "border crossing")),
        ("cyber_activity", ("cyber",)),
        ("security_warning", ("warning", "alert")),
        ("polish_military_activity", ("polish military", "polish armed forces")),
        (
            "russian_activity",
            tuple(term.casefold() for term in terms.get("russia", [])),
        ),
        ("nato_activity", tuple(term.casefold() for term in terms.get("nato", []))),
    ]
    observation.category = next(
        (category for category, needles in rules if any(n in text for n in needles)),
        "military_statement",
    )
    perspective_actor = {
        "nato_official": "NATO",
        "polish_official": "POLAND",
        "russian_official": "RUSSIA",
        "russian_state_media": "RUSSIA",
    }
    observation.actor_reporting = perspective_actor.get(
        observation.source_perspective, "UNKNOWN"
    )
    subjects = [
        ("NATO", matched.get("nato")),
        ("RUSSIA", matched.get("russia")),
        ("POLAND", ["poland"] if "poland" in text else []),
        ("BELARUS", ["belarus"] if "belarus" in text else []),
        ("UKRAINE", ["ukraine"] if "ukraine" in text else []),
    ]
    observation.actor_subject = next(
        (
            actor
            for actor, hits in subjects
            if hits and actor != observation.actor_reporting
        ),
        next((actor for actor, hits in subjects if hits), "UNKNOWN"),
    )
    for term, value in LOCATIONS.items():
        if term in text:
            country, region, lat, lon, precision = value
            observation.location = {
                "country": country,
                "region": region,
                "latitude": lat,
                "longitude": lon,
                "precision": precision,
                "method": "controlled_term_table",
            }
            break
    return True


def _title_key(value: str) -> str:
    words = re.findall(r"[a-z0-9]+", value.casefold())
    return " ".join(
        word
        for word in words
        if word not in {"the", "a", "an", "to", "of", "in", "on", "and"}
    )


def _same_event(left: Observation, right: Observation) -> bool:
    if left.canonical_source_url == right.canonical_source_url:
        return True
    if (
        left.category != right.category
        or abs((left.published - right.published).total_seconds()) > 86400
    ):
        return False
    if (
        left.location
        and right.location
        and left.location.get("region") != right.location.get("region")
    ):
        return False
    return (
        SequenceMatcher(None, _title_key(left.title), _title_key(right.title)).ratio()
        >= 0.72
    )


def confidence_for(reports: list[Observation]) -> tuple[float, str, int, int]:
    unique_urls = {item.canonical_source_url for item in reports}
    domains = {urlsplit(url).netloc for url in unique_urls}
    direct = [item for item in reports if item.source_type != "reddit"]
    bases = [RELIABILITY_BASE.get(item.reliability, 0.3) for item in direct or reports]
    confidence = max(bases, default=0.2)
    if len(domains) > 1:
        confidence += min(0.22, 0.10 * (len(domains) - 1))
    official = any(item.source_type == "official" for item in reports)
    if official and len(domains) > 1:
        confidence += 0.10
    confidence = min(0.92, round(confidence, 2))
    if official and len(domains) == 1:
        status = "officially_reported"
    elif len(domains) >= 2:
        status = "corroborated" if confidence >= 0.65 else "developing"
    elif all(item.source_type == "reddit" for item in reports):
        status = "unverified" if confidence < 0.3 else "single_source"
    else:
        status = "single_source"
    return confidence, status, len(unique_urls), len(domains)


def cluster_observations(observations: list[Observation]) -> list[list[Observation]]:
    clusters: list[list[Observation]] = []
    for observation in sorted(observations, key=lambda item: item.published):
        cluster = next(
            (items for items in clusters if _same_event(items[0], observation)), None
        )
        if cluster is None:
            clusters.append([observation])
        else:
            cluster.append(observation)
    return clusters


def normalize_cluster(reports: list[Observation]) -> dict:
    lead = max(
        reports,
        key=lambda item: (
            item.source_type == "official",
            RELIABILITY_BASE.get(item.reliability, 0),
        ),
    )
    confidence, status, source_count, independent_count = confidence_for(reports)
    first_seen, last_seen = (
        min(item.published for item in reports),
        max(item.published for item in reports),
    )
    digest = hashlib.sha256(
        "|".join(sorted({item.canonical_source_url for item in reports})).encode()
    ).hexdigest()[:12]
    prefix = (
        "A Reddit post claims"
        if lead.source_type == "reddit"
        else f"{lead.source_name} reported"
    )
    breaking_terms = (
        "airspace violation",
        "border crossing",
        "missile impact",
        "article 4",
        "article 5",
        "mobilization",
        "nato response",
        "nuclear forces",
        "strategic bomber",
        "mass drone attack",
        "large military exercise",
    )
    combined_text = " ".join(
        f"{item.title} {item.description}" for item in reports
    ).casefold()
    official = any(item.source_type == "official" for item in reports)
    breaking = any(term in combined_text for term in breaking_terms) and (
        independent_count >= 2 or (official and len(reports) >= 2)
    )
    europe_layers = {lead.category}
    actors = {item.actor_subject for item in reports}
    country = (lead.location or {}).get("country")
    if "NATO" in actors:
        europe_layers.add("nato_activity")
    if "RUSSIA" in actors:
        europe_layers.add("russian_activity")
    if country in {
        "Poland",
        "Poland/Lithuania",
        "Lithuania",
        "Latvia",
        "Estonia",
        "Finland",
    }:
        europe_layers.add("eastern_flank")
    if country == "Ukraine":
        europe_layers.add("ukraine_war")
    if lead.category in {"missile_activity", "drone_activity"}:
        europe_layers.add("missile_drone")
    if any(item.source_type == "reddit" for item in reports):
        europe_layers.add("reddit_osint")
    event = create_event(
        "europe_security",
        lead.category,
        lead.title,
        f"{prefix}: {lead.description or lead.title}",
        [lead.source_name],
        "high" if confidence >= 0.75 else "medium",
        lead.location,
        round(confidence * 100),
    )
    event.update(
        {
            "event_id": f"SG-EU-{digest}",
            "timestamp": last_seen.isoformat(),
            "first_seen": first_seen.isoformat(),
            "last_seen": last_seen.isoformat(),
            "status": status,
            "actor": lead.actor_subject,
            "actors": sorted(
                {
                    item.actor_subject
                    for item in reports
                    if item.actor_subject != "UNKNOWN"
                }
            ),
            "actor_reporting": lead.actor_reporting,
            "actor_subject": lead.actor_subject,
            "source_url": lead.canonical_source_url,
            "url": lead.canonical_source_url,
            "source_type": lead.source_type,
            "source_perspective": lead.source_perspective,
            "source_count": source_count,
            "independent_source_count": independent_count,
            "source_types": sorted({item.source_type for item in reports}),
            "source_domains": sorted(
                {urlsplit(item.post_url).netloc for item in reports}
            ),
            "original_source_domains": sorted(
                {urlsplit(item.canonical_source_url).netloc for item in reports}
            ),
            "event_cluster_id": f"EU-{digest}",
            "verification": {
                "confirmed": status == "confirmed",
                "source_count": independent_count,
            },
            "europe_layers": sorted(europe_layers),
            "metadata": {
                "observation_count": len(reports),
                "location_precision": (lead.location or {}).get("precision"),
                "matched_terms": lead.matched_terms,
                "breaking": breaking,
                "reports": [
                    {
                        "source": item.source_name,
                        "subreddit": item.subreddit,
                        "post_title": item.title,
                        "post_url": item.post_url,
                        "external_url": item.external_url,
                        "author": item.author,
                        "published": item.published.isoformat(),
                        "score": item.score,
                        "comment_count": item.comment_count,
                        "post_flair": item.flair,
                    }
                    for item in reports
                ],
            },
        }
    )
    return event


def load_europe_config(path: str | Path) -> dict:
    value = yaml.safe_load(Path(path).read_text(encoding="utf-8")) or {}
    if not isinstance(value.get("sources"), list) or not isinstance(
        value.get("terms"), dict
    ):
        raise TypeError("Europe security configuration requires sources and terms")
    return value


def _load_state(path: str | Path | None) -> dict:
    if not path or not Path(path).is_file():
        return {"sources": {}}
    try:
        value = json.loads(Path(path).read_text(encoding="utf-8"))
        return value if isinstance(value.get("sources"), dict) else {"sources": {}}
    except (OSError, TypeError, ValueError):
        return {"sources": {}}


def _save_state(path: str | Path | None, state: dict) -> None:
    if not path:
        return
    target = Path(path)
    target.parent.mkdir(parents=True, exist_ok=True)
    temporary = target.with_name(f".{target.name}.{os.getpid()}.tmp")
    temporary.write_text(json.dumps(state, indent=2), encoding="utf-8")
    os.replace(temporary, target)


def collect_europe_security(
    config: dict,
    reference_time: datetime,
    *,
    transport=requests.get,
    state_path: str | Path | None = None,
) -> CollectionResult:
    observations: list[Observation] = []
    errors = []
    received = 0
    state = _load_state(state_path)
    for source in config["sources"]:
        if not source.get("enabled", True):
            continue
        try:
            source_state = state["sources"].setdefault(source["id"], {})
            headers = {
                "User-Agent": USER_AGENT,
                "Accept": "application/rss+xml, application/atom+xml, application/xml;q=0.9",
            }
            if source_state.get("etag"):
                headers["If-None-Match"] = source_state["etag"]
            if source_state.get("last_modified"):
                headers["If-Modified-Since"] = source_state["last_modified"]
            response = transport(source["url"], headers=headers, timeout=(5, 15))
            if getattr(response, "status_code", None) == 304:
                continue
            response.raise_for_status()
            payload = response.content
            if len(payload) > int(config.get("max_response_bytes", 2_000_000)):
                raise ValueError("feed exceeds configured size limit")
            parsed = parse_feed(payload, source, reference_time)
            received += len(parsed)
            seen = set(source_state.get("seen", []))
            fresh = []
            for item in parsed:
                item_id = hashlib.sha256(
                    f"{item.post_url}|{item.published.isoformat()}".encode()
                ).hexdigest()
                if item_id not in seen:
                    fresh.append(item)
                    seen.add(item_id)
            observations.extend(
                item for item in fresh if classify(item, config["terms"])
            )
            response_headers = getattr(response, "headers", {})
            source_state.update(
                {
                    "etag": response_headers.get("ETag"),
                    "last_modified": response_headers.get("Last-Modified"),
                    "last_success": reference_time.isoformat(),
                    "failure_count": 0,
                    "items_received": len(parsed),
                    "seen": list(seen)[-5000:],
                }
            )
        except Exception as error:
            errors.append(f"{source.get('id', 'unknown')}: {error}")
            source_state = state["sources"].setdefault(source.get("id", "unknown"), {})
            source_state["last_failure"] = reference_time.isoformat()
            source_state["failure_count"] = (
                int(source_state.get("failure_count", 0)) + 1
            )
    _save_state(state_path, state)
    clusters = cluster_observations(observations)
    events = [normalize_cluster(cluster) for cluster in clusters]
    status = (
        "partial"
        if errors and events
        else "error"
        if errors
        else "ok"
        if events
        else "no_data"
    )
    return CollectionResult(
        events=events,
        status=status,
        error="; ".join(errors) or None,
        metrics={
            "sources_configured": len(config["sources"]),
            "items_received": received,
            "relevant_observations": len(observations),
            "event_clusters": len(events),
            "source_failures": len(errors),
        },
    )
