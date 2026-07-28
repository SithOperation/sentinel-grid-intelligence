"""
Event Classification Engine

Assigns broad intelligence categories.

Preserves detailed classifications
created by collectors.
"""


def classify_events(events):

    for event in events:
        event_type = event.get("event_type")
        if event_type in {
            "earthquake",
            "volcano",
            "weather_alert",
            "wildfire",
            "flood",
            "tropical_cyclone",
            "natural_hazard",
        }:
            event["category"] = event_type
            continue
        text = (event.get("title", "") + event.get("description", "")).lower()

        if any(
            word in text
            for word in ["missile", "strike", "attack", "battle", "war", "troops"]
        ):
            event["category"] = "conflict"

        else:
            event.setdefault("category", "general")

    return events
