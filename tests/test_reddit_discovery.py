from datetime import UTC, datetime
from pathlib import Path

from sources.feed import build_source_feed
from sources.reddit import discover_reddit_sources, reddit_map_events
from sources.registry import load_registry

NOW = datetime(2026, 7, 28, 12, tzinfo=UTC)
ROOT = Path(__file__).resolve().parents[1]


class Response:
    status_code = 200

    def __init__(self, payload):
        self.text = payload

    def raise_for_status(self):
        return None


class Session:
    def __init__(self, payload):
        self.payload = payload
        self.calls = []

    def get(self, url, **kwargs):
        self.calls.append((url, kwargs))
        return Response(self.payload)


def _listing(title):
    return f"""<feed xmlns="http://www.w3.org/2005/Atom"><entry>
    <category term="worldnews"/><id>t3_abc</id>
    <link href="https://www.reddit.com/r/worldnews/comments/abc/report/"/>
    <published>{NOW.isoformat()}</published><title>{title}</title>
    <content>{title}</content></entry></feed>"""


def test_nuclear_keyword_and_city_create_unverified_map_candidate():
    registry = load_registry(ROOT / "config/source_registry.yaml")
    source = next(value for value in registry.sources if value.id == "reddit_worldnews")
    items, health = discover_reddit_sources(
        [source],
        NOW,
        session=Session(_listing("Nuclear alert reported in Tehran")),
    )
    assert health[0].status == "fresh"
    assert items[0].map_eligible is True
    assert items[0].location_label == "Tehran"
    assert items[0].claim_confidence < 1
    events = reddit_map_events(items)
    assert events[0]["event_type"] == "reddit_report"
    verification = events[0]["verification"]
    assert isinstance(verification, dict)
    assert verification["confirmed"] is False
    feed = build_source_feed(items, health, publication_id="a" * 32, generated_at=NOW)
    feed_items = feed["items"]
    assert isinstance(feed_items, list)
    assert isinstance(feed_items[0], dict)
    assert feed_items[0]["map_eligible"] is True
    assert feed_items[0]["location_label"] == "Tehran"


def test_nuke_keyword_without_city_stays_feed_only():
    registry = load_registry(ROOT / "config/source_registry.yaml")
    source = next(value for value in registry.sources if value.id == "reddit_worldnews")
    items, _ = discover_reddit_sources(
        [source],
        NOW,
        session=Session(_listing("Unverified nuke discussion")),
    )
    assert len(items) == 1
    assert items[0].map_eligible is False
    assert reddit_map_events(items) == []
