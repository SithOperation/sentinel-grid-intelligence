from datetime import datetime


def generate_timeline(events):

    timeline = []


    for event in events:

        timeline.append({

            "event_id": event.get(
                "event_id"
            ),

            "timestamp": event.get(
                "timestamp"
            ),

            "event_type": event.get(
                "event_type"
            ),

            "title": event.get(
                "title"
            ),

            "priority": event.get(
                "priority",
                "unknown"
            ),

            "threat_level": event.get(
                "threat_level",
                "unknown"
            )

        })


    timeline.sort(
        key=lambda x: x.get(
            "timestamp",
            ""
        )
    )


    return timeline