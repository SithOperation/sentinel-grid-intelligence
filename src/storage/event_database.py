import json
from datetime import datetime, timedelta, timezone

from processors.event_deduplication import remove_duplicates
from settings import PROJECT_ROOT

DATABASE_PATH = PROJECT_ROOT / "data/database/events.json"


def load_events():

    if not DATABASE_PATH.exists():
        return []

    with open(DATABASE_PATH, "r", encoding="utf-8") as file:
        events = json.load(file)

    if not isinstance(events, list):
        raise TypeError("Event database must contain a JSON array")
    return events


def save_events(events):

    DATABASE_PATH.parent.mkdir(parents=True, exist_ok=True)

    with open(DATABASE_PATH, "w", encoding="utf-8") as file:
        json.dump(events, file, indent=4)


def append_events(new_events):

    existing = load_events()

    existing.extend(new_events)
    existing = remove_duplicates(existing)

    save_events(existing)

    return existing


def apply_retention(events, max_age_hours=72, max_events=5000, now=None):
    now = now or datetime.now(timezone.utc)
    cutoff = now - timedelta(hours=max_age_hours)
    retained = []

    for event in events:
        timestamp = event.get("timestamp")
        try:
            parsed = datetime.fromisoformat(str(timestamp).replace("Z", "+00:00"))
            if parsed.tzinfo is None:
                parsed = parsed.replace(tzinfo=timezone.utc)
        except (TypeError, ValueError):
            continue
        if event.get("event_type") == "weather_alert":
            weather = event.get("weather", {})
            expiration = weather.get("ends") or weather.get("expires")
            try:
                expires = datetime.fromisoformat(str(expiration).replace("Z", "+00:00"))
                if expires.tzinfo is None:
                    expires = expires.replace(tzinfo=timezone.utc)
            except (TypeError, ValueError):
                continue
            if expires < now:
                continue
        if cutoff <= parsed <= now:
            retained.append((parsed, event))

    retained.sort(key=lambda item: item[0])
    return [event for _, event in retained[-max_events:]]
