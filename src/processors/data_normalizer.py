"""
Sentinel Grid Data Normalizer

Converts incoming intelligence events
into a standard format.
"""

import uuid
import datetime


def normalize_events(events):

    normalized = []


    for event in events:

        event["event_id"] = (
            "SG-" +
            str(uuid.uuid4())[:8]
        )


        event.setdefault(
            "timestamp",
            datetime.datetime.now(datetime.UTC).isoformat()
        )


        event.setdefault(
            "verified",
            False
        )


        event.setdefault(
            "confidence",
            50
        )


        event.setdefault(
            "category",
            "unknown"
        )


        event.setdefault(
            "location",
            {
                "latitude": 0,
                "longitude": 0
            }
        )


        normalized.append(event)


    return normalized