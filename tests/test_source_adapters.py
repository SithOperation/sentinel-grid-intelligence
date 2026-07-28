import json
from datetime import UTC, datetime

import pytest

from sources.adapters import (
    manual_items,
    parse_reddit_atom,
    parse_reddit_listing,
    parse_rss,
    parse_website_links,
    parse_x_syndication,
)

NOW = datetime(2026, 7, 28, 12, tzinfo=UTC)


def test_manual_url_adapter_normalizes_items():
    items = manual_items(
        "manual",
        "manual",
        [
            {
                "url": "https://example.com/report?utm_source=x",
                "published_at": NOW.isoformat(),
                "title": "Report",
                "text": "Text",
            }
        ],
        NOW,
    )
    assert items[0].canonical_url == "https://example.com/report"


def test_rss_and_atom_parser():
    rss = """<rss><channel><item><guid>1</guid><title>Report</title>
    <link>https://example.com/1</link><pubDate>Tue, 28 Jul 2026 10:00:00 +0000</pubDate>
    <description>Details</description></item></channel></rss>"""
    atom = """<feed xmlns="http://www.w3.org/2005/Atom"><entry><id>2</id>
    <title>Atom report</title><link href="https://example.com/2"/>
    <updated>2026-07-28T11:00:00Z</updated><summary>Details</summary></entry></feed>"""
    assert [item.platform_item_id for item in parse_rss("rss", rss, NOW)] == ["1"]
    assert [item.platform_item_id for item in parse_rss("atom", atom, NOW)] == ["2"]


def test_website_parser_keeps_only_approved_host_links():
    html = """<a href="https://www.president.gov.ua/en/news/report">Official report</a>
    <a href="https://evil.example/report">Other</a>"""
    items = parse_website_links("president", html, NOW, allowed_host="president.gov.ua")
    assert [item.canonical_url for item in items] == [
        "https://www.president.gov.ua/en/news/report"
    ]


def test_reddit_listing_parser():
    payload = json.dumps(
        {
            "data": {
                "children": [
                    {
                        "data": {
                            "id": "abc",
                            "permalink": "/r/ukraine/comments/abc/report/",
                            "created_utc": NOW.timestamp(),
                            "title": "Report",
                            "selftext": "Details",
                            "is_video": True,
                        }
                    }
                ]
            }
        }
    )
    items = parse_reddit_listing("reddit_ukraine", payload, NOW)
    assert items[0].platform_item_id == "abc"
    assert items[0].media_type == "video"


def test_reddit_atom_parser_preserves_subreddit():
    atom = f"""<feed xmlns="http://www.w3.org/2005/Atom"><entry>
    <category term="worldnews"/><id>t3_abc</id>
    <link href="https://www.reddit.com/r/worldnews/comments/abc/report/"/>
    <published>{NOW.isoformat()}</published><title>Nuclear report</title>
    <content>Report from Tehran</content></entry></feed>"""
    items = parse_reddit_atom(atom, NOW)
    assert items[0].source_id == "reddit_worldnews"
    assert items[0].platform_item_id == "abc"


def test_x_syndication_parser_uses_embedded_fixture_not_live_access():
    timeline = {
        "props": {
            "pageProps": {
                "timeline": {
                    "entries": [
                        {
                            "tweet": {
                                "id_str": "123456",
                                "full_text": "Source-reported activity",
                                "created_at": "Tue Jul 28 10:00:00 +0000 2026",
                            }
                        }
                    ]
                }
            }
        }
    }
    html = (
        '<script id="__NEXT_DATA__" type="application/json">'
        + json.dumps(timeline)
        + "</script>"
    )
    items = parse_x_syndication("example", "example", html, NOW)
    assert items[0].canonical_url == "https://x.com/example/status/123456"


@pytest.mark.parametrize(
    ("parser", "payload"),
    [
        (lambda value: parse_rss("rss", value, NOW), "<broken"),
        (lambda value: parse_reddit_listing("reddit", value, NOW), "{"),
        (lambda value: parse_x_syndication("x", "x", value, NOW), "<html></html>"),
    ],
)
def test_malformed_adapter_payloads_fail_at_the_adapter_boundary(parser, payload):
    with pytest.raises((ValueError, json.JSONDecodeError)):
        parser(payload)
