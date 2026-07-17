import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from intelligence.map_generator import generate_map_events
from intelligence.threat_scoring import analyze_threats
from models.event_model import create_event
from processors.confidence_scoring import apply_confidence
from processors.data_normalizer import normalize_events
from processors.event_classifier import classify_events
from processors.event_deduplication import remove_duplicates
from processors.geolocation import apply_geolocation
from settings import load_config, source_enabled
from storage import event_database
import main as pipeline
from output import dashboard_exporter
from output.contracts import ContractError, SCHEMA_VERSION
from output.publisher import publish_artifacts
from storage.event_database import apply_retention
from utils.sanitization import plain_text, safe_url
from datetime import datetime, timedelta, timezone
import json


class SettingsTests(unittest.TestCase):
    def test_repository_config_matches_runtime_sources(self):
        config = load_config()
        self.assertTrue(source_enabled(config, "news"))
        self.assertTrue(source_enabled(config, "satellite", "nasa_eonet"))
        self.assertTrue(source_enabled(config, "humanitarian", "gdacs"))

    def test_invalid_limits_are_rejected(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "config.yaml"
            path.write_text("output:\n  max_map_events: 0\n", encoding="utf-8")
            with self.assertRaises(ValueError):
                load_config(path)


class PipelineTests(unittest.TestCase):
    def test_pipeline_geolocates_scores_and_maps_event(self):
        event = create_event(
            "conflict",
            "conflict_report",
            "Missile attack reported near Kyiv",
            source=["Reuters"],
            priority="high",
            confidence=70,
        )

        events = normalize_events([event])
        events = apply_geolocation(events)
        events = classify_events(events)
        events = remove_duplicates(events)
        events = apply_confidence(events)
        events = analyze_threats(events)
        mapped = generate_map_events(events)

        self.assertEqual(events[0]["category"], "conflict")
        self.assertEqual(events[0]["location"]["city"], "Kyiv")
        self.assertEqual(events[0]["confidence"], 85)
        self.assertEqual(events[0]["threat_level"], "CRITICAL")
        self.assertEqual(len(mapped), 1)

    def test_deduplication_uses_unique_sources_for_verification(self):
        first = create_event("news", "report", "Same title", source=["BBC"])
        second = create_event("news", "report", "Same title", source=["BBC"])
        third = create_event("news", "report", "Same title", source=["Reuters"])

        result = remove_duplicates([first, second, third])

        self.assertEqual(len(result), 1)
        self.assertEqual(result[0]["duplicate_count"], 3)
        self.assertEqual(result[0]["source"], ["BBC", "Reuters"])
        self.assertEqual(result[0]["verification"]["source_count"], 2)

    def test_confidence_scoring_is_idempotent(self):
        event = create_event("cyber", "kev", "CVE test", source=["CISA"], confidence=70)
        apply_confidence([event])
        first_score = event["confidence"]
        apply_confidence([event])
        self.assertEqual(event["confidence"], first_score)

    def test_stable_event_id_is_derived_from_fingerprint(self):
        first = create_event("news", "report", "Stable title", source=["BBC"])
        second = create_event("news", "report", "Stable title", source=["Reuters"])
        first_id = remove_duplicates([first])[0]["event_id"]
        second_id = remove_duplicates([second])[0]["event_id"]
        self.assertEqual(first_id, second_id)

    def test_map_rejects_invalid_coordinates_but_keeps_equator(self):
        events = [
            {"event_id": "unknown", "location": {"latitude": 0, "longitude": 0}},
            {"event_id": "bad", "location": {"latitude": 100, "longitude": 20}},
            {"event_id": "equator", "location": {"latitude": 0, "longitude": 20}},
        ]
        self.assertEqual(
            [event["event_id"] for event in generate_map_events(events)],
            ["equator"],
        )

    def test_database_merges_across_runs(self):
        event = create_event("cyber", "kev", "CVE test", source=["CISA"])
        with tempfile.TemporaryDirectory() as directory:
            database_path = Path(directory) / "events.json"
            with patch.object(event_database, "DATABASE_PATH", database_path):
                event_database.append_events([event])
                merged = event_database.append_events([event.copy()])

        self.assertEqual(len(merged), 1)
        self.assertEqual(merged[0]["duplicate_count"], 2)

    def test_main_writes_all_frontend_outputs_without_live_apis(self):
        event = create_event(
            "conflict",
            "conflict_report",
            "Missile activity in Ukraine",
            source=["Reuters"],
            priority="high",
            confidence=70,
        )
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            with (
                patch.object(pipeline, "collect_all_sources", return_value=[event]),
                patch.object(event_database, "DATABASE_PATH", root / "events.json"),
                patch.object(pipeline, "OUTPUT_DIRECTORY", root),
            ):
                pipeline.main()

            expected = [
                root / "world_events.json",
                root / "intelligence_brief.json",
                root / "timeline.json",
                root / "trends.json",
                root / "map_events.json",
                root / "dashboard.json",
                root / "health.json",
                root / "manifest.json",
                root / "events.json",
            ]
            self.assertTrue(all(path.exists() for path in expected))
            world = json.loads((root / "world_events.json").read_text(encoding="utf-8"))
            self.assertEqual(world["schema_version"], SCHEMA_VERSION)

    def test_invalid_release_does_not_replace_current_output(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            current = root / "world_events.json"
            current.write_text("current", encoding="utf-8")
            with self.assertRaises(ContractError):
                publish_artifacts({"world_events.json": {}}, root)
            self.assertEqual(current.read_text(encoding="utf-8"), "current")

    def test_retention_limits_age_and_count(self):
        now = datetime.now(timezone.utc)
        events = []
        for days in (40, 3, 2, 1):
            events.append({"timestamp": (now - timedelta(days=days)).isoformat(), "days": days})
        retained = apply_retention(events, max_age_days=30, max_events=2, now=now)
        self.assertEqual([event["days"] for event in retained], [2, 1])

    def test_feed_content_is_sanitized(self):
        self.assertEqual(plain_text("<b>Hello</b><script>bad()</script>", 100), "Hello bad()")
        self.assertEqual(safe_url("javascript:alert(1)"), "")
        self.assertEqual(safe_url("https://example.com/report"), "https://example.com/report")


if __name__ == "__main__":
    unittest.main()
