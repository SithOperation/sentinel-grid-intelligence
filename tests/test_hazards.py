import json
import tempfile
import unittest
from datetime import UTC, datetime, timedelta
from pathlib import Path
from unittest.mock import patch

import requests

import main as pipeline
from api.bounded_json import BoundedJSONTransport, JSONResponse, ProviderError
from collectors.earthquake_collector import collect_earthquakes
from collectors.satellite_collector import collect_natural_events
from collectors.volcano_collector import collect_volcanoes
from collectors.weather_collector import (
    collect_weather_alerts,
    representative_point,
)
from intelligence.map_generator import generate_map_events
from processors.confidence_scoring import apply_confidence
from processors.event_classifier import classify_events
from processors.event_deduplication import remove_duplicates
from storage import event_database
from storage.event_database import apply_retention

REFERENCE = datetime(2026, 7, 28, 12, tzinfo=UTC)
BASE = {
    "connection_timeout_seconds": 1,
    "request_timeout_seconds": 2,
    "max_response_bytes": 10_000,
}


class FixtureTransport:
    def __init__(self, data=None, error=None):
        self.data = data
        self.error = error

    def get(self, url):
        del url
        if self.error:
            raise self.error
        return JSONResponse(self.data, len(json.dumps(self.data)))


def usgs_feature(event_id="us1", when=REFERENCE, coordinates=None, **properties):
    values = {
        "type": "earthquake",
        "time": int(when.timestamp() * 1000),
        "updated": int(when.timestamp() * 1000),
        "mag": 5.2,
        "magType": "mw",
        "place": "10 km W of Test",
        "title": "M 5.2 - Test",
        "url": f"https://earthquake.usgs.gov/earthquakes/eventpage/{event_id}",
        "detail": f"https://earthquake.usgs.gov/fdsnws/event/1/query?eventid={event_id}",
        "tsunami": 1,
        "alert": "yellow",
        "felt": 12,
        "sig": 500,
        "status": "reviewed",
    }
    values.update(properties)
    return {
        "type": "Feature",
        "id": event_id,
        "properties": values,
        "geometry": {"type": "Point", "coordinates": coordinates or [-122, 45, 10]},
    }


def eonet_event(event_id="E1", geometries=None, closed=None):
    return {
        "id": event_id,
        "title": "Test Volcano eruption",
        "description": "Ash plume observed",
        "link": f"https://eonet.gsfc.nasa.gov/api/v3/events/{event_id}",
        "closed": closed,
        "categories": [{"id": "volcanoes", "title": "Volcanoes"}],
        "sources": [{"id": "S", "url": "https://example.gov/source"}],
        "geometry": geometries
        or [
            {
                "date": (REFERENCE - timedelta(hours=2)).isoformat(),
                "type": "Point",
                "coordinates": [140, 35],
            }
        ],
    }


def eonet_natural_event(category="Wildfires", event_id="N1"):
    event = eonet_event(event_id)
    event["title"] = f"Test {category}"
    event["categories"] = [{"id": category.casefold(), "title": category}]
    return event


def nws_alert(alert_id="urn:alert:1", geometry=None, expires=None, severity="Severe"):
    return {
        "type": "Feature",
        "id": alert_id,
        "geometry": geometry,
        "properties": {
            "id": alert_id,
            "@id": "https://api.weather.gov/alerts/1",
            "event": "Severe Thunderstorm Warning",
            "severity": severity,
            "certainty": "Observed",
            "urgency": "Immediate",
            "status": "Actual",
            "messageType": "Alert",
            "headline": "Warning",
            "description": "Severe storm",
            "instruction": "Shelter indoors",
            "effective": (REFERENCE - timedelta(hours=1)).isoformat(),
            "onset": (REFERENCE - timedelta(minutes=30)).isoformat(),
            "expires": (expires or REFERENCE + timedelta(hours=1)).isoformat(),
            "ends": None,
            "areaDesc": "Test County",
            "senderName": "NWS Test",
            "response": "Shelter",
            "geocode": {"SAME": ["001"]},
            "references": [],
        },
    }


