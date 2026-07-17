"""
Sentinel Grid Event Model

Standard event structure used across:
- news
- conflict
- aircraft
- maritime
- satellite
- cyber
- humanitarian

"""

from datetime import datetime, timezone
import uuid



def create_event(
    event_type,
    classification,
    title,
    description="",
    source=None,
    priority="medium",
    location=None,
    confidence=0
):


    return {


        "event_id":

        f"SG-{uuid.uuid4().hex[:8]}",



        "event_type":

        event_type,



        "classification":

        classification,



        "priority":

        priority,



        "title":

        title,



        "description":

        description,



        "source":

        source or [],



        "timestamp":

        datetime.now(
            timezone.utc
        ).isoformat(),



        "location":

        location or {

            "country":
            "Unknown",

            "region":
            "Unknown",

            "latitude":
            0,

            "longitude":
            0

        },



        "actors":

        [],



        "confidence":

        confidence,


        "base_confidence":

        confidence,



        "verification":

        {

            "confirmed":

            False,


            "source_count":

            0

        }

    }
