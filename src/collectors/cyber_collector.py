"""
Cyber Intelligence Collector

Source:
- CISA Known Exploited Vulnerabilities Catalog

Tracks:
- exploited vulnerabilities
- vendors
- products
- CVE activity

Output:
Sentinel Grid standardized event format
"""


from api.cisa import fetch
from models.event_model import create_event



def collect_cyber():

    events = []


    try:


        vulnerabilities = fetch()



        for vuln in vulnerabilities[:25]:


            event = create_event(

                event_type="cyber",

                classification="known_exploited_vulnerability",

                priority="high",

                title=vuln.get(

                    "vulnerabilityName",

                    "Unknown vulnerability"

                ),

                description=vuln.get(

                    "shortDescription",

                    ""

                ),

                source=[

                    "CISA KEV"

                ],

                confidence=90

            )



            event["threat"] = {


                "cve":

                vuln.get(

                    "cveID"

                ),


                "vendor":

                vuln.get(

                    "vendorProject"

                ),


                "product":

                vuln.get(

                    "product"

                )

            }



            event["target"] = {


                "sector":

                "UNKNOWN",


                "organization":

                "UNKNOWN",


                "country":

                "UNKNOWN"

            }



            event["verification"] = {


                "confirmed":

                True,


                "source_count":

                1

            }



            events.append(

                event

            )



        print(

            f"[+] CISA cyber collected {len(events)} events"

        )



    except Exception as error:


        print(

            "[!] Cyber collector failed:",

            error

        )



    return events