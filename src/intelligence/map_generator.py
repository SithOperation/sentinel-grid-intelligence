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


        # A pair of zeroes is the standard "unknown" location. Keep valid
        # points on the equator or prime meridian, but reject malformed data.
        if (
            latitude is None
            or longitude is None
            or (latitude == 0 and longitude == 0)
            or not isinstance(latitude, (int, float))
            or not isinstance(longitude, (int, float))
            or not -90 <= latitude <= 90
            or not -180 <= longitude <= 180
        ):
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
