import json
import tempfile
import unittest
from datetime import UTC, datetime, timedelta
from pathlib import Path
from unittest.mock import patch

import requests

import main as pipeline
from api.x_public import (
    PublicPage,
    PublicXTransport,
    XFetchError,
    XMetadataError,
    XUnavailableError,
    extract_public_post,
)
from collectors.x_collector import XCollector, XStatusURL, load_x_urls
from intelligence.map_generator import generate_map_events
from models.x_report import (
    XReport,
    build_x_report_document,
    canonical_x_url,
    validate_x_report_document,
)
from storage import event_database
from storage.event_database import apply_retention

REFERENCE = datetime(2026, 7, 27, 12, 0, tzinfo=UTC)
STATUS_ID = "1234567890123456789"
CANONICAL = f"https://x.com/Example/status/{STATUS_ID}"
FIXTURES = Path(__file__).parent / "fixtures" / "x_public"


def fixture(name):
    return (FIXTURES / name).read_text(encoding="utf-8")


def configured(url=CANONICAL):
    return XStatusURL(
        url=url,
        source_class="official",
        location_name="Example City",
        latitude=10,
        longitude=20,
        location_precision="city",
        event_type="early_report",
    )


def report(*, published_at=REFERENCE, status_id="123"):
    return XReport(
        account="GoodAccount",
        source_url=f"https://x.com/GoodAccount/status/{status_id}",
        summary="Attack reported near the city",
        published_at=published_at,
        collected_at=REFERENCE,
        source_class="social_media_osint",
        event_type="reported_attack",
        latitude=10,
        longitude=20,
        location_name="Test City",
    )


class FixtureTransport:
    def __init__(self, values):
        self.values = values
        self.calls = []

    def fetch(self, url):
        self.calls.append(url)
        value = self.values[url]
        if isinstance(value, Exception):
            raise value
        return PublicPage(url, url, fixture(value))


class FakeResponse:
    def __init__(
        self,
        *,
        url=CANONICAL,
        body=b"<html></html>",
        status_code=200,
        headers=None,
        history=None,
    ):
        self.url = url
        self.body = body
        self.status_code = status_code
        self.headers = headers or {"Content-Type": "text/html"}
        self.history = history or []
        self.encoding = "utf-8"
        self.closed = False

    def iter_content(self, chunk_size):
        del chunk_size
        yield self.body

    def close(self):
        self.closed = True


class FakeSession:
    def __init__(self, value):
        self.value = value
        self.kwargs = None

    def get(self, url, **kwargs):
        del url
        self.kwargs = kwargs
        if isinstance(self.value, Exception):
            raise self.value
        return self.value


