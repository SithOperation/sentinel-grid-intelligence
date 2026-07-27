import io
import json
import os
import tempfile
import unittest
from datetime import UTC, datetime, timedelta
from pathlib import Path
from unittest.mock import patch

import main as pipeline
from api.x_api import XApiTransport, XAuthenticationError, XProviderError
from collectors.x_collector import XAccount, XCollector
from intelligence.map_generator import generate_map_events
from models.x_report import (
    XReport,
    build_x_report_document,
    validate_x_report_document,
)
from storage import event_database
from storage.event_database import apply_retention

REFERENCE = datetime(2026, 7, 27, 12, 0, tzinfo=UTC)
KEYWORDS = {"reported_attack": ["attack"]}


def report(
    *,
    account="GoodAccount",
    published_at=REFERENCE,
    longitude=20.0,
) -> XReport:
    return XReport(
        account=account,
        source_url=f"https://x.com/{account}/status/123",
        summary="Attack reported near the city",
        published_at=published_at,
        collected_at=REFERENCE,
        source_class="social_media_osint",
        event_type="reported_attack",
        latitude=10.0,
        longitude=longitude,
        location_name="Test City",
    )


def timeline(post_id="123", bbox=None):
    return {
        "data": [
            {
                "id": post_id,
                "text": "Attack reported near the city",
                "created_at": REFERENCE.isoformat(),
                "geo": {"place_id": "place-1"},
            }
        ],
        "includes": {
            "places": [
                {
                    "id": "place-1",
                    "full_name": "Test City",
                    "geo": {"bbox": bbox or [19.0, 9.0, 21.0, 11.0]},
                }
            ]
        },
        "meta": {},
    }


class RoutedTransport:
    def __init__(self, timelines):
        self.timelines = timelines

    def get(self, url, bearer_token):
        if "/users/by/username/" in url:
            handle = url.rsplit("/", 1)[-1]
            return {"data": {"id": handle}}
        user_id = url.split("/users/", 1)[1].split("/", 1)[0]
        value = self.timelines[user_id]
        if isinstance(value, Exception):
            raise value
        return value


