"""
CISA Known Exploited Vulnerabilities API Client

Source:
CISA KEV Catalog

Provides:
- CVE IDs
- vendors
- products
- vulnerability descriptions
- exploitation status
"""

import requests


CISA_KEV_URL = (
    "https://www.cisa.gov/sites/default/files/feeds/"
    "known_exploited_vulnerabilities.json"
)


HEADERS = {

    "User-Agent":

    "Sentinel-Grid-Intelligence/1.0"

}



def fetch():

    """
    Retrieve CISA Known Exploited Vulnerabilities.
    """

    try:

        response = requests.get(

            CISA_KEV_URL,

            headers=HEADERS,

            timeout=20

        )


        response.raise_for_status()


        data = response.json()


        return data.get(

            "vulnerabilities",

            []

        )


    except Exception as error:


        print(

            "[!] CISA API failed:",

            error

        )


        return []