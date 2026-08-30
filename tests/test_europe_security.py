from datetime import UTC, datetime
from xml.etree.ElementTree import ParseError

import pytest

from collectors.europe_security import (
    Observation,
    classify,
    cluster_observations,
    confidence_for,
    normalize_cluster,
    parse_date,
    parse_feed,
)
from sources.canonical import canonicalize_url

NOW = datetime(2026, 8, 30, 12, tzinfo=UTC)
TERMS = {
    "nato": ["nato"],
    "russia": ["russia", "kaliningrad"],
    "military_activity": ["airspace violation", "exercise", "deployment"],
    "geography": ["poland", "kaliningrad", "baltic sea"],
}


def reddit_source(subreddit="worldnews"):
    return {
        "id": f"reddit_{subreddit}",
        "name": f"r/{subreddit}",
        "source_type": "reddit",
        "source_perspective": "reddit_osint",
        "reliability": "medium",
        "subreddit": subreddit,
    }


def atom(external="https://www.reuters.com/world/europe/story/?utm_source=reddit"):
    return f"""<feed xmlns="http://www.w3.org/2005/Atom">
      <entry><title>NATO exercise in Poland</title>
      <link href="https://www.reddit.com/r/worldnews/comments/abc/story/"/>
      <content type="html">&lt;a href="{external}"&gt;Reuters&lt;/a&gt; NATO exercise in Poland</content>
      <author><name>public-user</name></author><published>2026-08-30T10:00:00Z</published></entry>
    </feed>"""


def test_canonical_url_removes_tracking_www_http_and_fragment():
    assert (
        canonicalize_url("http://www.Reuters.com/a/?utm_medium=x&gclid=y#z")
        == "https://reuters.com/a"
    )


def test_reddit_atom_extracts_external_url_and_sanitizes_html():
    item = parse_feed(atom(), reddit_source(), NOW)[0]
    assert item.canonical_source_url == "https://reuters.com/world/europe/story"
    assert item.post_url.startswith("https://reddit.com/")
    assert item.author is None  # nested author markup is not trusted as flat text
    assert "<a" not in item.description


def test_cross_subreddit_reposts_are_one_underlying_source():
    reports = []
    for subreddit in ("worldnews", "europe", "poland", "geopolitics"):
        item = parse_feed(atom(), reddit_source(subreddit), NOW)[0]
        assert classify(item, TERMS)
        reports.append(item)
    clusters = cluster_observations(reports)
    assert len(reports) == 4
    assert len(clusters) == 1
    event = normalize_cluster(clusters[0])
    assert event["metadata"]["observation_count"] == 4
    assert event["source_count"] == 1
    assert event["independent_source_count"] == 1
    assert event["status"] == "single_source"


def test_actor_reporting_is_separate_from_subject():
    item = Observation(
        "tass",
        "TASS",
        "state_media",
        "russian_state_media",
        "medium",
        "Russia says NATO aircraft approached Kaliningrad",
        "airspace violation",
        "https://tass.com/1",
        "https://tass.com/1",
        "https://tass.com/1",
        NOW,
    )
    assert classify(item, TERMS)
    assert item.actor_reporting == "RUSSIA"
    assert item.actor_subject == "NATO"
    assert item.location is not None
    assert item.location["precision"] == "city"


def test_confidence_does_not_use_reddit_popularity_or_reposts():
    reports = [
        parse_feed(atom(), reddit_source(name), NOW)[0] for name in ("a", "b", "c", "d")
    ]
    confidence, status, source_count, independent_count = confidence_for(reports)
    assert confidence == 0.35
    assert status == "single_source"
    assert source_count == independent_count == 1


def test_dates_and_malformed_feed():
    assert parse_date("Sun, 30 Aug 2026 10:00:00 GMT", NOW).tzinfo is not None
    assert parse_date("not-a-date", NOW) == NOW
    with pytest.raises(ParseError):
        parse_feed("<broken", reddit_source(), NOW)


def test_missing_location_is_not_fabricated():
    item = Observation(
        "media",
        "Media",
        "media",
        "european_media",
        "high",
        "NATO deployment announced",
        "military deployment",
        "https://example.com/1",
        "https://example.com/1",
        "https://example.com/1",
        NOW,
    )
    assert classify(item, TERMS)
    assert item.location is None