class XMigrationTests(unittest.TestCase):
    def test_valid_x_report_ingestion_and_map_integration(self):
        collector = XCollector(
            [XAccount("GoodAccount", "social_media_osint")],
            KEYWORDS,
            reference_time=REFERENCE,
            bearer_token="test-token",
            transport=RoutedTransport({"GoodAccount": timeline()}),
        )

        result = collector.collect()
        self.assertEqual(len(result.events), 1)
        event = result.events[0]
        self.assertEqual(event["classification"], "reported_attack")
        x_report = event["x_report"]
        self.assertIsInstance(x_report, dict)
        assert isinstance(x_report, dict)
        self.assertEqual(x_report["status_id"], "123")
        mapped = generate_map_events([event])
        self.assertEqual(len(mapped), 1)
        self.assertEqual(mapped[0]["type"], "x_report")
        self.assertEqual(mapped[0]["url"], "https://x.com/GoodAccount/status/123")

    def test_malformed_provider_response_isolated_per_account(self):
        collector = XCollector(
            [
                XAccount("BadAccount", "social_media_osint"),
                XAccount("GoodAccount", "social_media_osint"),
            ],
            KEYWORDS,
            reference_time=REFERENCE,
            bearer_token="test-token",
            transport=RoutedTransport(
                {
                    "BadAccount": {"data": "not-an-array"},
                    "GoodAccount": timeline(),
                }
            ),
        )

        result = collector.collect()
        self.assertTrue(result.partial)
        self.assertEqual(len(result.events), 1)
        self.assertEqual(result.accounts[0].status, "failed")
        self.assertIn("timeline data", result.accounts[0].error or "")

    def test_malformed_json_becomes_provider_error(self):
        response = io.BytesIO(b"{not-json")
        with (
            patch("api.x_api.urlopen", return_value=response),
            self.assertRaises(XProviderError),
        ):
            XApiTransport(retries=0).get("https://api.x.com/2/test", "token")

    def test_invalid_coordinates_do_not_abort_other_accounts(self):
        collector = XCollector(
            [
                XAccount("BadAccount", "social_media_osint"),
                XAccount("GoodAccount", "social_media_osint"),
            ],
            KEYWORDS,
            reference_time=REFERENCE,
            bearer_token="test-token",
            transport=RoutedTransport(
                {
                    "BadAccount": timeline("111", [0, -91, 1, 10]),
                    "GoodAccount": timeline(),
                }
            ),
        )

        result = collector.collect()
        self.assertTrue(result.partial)
        self.assertEqual(len(result.events), 1)

    def test_account_must_match_source_url(self):
        with self.assertRaisesRegex(ValueError, "must match"):
            XReport(
                account="AccountA",
                source_url="https://x.com/AccountB/status/123",
                summary="Report",
                published_at=REFERENCE,
                collected_at=REFERENCE,
                source_class="social_media_osint",
                event_type="unclassified_early_report",
                latitude=1,
                longitude=1,
                location_name="Place",
            )

    def test_exact_48_hour_boundary_is_retained(self):
        boundary = report(published_at=REFERENCE - timedelta(hours=48))
        older = report(published_at=REFERENCE - timedelta(hours=48, microseconds=1))
        retained = apply_retention(
            [boundary.to_event(), older.to_event()],
            max_age_hours=48,
            now=REFERENCE,
        )

        self.assertEqual(len(retained), 1)
        document = build_x_report_document(retained, REFERENCE)
        validate_x_report_document(document, reference_time=REFERENCE)

    def test_antimeridian_midpoint_stays_near_dateline(self):
        location = XCollector._location_from_place(
            {"full_name": "Dateline", "geo": {"bbox": [170, -10, -170, 10]}}
        )
        self.assertIsNotNone(location)
        assert location is not None
        self.assertEqual(abs(location[2]), 180)

    def test_partial_account_failure_still_returns_successful_reports(self):
        collector = XCollector(
            [
                XAccount("Down", "social_media_monitor"),
                XAccount("GoodAccount", "social_media_osint"),
            ],
            KEYWORDS,
            reference_time=REFERENCE,
            bearer_token="test-token",
            transport=RoutedTransport(
                {
                    "Down": XProviderError("provider unavailable"),
                    "GoodAccount": timeline(),
                }
            ),
        )
        result = collector.collect()
        self.assertEqual(
            [item.status for item in result.accounts], ["failed", "success"]
        )
        self.assertEqual(len(result.events), 1)

    def test_total_provider_failure_is_reported_clearly(self):
        collector = XCollector(
            [XAccount("Down", "social_media_monitor")],
            KEYWORDS,
            reference_time=REFERENCE,
            bearer_token="test-token",
            transport=RoutedTransport({"Down": XProviderError("provider unavailable")}),
        )
        with self.assertRaisesRegex(XProviderError, "failed for all accounts"):
            collector.collect()

    def test_missing_secret_fails_x_portion_clearly(self):
        with patch.dict(os.environ, {}, clear=True):
            collector = XCollector(
                [XAccount("GoodAccount", "social_media_osint")],
                KEYWORDS,
                reference_time=REFERENCE,
                bearer_token=None,
                transport=RoutedTransport({}),
            )
            with self.assertRaisesRegex(XAuthenticationError, "X_API_BEARER_TOKEN"):
                collector.collect()

    def test_missing_x_secret_does_not_stop_other_collectors(self):
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
                    "accounts_file": "config/x_accounts.json",
                    "keywords_file": "config/x_keywords.json",
                    "max_pages": 1,
                    "page_size": 10,
                    "retries": 0,
                    "backoff_seconds": 0,
                    "timeout_seconds": 1,
                },
            }
        }
        cyber_event = {"event_type": "cyber", "title": "Retained cyber event"}
        with (
            patch.object(pipeline, "CONFIG", config),
            patch.object(pipeline, "collect_cyber", return_value=[cyber_event]),
            patch.dict(os.environ, {}, clear=True),
        ):
            collected = pipeline.collect_all_sources(REFERENCE)

        self.assertEqual(collected, [cyber_event])
        x_health = next(
            item for item in pipeline.LAST_COLLECTION_HEALTH if item["source"] == "x"
        )
        self.assertEqual(x_health["status"], "error")
        self.assertIn("X_API_BEARER_TOKEN", x_health["error"])

    def test_failed_collection_preserves_retained_x_output(self):
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

            document = json.loads(
                (root / "output" / "x_reports.json").read_text(encoding="utf-8")
            )
            self.assertEqual(len(document["reports"]), 1)
            manifest = json.loads(
                (root / "output" / "manifest.json").read_text(encoding="utf-8")
            )
            self.assertIn("x_reports.json", manifest["files"])


if __name__ == "__main__":
    unittest.main()
