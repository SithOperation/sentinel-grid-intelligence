def generate_map_events(events):

    map_events = []


    for event in events:

        location = event.get(
            "location",
            {}
        )


        latitude = location.get(
            "latitude",
            0
        )

        longitude = location.get(
            "longitude",
            0
        )


        # Skip events without coordinates

        if latitude == 0 and longitude == 0:
            continue


        map_events.append({

            "event_id": event.get(
                "event_id"
            ),

            "type": event.get(
                "event_type",
                "unknown"
            ),

            "title": event.get(
                "title"
            ),

            "description": event.get(
                "description"
            ),

            "latitude": latitude,

            "longitude": longitude,

            "priority": event.get(
                "priority",
                "unknown"
            ),

            "threat_level": event.get(
                "threat_level",
                "unknown"
            ),

            "confidence": event.get(
                "confidence",
                0
            ),

            "timestamp": event.get(
                "timestamp"
            )

        })


    return map_events