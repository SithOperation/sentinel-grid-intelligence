"""
News RSS API Client

Sources:
- BBC World News RSS
- UN News RSS
- NATO News RSS
- Crisis Group RSS

Provides:
- article titles
- descriptions
- links
- source metadata
"""


import requests
import xml.etree.ElementTree as ET



NEWS_FEEDS = [

    {
        "name": "BBC World News",
        "url":
        "https://feeds.bbci.co.uk/news/world/rss.xml"
    },


    {
        "name": "UN News",
        "url":
        "https://news.un.org/feed/subscribe/en/news/all/rss.xml"
    },


    {
        "name": "NATO News",
        "url":
        "https://www.nato.int/cps/en/natohq/news.htm"
    },


    {
        "name": "Crisis Group",
        "url":
        "https://www.crisisgroup.org/rss.xml"
    }

]



HEADERS = {

    "User-Agent":

    "Sentinel-Grid-Intelligence/1.0"

}



def parse_feed(xml_data):

    articles = []


    try:

        root = ET.fromstring(
            xml_data
        )


        for item in root.findall(
            ".//item"
        )[:10]:


            articles.append(

                {

                    "title":

                    item.findtext(
                        "title",
                        "Unknown"
                    ),


                    "description":

                    item.findtext(
                        "description",
                        ""
                    ),


                    "link":

                    item.findtext(
                        "link",
                        ""
                    )

                }

            )


    except Exception as error:


        print(

            "[!] RSS parsing failed:",

            error

        )


    return articles




def fetch():


    articles = []



    for feed in NEWS_FEEDS:


        try:


            response = requests.get(

                feed["url"],

                headers=HEADERS,

                timeout=15

            )


            response.raise_for_status()



            feed_articles = parse_feed(

                response.text

            )



            for article in feed_articles:


                article["source"] = feed["name"]


                articles.append(

                    article

                )



            print(

                f"[+] {feed['name']} articles collected: {len(feed_articles)}"

            )



        except Exception as error:


            print(

                f"[!] {feed['name']} failed:",

                error

            )



    return articles