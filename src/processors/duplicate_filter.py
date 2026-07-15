"""
Duplicate Event Filter
"""


def remove_duplicates(events):


    seen = set()

    results = []


    for event in events:


        key = (

            event.get("title"),

            event.get("timestamp")

        )


        if key not in seen:

            seen.add(key)

            results.append(event)



    return results
