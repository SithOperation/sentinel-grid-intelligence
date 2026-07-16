"""
Conflict Intelligence Collector

Source:
News API abstraction layer

Tracks:
- conflict reporting
- geopolitical instability
- military activity
- humanitarian conflict events

Output:
Sentinel Grid standardized event format
"""


from api.news import fetch
from models.event_model import create_event



CONFLICT_KEYWORDS = [

    "war",
    "conflict",
    "attack",
    "military",
    "missile",
    "strike",
    "airstrike",
    "troops",
    "invasion",
    "weapon",
    "armed",
    "violence",
    "battle",
    "ceasefire"

]



def is_conflict_related(text):

    text = text.lower()


    for word in CONFLICT_KEYWORDS:

        if word in text:

            return True


    return False




def create_conflict_event(article):


    source = article.get(

        "source",

        "Unknown"

    )


    event = create_event(

        event_type="conflict",

        classification="conflict_report",

        priority="high",

        title=article.get(

            "title",

            "Conflict Intelligence Report"

        ),

        description=article.get(

            "description",

            ""

        ),

        source=[

            source

        ],

        confidence=70

    )


    event["equipment"] = []


    event["verification"] = {


        "confirmed":

        False,


        "source_count":

        1

    }


    return event




def collect_conflicts():

    events = []


    print(

        "[+] Collecting conflict intelligence"

    )


    try:

        articles = fetch()


        source_counts = {}



        for article in articles:


            text = (

                article.get(

                    "title",

                    ""

                )

                +

                article.get(

                    "description",

                    ""

                )

            )



            if is_conflict_related(text):


                event = create_conflict_event(

                    article

                )


                events.append(

                    event

                )



                source = article.get(

                    "source",

                    "Unknown"

                )


                source_counts[source] = (

                    source_counts.get(

                        source,

                        0

                    )

                    + 1

                )



        for source, count in source_counts.items():

            print(

                f"[+] {source} conflict events: {count}"

            )


    except Exception as error:


        print(

            "[!] Conflict collector failed:",

            error

        )


    return events