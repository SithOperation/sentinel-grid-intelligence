"""
Sentinel Grid Data Normalizer

Converts incoming intelligence events
into the Sentinel Grid standard format.

Preserves existing intelligence data.
"""


import datetime
from datetime import timezone



def normalize_events(events):

    normalized = []


    for event in events:


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