"""
Sentinel Grid Data Normalizer

Converts incoming intelligence events
into the Sentinel Grid standard format.

Preserves existing intelligence data.
"""


import datetime
from datetime import timezone
from utils.sanitization import plain_text, safe_url



def normalize_events(events):

    normalized = []


    for event in events:

        event["title"] = plain_text(event.get("title", "Unknown event"), 500)
        event["description"] = plain_text(event.get("description", ""), 5000)
        if "url" in event:
            event["url"] = safe_url(event["url"])


        # Preserve existing event IDs
        event.setdefault(
            "event_id",
            "SG-UNKNOWN"
        )


        # Ensure timestamp exists
        event.setdefault(
            "timestamp",
            datetime.datetime.now(
                timezone.utc
            ).isoformat()
        )


        # Standard confidence
        event.setdefault(
            "confidence",
            50
        )

        event.setdefault(
            "base_confidence",
            event["confidence"]
        )


        # Standard category
        event.setdefault(
            "category",
            event.get(
                "classification",
                "unknown"
            )
        )


        # Standard location
        event.setdefault(
            "location",
            {

                "country":
                "Unknown",

                "region":
                "Unknown",

                "latitude":
                0,

                "longitude":
                0

            }
        )


        # Standard verification
        event.setdefault(
            "verification",
            {

                "confirmed":
                False,

                "source_count":
                1

            }
        )


        normalized.append(
            event
        )


    return normalized
