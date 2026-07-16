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

                1

            )



            existing["verification"]["source_count"] = (

                existing["duplicate_count"]

            )


            existing["source"].extend(

                event.get(

                    "source",

                    []

                )

            )


            continue



        event["event_hash"] = event_hash


        event["duplicate_count"] = 1



        seen[event_hash] = event


        results.append(event)



    return results