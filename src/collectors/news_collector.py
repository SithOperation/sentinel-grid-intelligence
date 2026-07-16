"""
News Intelligence Collector

Source:
News API abstraction layer

Tracks:
- geopolitical reporting
- international events
- diplomatic activity
- global security developments

Output:
Sentinel Grid standardized event format
"""


from api.news import fetch
from models.event_model import create_event



def create_news_event(article):


    source = article.get(

        "source",

        "Unknown"

    )


    event = create_event(

        event_type="news",

        classification="geopolitical_reporting",

        priority="medium",

        title=article.get(

            "title",

            "Global news event"

        ),

        description=article.get(

            "description",

            ""

        ),

        source=[

            source

        ],

        confidence=60

    )



    event["category"] = "global"



    event["verification"] = {


        "confirmed":

        True,


        "source_count":

        1

    }



    return event




def collect_news():


    events = []



    print(

        "[+] Collecting news intelligence"

    )



    try:


        articles = fetch()



        source_counts = {}



        for article in articles[:50]:


            event = create_news_event(

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

                +

                1

            )



        for source, count in source_counts.items():


            print(

                f"[+] {source} news events: {count}"

            )



    except Exception as error:


        print(

            "[!] News collector failed:",

            error

        )



    return events