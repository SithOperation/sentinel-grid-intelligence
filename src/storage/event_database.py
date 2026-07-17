from pathlib import Path
import json
from datetime import datetime, timedelta, timezone

from processors.event_deduplication import remove_duplicates
from settings import PROJECT_ROOT


DATABASE_PATH = PROJECT_ROOT / "data/database/events.json"


def load_events():

    if not DATABASE_PATH.exists():
        return []

    with open(
        DATABASE_PATH,
        "r",
        encoding="utf-8"
    ) as file:

        events = json.load(file)

    if not isinstance(events, list):
        raise ValueError("Event database must contain a JSON array")
    return events



def save_events(events):

    DATABASE_PATH.parent.mkdir(
        parents=True,
        exist_ok=True
    )


    with open(
        DATABASE_PATH,
        "w",
        encoding="utf-8"
    ) as file:

        json.dump(
            events,
            file,
            indent=4
        )



def append_events(new_events):

    existing = load_events()


    existing.extend(new_events)
    existing = remove_duplicates(existing)


    save_events(
        existing
    )


    return existing


def apply_retention(events, max_age_days=30, max_events=5000, now=None):
    now = now or datetime.now(timezone.utc)
    cutoff = now - timedelta(days=max_age_days)
    retained = []

    for event in events:
        timestamp = event.get("timestamp")
        try:
            parsed = datetime.fromisoformat(str(timestamp).replace("Z", "+00:00"))
            if parsed.tzinfo is None:
                parsed = parsed.replace(tzinfo=timezone.utc)
        except (TypeError, ValueError):
            parsed = now
        if parsed >= cutoff:
            retained.append((parsed, event))

    retained.sort(key=lambda item: item[0])
    return [event for _, event in retained[-max_events:]]
