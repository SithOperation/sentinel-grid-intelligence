"""
Event Classification Engine

Assigns intelligence categories.
"""


def classify_events(events):


    for event in events:

        # Preserve existing intelligence classifications
        if event.get("classification") not in [None, "", "general"]:

            continue

        text = (

            event.get(
                "title",
                ""
            )

            +

            event.get(
                "description",
                ""
            )

        ).lower()



        if any(word in text for word in
               [
                   "missile",
                   "strike",
                   "attack",
                   "battle"
               ]):

            event["classification"] = "conflict"



        elif any(word in text for word in
                 [
                     "cyber",
                     "malware",
                     "ransomware"
                 ]):

            event["classification"] = "cyber"



        elif any(word in text for word in
                 [
                     "ship",
                     "vessel",
                     "naval"
                 ]):

            event["classification"] = "maritime"



        elif any(word in text for word in
                 [
                     "aircraft",
                     "flight"
                 ]):

            event["classification"] = "air"



        else:

            event["classification"] = "general"



    return events