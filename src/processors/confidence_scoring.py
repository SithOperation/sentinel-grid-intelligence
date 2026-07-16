"""
Confidence Scoring Engine

Calculates intelligence reliability.

Factors:
- Source reputation
- Verification count
- Existing collector confidence
- Multi-source confirmation

Output:
confidence score + confidence level
"""


SOURCE_WEIGHTS = {

    "cisa": 20,

    "nasa": 15,

    "opensky": 10,

    "aisstream": 10,

    "gdacs": 15,

    "un": 10,

    "bbc": 10,

    "reuters": 15,

    "crisis group": 10

}



def calculate_source_bonus(source):


    bonus = 0



    if isinstance(source, list):

        source_text = " ".join(
            source
        ).lower()

    else:

        source_text = str(
            source
        ).lower()



    for name, weight in SOURCE_WEIGHTS.items():

        if name in source_text:

            bonus += weight



    return bonus




def apply_confidence(events):


    for event in events:


        score = event.get(

            "confidence",

            50

        )



        source = event.get(

            "source",

            []

        )



        score += calculate_source_bonus(

            source

        )



        verification = event.get(

            "verification",

            {}

        )



        source_count = verification.get(

            "source_count",

            1

        )



        if source_count > 1:


            score += (

                source_count * 5

            )



        if score > 100:

            score = 100



        event["confidence"] = score



        if score >= 90:


            event["confidence_level"] = "verified"



        elif score >= 70:


            event["confidence_level"] = "high"



        elif score >= 40:


            event["confidence_level"] = "medium"



        else:


            event["confidence_level"] = "low"



    return events