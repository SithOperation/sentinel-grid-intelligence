import hashlib


def create_event_hash(event):

    unique_string = (
        str(event.get("event_type")) +
        str(event.get("title")) +
        str(event.get("location")) +
        str(event.get("description"))
    )

    return hashlib.sha256(
        unique_string.encode()
    ).hexdigest()



def remove_duplicates(events):

    seen = set()
    unique_events = []


    for event in events:

        event_hash = create_event_hash(event)

        if event_hash not in seen:

            seen.add(event_hash)

            event["event_hash"] = event_hash

            unique_events.append(event)


    return unique_events