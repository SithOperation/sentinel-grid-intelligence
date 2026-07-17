"""
Sentinel Grid Event Deduplication

Creates stable event fingerprints.

Features:
- CVE identity for cyber events
- Location awareness
- Source aggregation
- Duplicate tracking
"""


import hashlib



def clean(value):

    if value is None:

        return ""

    return str(value).strip().lower()



def create_event_hash(event):


    event_type = clean(

        event.get(
            "event_type"
        )

    )



    # Cyber events are unique by CVE

    if event_type == "cyber":


        cve = (

            event.get(
                "threat",
                {}
            )
            .get(
                "cve"
            )

        )


        if cve:


            return hashlib.sha256(

                clean(
                    cve
                ).encode()

            ).hexdigest()

    if event_type == "aircraft":
        aircraft = event.get("aircraft", {})
        sensor_identity = clean(aircraft.get("icao")) + clean(event.get("timestamp"))
        if sensor_identity:
            return hashlib.sha256(sensor_identity.encode()).hexdigest()

    if event_type == "maritime":
        vessel = event.get("vessel", {})
        sensor_identity = clean(vessel.get("mmsi")) + clean(event.get("timestamp"))
        if sensor_identity:
            return hashlib.sha256(sensor_identity.encode()).hexdigest()

    if event_type == "satellite":
        observation_id = event.get("observation", {}).get("event_id")
        if observation_id:
            return hashlib.sha256(clean(observation_id).encode()).hexdigest()



    location = event.get(

        "location",

        {}

    )


    location_key = (

        clean(
            location.get(
                "country"
            )
        )

        +

        clean(
            location.get(
                "region"
            )
        )

    )



    identity = (

        event_type

        +

        clean(
            event.get(
                "title"
            )
        )

        +

        location_key

    )



    return hashlib.sha256(

        identity.encode()

    ).hexdigest()




def remove_duplicates(events):


    seen = {}

    results = []



    for event in events:


        event_hash = create_event_hash(

            event

        )



        if event_hash in seen:


            existing = seen[event_hash]


            existing["duplicate_count"] = (

                existing.get(

                    "duplicate_count",

                    1

                )

                +

                event.get("duplicate_count", 1)

            )



            verification = existing.setdefault("verification", {})
            existing_sources = existing.get("source", [])
            if not isinstance(existing_sources, list):
                existing_sources = [existing_sources]
            new_sources = event.get("source", [])
            if not isinstance(new_sources, list):
                new_sources = [new_sources]
            existing["source"] = list(dict.fromkeys(existing_sources + new_sources))
            verification["source_count"] = len(existing["source"])


            continue



        event["event_hash"] = event_hash

        event["event_id"] = f"SG-{event_hash[:12]}"


        event["duplicate_count"] = 1



        seen[event_hash] = event


        results.append(event)



    return results