class HazardCollectorTests(unittest.TestCase):
    def test_usgs_valid_order_epoch_metadata_and_tsunami(self):
        payload = {
            "features": [usgs_feature()],
            "metadata": {"generated": int(REFERENCE.timestamp() * 1000)},
        }
        result = collect_earthquakes(
            {**BASE, "feed_url": "https://example.gov/feed"},
            REFERENCE,
            FixtureTransport(payload),
        )
        self.assertEqual(result.status, "ok")
        event = result.events[0]
        self.assertEqual(event["location"]["longitude"], -122)
        self.assertEqual(event["location"]["latitude"], 45)
        self.assertEqual(event["timestamp"], REFERENCE.isoformat())
        self.assertTrue(event["earthquake"]["tsunami"])
        self.assertEqual(event["provider"]["id"], "us1")

    def test_usgs_missing_magnitude_is_retained(self):
        result = collect_earthquakes(
            {**BASE, "feed_url": "https://example.gov/feed"},
            REFERENCE,
            FixtureTransport({"features": [usgs_feature(mag=None)]}),
        )
        self.assertEqual(len(result.events), 1)
        self.assertIsNone(result.events[0]["earthquake"]["magnitude"])

    def test_usgs_rejects_bad_coordinates_duplicate_and_stale(self):
        payload = {
            "features": [
                usgs_feature(coordinates=[200, 10, 1]),
                usgs_feature("dupe"),
                usgs_feature("dupe"),
                usgs_feature("stale", REFERENCE - timedelta(hours=72, microseconds=1)),
            ]
        }
        result = collect_earthquakes(
            {**BASE, "feed_url": "https://example.gov/feed"},
            REFERENCE,
            FixtureTransport(payload),
        )
        self.assertEqual(len(result.events), 1)
        self.assertEqual(result.metrics["records_rejected"], 3)

    def test_usgs_exact_72_hour_boundary(self):
        result = collect_earthquakes(
            {**BASE, "feed_url": "https://example.gov/feed"},
            REFERENCE,
            FixtureTransport(
                {"features": [usgs_feature(when=REFERENCE - timedelta(hours=72))]}
            ),
        )
        self.assertEqual(len(result.events), 1)

    def test_volcano_selects_newest_valid_geometry_and_rejects_closed(self):
        geometries = [
            {
                "date": (REFERENCE - timedelta(hours=2)).isoformat(),
                "type": "Point",
                "coordinates": [1, 2],
            },
            {
                "date": (REFERENCE - timedelta(hours=1)).isoformat(),
                "type": "Point",
                "coordinates": [3, 4],
            },
            {"date": REFERENCE.isoformat(), "type": "Polygon", "coordinates": []},
        ]
        payload = {
            "events": [
                eonet_event(geometries=geometries),
                eonet_event("closed", closed=REFERENCE.isoformat()),
            ]
        }
        result = collect_volcanoes(
            {**BASE, "endpoint_url": "https://example.gov/events"},
            REFERENCE,
            FixtureTransport(payload),
        )
        self.assertEqual(len(result.events), 1)
        self.assertEqual(result.events[0]["location"]["longitude"], 3)
        self.assertEqual(len(result.events[0]["volcano"]["geometry_history"]), 2)

    def test_volcano_malformed_stale_duplicate_and_failure(self):
        payload = {
            "events": [
                eonet_event(
                    "bad",
                    [
                        {
                            "date": REFERENCE.isoformat(),
                            "type": "Point",
                            "coordinates": ["x"],
                        }
                    ],
                ),
                eonet_event(
                    "stale",
                    [
                        {
                            "date": (REFERENCE - timedelta(hours=73)).isoformat(),
                            "type": "Point",
                            "coordinates": [1, 2],
                        }
                    ],
                ),
                eonet_event("same"),
                eonet_event("same"),
            ]
        }
        result = collect_volcanoes(
            {**BASE, "endpoint_url": "https://example.gov/events"},
            REFERENCE,
            FixtureTransport(payload),
        )
        self.assertEqual(len(result.events), 1)
        failed = collect_volcanoes(
            {**BASE, "endpoint_url": "https://example.gov/events"},
            REFERENCE,
            FixtureTransport(error=ProviderError("down")),
        )
        self.assertEqual(failed.status, "error")

    def test_selected_eonet_natural_events_are_map_first(self):
        payload = {
            "events": [
                eonet_natural_event("Wildfires", "fire"),
                eonet_natural_event("Floods", "flood"),
                eonet_natural_event("Severe Storms", "storm"),
                eonet_natural_event("Drought", "unsupported"),
            ]
        }
        result = collect_natural_events(
            {**BASE, "endpoint_url": "https://example.gov/events"},
            REFERENCE,
            FixtureTransport(payload),
        )
        self.assertEqual(
            [event["event_type"] for event in result.events],
            ["wildfire", "flood", "tropical_cyclone"],
        )
        self.assertEqual(len(generate_map_events(result.events)), 3)

    def test_weather_point_polygon_multipolygon_and_missing_geometry(self):
        geometries = [
            {"type": "Point", "coordinates": [-80, 30]},
            {
                "type": "Polygon",
                "coordinates": [[[-81, 30], [-79, 30], [-79, 32], [-81, 32]]],
            },
            {
                "type": "MultiPolygon",
                "coordinates": [[[[-81, 30], [-79, 30], [-80, 32]]]],
            },
            None,
        ]
        result = collect_weather_alerts(
            {**BASE, "alerts_url": "https://example.gov/alerts"},
            REFERENCE,
            FixtureTransport(
                {
                    "features": [
                        nws_alert(f"a{i}", geometry)
                        for i, geometry in enumerate(geometries)
                    ]
                }
            ),
        )
        self.assertEqual(len(result.events), 4)
        self.assertEqual(len(generate_map_events(result.events)), 3)
        self.assertEqual(result.metrics["missing_geometry"], 1)
        polygon_point = representative_point(geometries[1])
        self.assertIsNotNone(polygon_point)
        assert polygon_point is not None
        self.assertAlmostEqual(polygon_point[0], -80)

    def test_weather_expired_active_invalid_severity_and_timestamp_policy(self):
        payload = {
            "features": [
                nws_alert("expired", expires=REFERENCE - timedelta(seconds=1)),
                nws_alert(
                    "active", geometry={"type": "Point", "coordinates": [-80, 30]}
                ),
                nws_alert("bad-severity", severity="Catastrophic"),
            ]
        }
        result = collect_weather_alerts(
            {**BASE, "alerts_url": "https://example.gov/alerts"},
            REFERENCE,
            FixtureTransport(payload),
        )
        self.assertEqual(len(result.events), 1)
        self.assertEqual(result.events[0]["timestamp"], REFERENCE.isoformat())
        self.assertEqual(result.metrics["expired_alerts"], 1)

    def test_provider_failure_status(self):
        for collector, key in (
            (collect_earthquakes, "feed_url"),
            (collect_weather_alerts, "alerts_url"),
        ):
            result = collector(
                {**BASE, key: "https://example.gov/data"},
                REFERENCE,
                FixtureTransport(error=ProviderError("provider request timed out")),
            )
            self.assertEqual(result.status, "error")