class XMigrationTests(unittest.TestCase):
    def test_successful_public_metadata_extraction(self):
        post = extract_public_post(
            PublicPage(CANONICAL, CANONICAL, fixture("jsonld_post.html"))
        )
        self.assertEqual(post.status_id, STATUS_ID)
        self.assertEqual(post.account, "Example")
        self.assertEqual(post.published_at, "2026-07-27T11:00:00Z")

    def test_html_escaping_and_entity_decoding(self):
        post = extract_public_post(
            PublicPage(CANONICAL, CANONICAL, fixture("jsonld_post.html"))
        )
        self.assertEqual(post.text, "Flood & fire reported <near> the river")

    def test_open_graph_metadata_fallback(self):
        post = extract_public_post(
            PublicPage(CANONICAL, CANONICAL, fixture("opengraph_post.html"))
        )
        self.assertEqual(post.text, "Public & verified report")

    def test_url_normalization(self):
        for url in (
            CANONICAL,
            f"https://www.x.com/Example/status/{STATUS_ID}",
            f"https://twitter.com/Example/status/{STATUS_ID}",
            f"https://www.twitter.com/Example/status/{STATUS_ID}",
        ):
            self.assertEqual(canonical_x_url(url)[0], CANONICAL)
            self.assertEqual(configured(url).url, CANONICAL)

    def test_invalid_host_and_status_id_rejected(self):
        for url in (
            f"https://example.com/Example/status/{STATUS_ID}",
            "https://x.com/Example/status/not-numeric",
            f"http://x.com/Example/status/{STATUS_ID}",
            "https://x.com/Example",
        ):
            with self.subTest(url=url), self.assertRaises(ValueError):
                canonical_x_url(url)

    def test_redirect_to_external_domain_rejected(self):
        response = FakeResponse(
            status_code=302,
            headers={
                "Content-Type": "text/html",
                "Location": "https://example.com/landing",
            },
        )
        transport = PublicXTransport(session=FakeSession(response))
        with self.assertRaisesRegex(XFetchError, "redirect destination"):
            transport.fetch(CANONICAL)

    def test_redirect_cannot_change_configured_status_id(self):
        response = FakeResponse(
            status_code=302,
            headers={
                "Content-Type": "text/html",
                "Location": "https://x.com/Example/status/999",
            },
        )
        transport = PublicXTransport(session=FakeSession(response))
        with self.assertRaisesRegex(XFetchError, "changed the configured"):
            transport.fetch(CANONICAL)

    def test_response_size_limit(self):
        response = FakeResponse(body=b"x" * 2049)
        transport = PublicXTransport(
            session=FakeSession(response), max_response_bytes=2048
        )
        with self.assertRaisesRegex(XFetchError, "size limit"):
            transport.fetch(CANONICAL)

    def test_timeout_handling(self):
        transport = PublicXTransport(
            session=FakeSession(requests.Timeout("read timed out"))
        )
        with self.assertRaisesRegex(XFetchError, "timed out"):
            transport.fetch(CANONICAL)

    def test_deleted_and_login_wall_handling(self):
        for name in ("deleted.html", "login_wall.html"):
            with self.subTest(name=name), self.assertRaises(XUnavailableError):
                extract_public_post(PublicPage(CANONICAL, CANONICAL, fixture(name)))

    def test_missing_timestamp_and_malformed_metadata(self):
        with self.assertRaisesRegex(XMetadataError, "timestamp"):
            extract_public_post(
                PublicPage(CANONICAL, CANONICAL, fixture("missing_timestamp.html"))
            )
        with self.assertRaisesRegex(XMetadataError, "post text"):
            extract_public_post(
                PublicPage(CANONICAL, CANONICAL, fixture("malformed_metadata.html"))
            )

    def test_valid_ingestion_map_and_health_metrics(self):
        with tempfile.TemporaryDirectory() as directory:
            transport = FixtureTransport({CANONICAL: "jsonld_post.html"})
            result = XCollector(
                [configured()],
                reference_time=REFERENCE,
                transport=transport,
                cache_path=Path(directory) / "cache.json",
                request_interval_seconds=0,
            ).collect()
        self.assertEqual(len(result.events), 1)
        self.assertEqual(result.fetched_count, 1)
        self.assertEqual(result.accepted_count, 1)
        self.assertEqual(result.health_metrics()["configured_url_count"], 1)
        mapped = generate_map_events(list(result.events))
        self.assertEqual(mapped[0]["url"], CANONICAL)
        self.assertEqual(mapped[0]["type"], "x_report")

    def test_per_url_failure_isolation(self):
        second = configured("https://x.com/Other/status/987654321")
        transport = FixtureTransport(
            {
                CANONICAL: "jsonld_post.html",
                second.url: "jsonld_post.html",
            }
        )
        # Use matching metadata for the second URL.
        other_html = (
            fixture("jsonld_post.html")
            .replace(CANONICAL, second.url)
            .replace("@Example", "@Other")
        )
        with (
            tempfile.TemporaryDirectory() as directory,
            patch(
                "collectors.x_collector.extract_public_post",
                side_effect=[
                    XUnavailableError("public post is unavailable"),
                    extract_public_post(PublicPage(second.url, second.url, other_html)),
                ],
            ),
        ):
            result = XCollector(
                [configured(), second],
                reference_time=REFERENCE,
                transport=transport,
                cache_path=Path(directory) / "cache.json",
                request_interval_seconds=0,
            ).collect()
        self.assertEqual(len(result.events), 1)
        self.assertTrue(result.partial)
        self.assertEqual(result.unavailable_count, 1)

    def test_cache_reuse_by_status_id(self):
        with tempfile.TemporaryDirectory() as directory:
            cache_path = Path(directory) / "cache.json"
            first_transport = FixtureTransport({CANONICAL: "jsonld_post.html"})
            first = XCollector(
                [configured()],
                reference_time=REFERENCE,
                transport=first_transport,
                cache_path=cache_path,
                request_interval_seconds=0,
            ).collect()
            second_transport = FixtureTransport({})
            second = XCollector(
                [configured()],
                reference_time=REFERENCE,
                transport=second_transport,
                cache_path=cache_path,
                request_interval_seconds=0,
            ).collect()
        self.assertEqual(first.fetched_count, 1)
        self.assertEqual(second.cached_count, 1)
        self.assertEqual(second_transport.calls, [])

    def test_malformed_cache_is_refetched(self):
        with tempfile.TemporaryDirectory() as directory:
            cache_path = Path(directory) / "cache.json"
            cache_path.write_text(
                json.dumps(
                    {
                        "schema_version": "1.0",
                        "posts": {
                            STATUS_ID: {
                                "canonical_url": CANONICAL,
                                "account": None,
                                "text": None,
                                "published_at": None,
                            }
                        },
                    }
                ),
                encoding="utf-8",
            )
            transport = FixtureTransport({CANONICAL: "jsonld_post.html"})
            result = XCollector(
                [configured()],
                reference_time=REFERENCE,
                transport=transport,
                cache_path=cache_path,
                request_interval_seconds=0,
            ).collect()
        self.assertEqual(result.fetched_count, 1)
        self.assertEqual(result.cached_count, 0)
        self.assertEqual(result.accepted_count, 1)

    def test_exact_48_hour_boundary_is_retained(self):
        boundary = report(published_at=REFERENCE - timedelta(hours=48), status_id="1")
        older = report(
            published_at=REFERENCE - timedelta(hours=48, microseconds=1),
            status_id="2",
        )
        retained = apply_retention(
            [boundary.to_event(), older.to_event()],
            max_age_hours=48,
            now=REFERENCE,
        )
        self.assertEqual(len(retained), 1)
        document = build_x_report_document(retained, REFERENCE)
        validate_x_report_document(document, reference_time=REFERENCE)

    def test_account_must_match_source_url(self):
        with self.assertRaisesRegex(ValueError, "must match"):
            XReport(
                account="AccountA",
                source_url="https://x.com/AccountB/status/123",
                summary="Report",
                published_at=REFERENCE,
                collected_at=REFERENCE,
                source_class="official",
                event_type="early_report",
                latitude=1,
                longitude=1,
                location_name="Place",
                location_precision="city",
            )

    def test_invalid_coordinates_rejected_in_configuration(self):
        payload = [
            {
                "url": CANONICAL,
                "source_class": "official",
                "location_name": "Place",
                "latitude": 91,
                "longitude": 0,
                "location_precision": "city",
                "event_type": "early_report",
            }
        ]
        with self.assertRaisesRegex(ValueError, "coordinates"):
            load_x_urls(payload)

    def test_all_x_failures_do_not_stop_existing_collectors(self):
        config = {
            "sources": {
                "news": {"enabled": False},
                "conflict": {"enabled": False},
                "aircraft": {"opensky": {"enabled": False}},
                "maritime": {"aisstream": {"enabled": False}},
                "satellite": {"nasa_eonet": {"enabled": False}},
                "cyber": {"enabled": True},
                "humanitarian": {"gdacs": {"enabled": False}},
                "x": {
                    "enabled": True,
                    "connection_timeout_seconds": 1,
                    "request_timeout_seconds": 1,
                    "request_interval_seconds": 0,
                    "max_response_bytes": 2048,
                    "max_urls_per_run": 1,
                    "cache_file": "data/cache/test.json",
                    "urls": [
                        {
                            "url": CANONICAL,
                            "source_class": "official",
                            "location_name": "Place",
                            "latitude": 1,
                            "longitude": 1,
                            "location_precision": "city",
                            "event_type": "early_report",
                        }
                    ],
                },
            }
        }
        cyber_event = {"event_type": "cyber", "title": "Retained cyber event"}
        failed_transport = FixtureTransport(
            {CANONICAL: XUnavailableError("public post is unavailable")}
        )
        with (
            tempfile.TemporaryDirectory() as directory,
            patch.object(pipeline, "CONFIG", config),
            patch.object(pipeline, "collect_cyber", return_value=[cyber_event]),
            patch.object(
                pipeline,
                "resolve_project_path",
                return_value=Path(directory) / "cache.json",
            ),
            patch.object(pipeline, "PublicXTransport", return_value=failed_transport),
        ):
            collected = pipeline.collect_all_sources(REFERENCE)
        self.assertEqual(collected, [cyber_event])
        x_health = next(
            item for item in pipeline.LAST_COLLECTION_HEALTH if item["source"] == "x"
        )
        self.assertEqual(x_health["status"], "error")
        self.assertEqual(x_health["metrics"]["unavailable_count"], 1)

    def test_last_known_good_and_website_artifacts_are_preserved(self):
        event = report(published_at=REFERENCE - timedelta(hours=1)).to_event()
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            with (
                patch.object(event_database, "DATABASE_PATH", root / "events.json"),
                patch.object(pipeline, "OUTPUT_DIRECTORY", root / "output"),
                patch.object(pipeline, "collect_all_sources", return_value=[]),
            ):
                event_database.save_events([event])
                pipeline.main(reference_time=REFERENCE)
            output = root / "output"
            document = json.loads(
                (output / "x_reports.json").read_text(encoding="utf-8")
            )
            self.assertEqual(len(document["reports"]), 1)
            for name in (
                "x_report_events.json",
                "x_report_pinpoints.geojson",
                "world_events.json",
                "map_events.json",
                "timeline.json",
                "dashboard.json",
                "health.json",
                "manifest.json",
            ):
                self.assertTrue((output / name).is_file(), name)


if __name__ == "__main__":
    unittest.main()
