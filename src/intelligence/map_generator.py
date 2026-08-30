MAP_EVENT_TYPES = {
    "conflict",
    "humanitarian",
    "earthquake",
    "volcano",
    "weather_alert",
    "wildfire",
    "flood",
    "tropical_cyclone",
    "natural_hazard",
    "x_report",
    "reddit_report",
    "europe_security",
}


def generate_map_events(events):

    map_events = []

    for event in events:
        if event.get("event_type") not in MAP_EVENT_TYPES:
            continue
        location = event.get("location", {})

        latitude = location.get("latitude", 0)

        longitude = location.get("longitude", 0)

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
        if event.get("event_type") == "conflict" and not location.get("city"):
            # Text-derived country centers are not sufficiently precise for a
            # conflict marker. Direct collector geometry remains eligible.
            continue

        map_event = {
            "event_id": event.get("event_id"),
            "type": event.get("event_type", "unknown"),
            "title": event.get("title"),
            "description": event.get("description"),
            "latitude": latitude,
            "longitude": longitude,
            "priority": event.get("priority", "unknown"),
            "threat_level": event.get("threat_level", "unknown"),
            "confidence": event.get("confidence", 0),
            "timestamp": event.get("timestamp"),
            "url": event.get("url", ""),
            "classification": event.get("classification", "unknown"),
            "source": event.get("source", []),
        }
        if event.get("event_type") == "europe_security":
            map_event.update(
                {
                    "status": event.get("status", "unverified"),
                    "source_type": event.get("source_type"),
                    "source_perspective": event.get("source_perspective"),
                    "actor_reporting": event.get("actor_reporting"),
                    "actor_subject": event.get("actor_subject"),
                    "source_count": event.get("source_count", 1),
                    "independent_source_count": event.get(
                        "independent_source_count", 1
                    ),
                    "event_cluster_id": event.get("event_cluster_id"),
                    "location_precision": location.get("precision"),
                    "europe_layers": event.get("europe_layers", []),
                }
            )
        map_events.append(map_event)

    return map_events
