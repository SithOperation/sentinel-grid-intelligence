"""
GDACS API Client

Global Disaster Alert and Coordination System

Provides:
- earthquakes
- floods
- storms
- volcanoes
- humanitarian disaster alerts
"""

import requests
import xml.etree.ElementTree as ET


GDACS_URL = (
    "https://www.gdacs.org/xml/rss.xml"
)


HEADERS = {

    "User-Agent":

    "Sentinel-Grid-Intelligence/1.0"

}



def fetch():

    """
    Retrieve GDACS disaster alerts.

    Returns:
        list of XML item elements
    """

    try:

        response = requests.get(

            GDACS_URL,

            headers=HEADERS,

            timeout=20

        )


        response.raise_for_status()


        root = ET.fromstring(

            response.content

        )


        events = root.findall(

            ".//item"

        )


        return events



    except Exception as error:


        print(

            "[!] GDACS API failed:",

            error

        )


        return []