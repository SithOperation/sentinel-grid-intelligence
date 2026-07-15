from pathlib import Path
import json


DATABASE_PATH = Path(
    "data/database/events.json"
)


def load_events():

    if not DATABASE_PATH.exists():
        return []

    with open(
        DATABASE_PATH,
        "r",
        encoding="utf-8"
    ) as file:

        return json.load(file)



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


    existing.extend(
        new_events
    )


    save_events(
        existing
    )


    return existing