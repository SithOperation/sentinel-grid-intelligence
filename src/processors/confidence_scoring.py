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

from settings import load_config


CONFIDENCE_LEVELS = load_config()["confidence"]


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


        source = event.get(

            "source",

            []

        )



        verification = event.get(

            "verification",

            {}

        )



        source_count = verification.get(

            "source_count",

            1

        )

        source_bonus = calculate_source_bonus(source)
        verification_bonus = source_count * 5 if source_count > 1 else 0

        if "base_confidence" not in event:
            # Older database records predate base_confidence and already include
            # these bonuses. Recover their base so repeated runs stay stable.
            event["base_confidence"] = max(
                0,
                event.get("confidence", 50) - source_bonus - verification_bonus,
            )

        score = event["base_confidence"] + source_bonus



        if source_count > 1:


            score += verification_bonus



        if score > 100:

            score = 100



        event["confidence"] = score



        if score >= CONFIDENCE_LEVELS["verified"]:


            event["confidence_level"] = "verified"



        elif score >= CONFIDENCE_LEVELS["high"]:


            event["confidence_level"] = "high"



        elif score >= CONFIDENCE_LEVELS["medium"]:


            event["confidence_level"] = "medium"



        else:


            event["confidence_level"] = "low"



    return events
