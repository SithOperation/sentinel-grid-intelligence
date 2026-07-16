"""
Timeline Intelligence Generator

Creates chronological intelligence timeline.

Used for:
- dashboard timeline views
- historical event tracking
- intelligence reporting
"""


from datetime import datetime





def safe_timestamp(timestamp):


    if not timestamp:

        return ""



    try:

        datetime.fromisoformat(
            timestamp.replace(
                "Z",
                "+00:00"
            )
        )

        return timestamp



    except Exception:

        return ""





def generate_timeline(events):


    timeline = []



    for event in events:


        timeline.append({


            "event_id":

            event.get(
                "event_id"
            ),



            "event_hash":

            event.get(
                "event_hash"
            ),



            "timestamp":

            event.get(
                "timestamp"
            ),



            "event_type":

            event.get(
                "event_type"
            ),



            "classification":

            event.get(
                "classification"
            ),



            "title":

            event.get(
                "title"
            ),



            "description":

            event.get(
                "description",
                ""
            )[:250],



            "priority":

            event.get(
                "priority",
                "unknown"
            ),



            "threat_score":

            event.get(
                "threat_score",
                0
            ),



            "threat_level":

            event.get(
                "threat_level",
                "unknown"
            ),



            "confidence":

            event.get(
                "confidence",
                0
            ),



            "source":

            event.get(
                "source",
                []
            ),



            "location":

            event.get(
                "location",
                {}

            )


        })



    timeline.sort(

        key=lambda event:

        safe_timestamp(

            event.get(
                "timestamp"
            )

        )

    )



    return timeline