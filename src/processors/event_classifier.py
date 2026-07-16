"""
Event Classification Engine

Assigns broad intelligence categories.

Preserves detailed classifications
created by collectors.
"""


def classify_events(events):


    for event in events:


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
                   "battle",
                   "war",
                   "troops"
               ]):

            event.setdefault(
                "category",
                "conflict"
            )



        elif any(word in text for word in
                 [
                     "cyber",
                     "malware",
                     "ransomware",
                     "vulnerability",
                     "exploit",
                     "cve"
                 ]):

            event.setdefault(
                "category",
                "cyber"
            )



        elif any(word in text for word in
                 [
                     "ship",
                     "vessel",
                     "naval"
                 ]):

            event.setdefault(
                "category",
                "maritime"
            )



        elif any(word in text for word in
                 [
                     "aircraft",
                     "flight"
                 ]):

            event.setdefault(
                "category",
                "air"
            )



        else:

            event.setdefault(
                "category",
                "general"
            )



    return events