class RetentionAndPipelineTests(unittest.TestCase):
    def test_runtime_source_health_contains_only_active_families(self):
        expected = {
            "conflict",
            "nasa_eonet_natural_events",
            "usgs_earthquakes",
            "nasa_eonet_volcanoes",
            "nws_weather_alerts",
            "gdacs",
            "x",
        }
        self.assertEqual(set(pipeline._configured_sources()), expected)

    def test_unsupported_retained_event_types_are_not_published(self):
        events = pipeline.process_events(
            [
                {
                    "event_type": "unsupported_feed",
                    "title": "Not part of Sentinel",
                },
                {
                    "event_type": "earthquake",
                    "title": "Supported",
                    "timestamp": REFERENCE.isoformat(),
                },
            ]
        )
        self.assertEqual([event["event_type"] for event in events], ["earthquake"])

    def test_rolling_72_hours_malformed_missing_and_expired_weather(self):
        events = [
            {
                "timestamp": (REFERENCE - timedelta(hours=72)).isoformat(),
                "id": "boundary",
            },
            {
                "timestamp": (
                    REFERENCE - timedelta(hours=72, microseconds=1)
                ).isoformat(),
                "id": "old",
            },
            {"timestamp": "bad", "id": "malformed"},
            {"id": "missing"},
            {
                "timestamp": REFERENCE.isoformat(),
                "id": "expired",
                "event_type": "weather_alert",
                "weather": {"expires": (REFERENCE - timedelta(seconds=1)).isoformat()},
            },
            {
                "timestamp": REFERENCE.isoformat(),
                "id": "active",
                "event_type": "weather_alert",
                "weather": {"expires": (REFERENCE + timedelta(hours=1)).isoformat()},
            },
        ]
        retained = apply_retention(events, now=REFERENCE)
        self.assertEqual([event["id"] for event in retained], ["boundary", "active"])

    def test_hazards_normalize_classify_score_and_deduplicate(self):
        earthquake = collect_earthquakes(
            {**BASE, "feed_url": "https://example.gov/feed"},
            REFERENCE,
            FixtureTransport({"features": [usgs_feature(), usgs_feature()]}),
        ).events
        events = apply_confidence(classify_events(remove_duplicates(earthquake)))
        self.assertEqual(len(events), 1)
        self.assertEqual(events[0]["category"], "earthquake")
        self.assertGreater(events[0]["confidence"], 90)

    def test_active_weather_refreshes_canonical_timestamp_across_runs(self):
        older = collect_weather_alerts(
            {**BASE, "alerts_url": "https://example.gov/alerts"},
            REFERENCE - timedelta(hours=2),
            FixtureTransport(
                {
                    "features": [
                        nws_alert(geometry={"type": "Point", "coordinates": [-80, 30]})
                    ]
                }
            ),
        ).events[0]
        newer = collect_weather_alerts(
            {**BASE, "alerts_url": "https://example.gov/alerts"},
            REFERENCE,
            FixtureTransport(
                {
                    "features": [
                        nws_alert(geometry={"type": "Point", "coordinates": [-80, 30]})
                    ]
                }
            ),
        ).events[0]
        merged = remove_duplicates([older, newer])
        self.assertEqual(len(merged), 1)
        self.assertEqual(merged[0]["timestamp"], REFERENCE.isoformat())

    def test_failed_new_source_does_not_stop_other_sources(self):
        config = {
            "sources": {
                "conflict": {"enabled": True},
                "eonet": {"enabled": False},
                "earthquake": {"usgs": {"enabled": True}},
                "weather": {"nws": {"enabled": False}},
                "humanitarian": {"gdacs": {"enabled": False}},
                "x": {"enabled": False},
            }
        }
        failed = type(
            "Result",
            (),
            {"events": [], "status": "error", "error": "down", "metrics": {}},
        )()
        with (
            patch.object(pipeline, "CONFIG", config),
            patch.object(pipeline, "fetch_news_articles", return_value=[]),
            patch.object(pipeline, "collect_earthquakes", return_value=failed),
            patch.object(
                pipeline,
                "collect_conflicts",
                return_value=[{"event_type": "conflict"}],
            ),
        ):
            events = pipeline.collect_all_sources(REFERENCE)
        self.assertEqual(events, [{"event_type": "conflict"}])

    def test_clean_empty_database_startup_and_explicit_reset(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            output = root / "output"
            output.mkdir()
            known = output / "world_events.json"
            unknown = output / "manual.json"
            known.write_text("{}", encoding="utf-8")
            unknown.write_text("{}", encoding="utf-8")
            database = root / "events.json"
            database.write_text("[]", encoding="utf-8")
            with (
                patch.object(pipeline, "OUTPUT_DIRECTORY", output),
                patch.object(event_database, "DATABASE_PATH", database),
                patch.object(
                    pipeline,
                    "CONFIG",
                    {
                        **pipeline.CONFIG,
                        "sources": {
                            **pipeline.CONFIG["sources"],
                            "x": {
                                **pipeline.CONFIG["sources"]["x"],
                                "cache_file": str(root / "cache.json"),
                            },
                        },
                    },
                ),
            ):
                removed = pipeline.reset_generated_data()
                self.assertIn(known, removed)
                self.assertFalse(database.exists())
                self.assertTrue(unknown.exists())
                self.assertEqual(event_database.load_events(), [])


class FakeResponse:
    def __init__(self, body=b"{}", headers=None):
        self.body = body
        self.headers = headers or {}

    def raise_for_status(self):
        return None

    def iter_content(self, chunk_size):
        del chunk_size
        yield self.body

    def close(self):
        return None


class FakeSession:
    def __init__(self, value):
        self.value = value

    def get(self, *args, **kwargs):
        del args, kwargs
        if isinstance(self.value, Exception):
            raise self.value
        return self.value


class BoundedTransportTests(unittest.TestCase):
    def test_timeout_malformed_json_and_oversize(self):
        cases = [
            (requests.Timeout(), "timed out"),
            (FakeResponse(b"{"), "malformed JSON"),
            (FakeResponse(b"x" * 11), "size limit"),
        ]
        for value, message in cases:
            transport = BoundedJSONTransport(
                connect_timeout_seconds=1,
                read_timeout_seconds=1,
                max_response_bytes=10,
                headers={},
                session=FakeSession(value),
            )
            with (
                self.subTest(message=message),
                self.assertRaisesRegex(ProviderError, message),
            ):
                transport.get("https://example.gov/data")


if __name__ == "__main__":
    unittest.main()
