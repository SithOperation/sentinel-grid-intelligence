"""
Sentinel Grid Threat Scoring Engine

Assigns threat scores and threat levels
to normalized intelligence events.

Threat Levels:

LOW
MEDIUM
HIGH
CRITICAL

Factors:

- Event type
- Classification
- Priority
- Confidence
- Threat indicators
- Cyber vulnerability severity
"""


def calculate_threat_score(event):


    score = 0



    event_type = event.get(

        "event_type",

        ""

    ).lower()



    classification = event.get(

        "classification",

        ""

    ).lower()



    title = event.get(

        "title",

        ""

    ).lower()



    description = event.get(

        "description",

        ""

    ).lower()



    priority = event.get(

        "priority",

        "low"

    ).lower()



    confidence = event.get(

        "confidence",

        0

    )



    text = (

        classification

        + " "

        + title

        + " "

        + description

    )



    #
    # Base event weighting
    #


    event_weights = {


        "conflict": 40,


        "cyber": 35,


        "humanitarian": 25,


        "maritime": 20,


        "aircraft": 20,


        "satellite": 15,


        "news": 10


    }



    score += event_weights.get(

        event_type,

        0

    )



    #
    # Classification weighting
    #


    high_risk_terms = [

        "attack",

        "strike",

        "airstrike",

        "military",

        "troops",

        "armed",

        "breach",

        "malware",

        "ransomware",

        "exploit",

        "vulnerability"

    ]



    critical_terms = [

        "nuclear",

        "ballistic",

        "missile",

        "invasion",

        "zero-day",

        "chemical",

        "biological",

        "mass casualty"

    ]



    for term in high_risk_terms:


        if term in text:

            score += 10



    for term in critical_terms:


        if term in text:

            score += 20



    #
    # Cyber specific scoring
    #


    if event_type == "cyber":


        threat = event.get(

            "threat",

            {}

        )


        if threat.get("cve"):

            score += 15



    #
    # Priority scoring
    #


    if priority == "critical":

        score += 25



    elif priority == "high":

        score += 15



    elif priority == "medium":

        score += 5



    #
    # Confidence scoring
    #


    if confidence >= 90:

        score += 15



    elif confidence >= 70:

        score += 10



    elif confidence >= 50:

        score += 5



    #
    # Maximum score
    #


    if score > 100:

        score = 100



    return score





def assign_threat_level(event):


    score = calculate_threat_score(

        event

    )


    event["threat_score"] = score



    if score >= 85:


        event["threat_level"] = "CRITICAL"



    elif score >= 60:


        event["threat_level"] = "HIGH"



    elif score >= 35:


        event["threat_level"] = "MEDIUM"



    else:


        event["threat_level"] = "LOW"



    return event





def analyze_threats(events):


    analyzed = []



    for event in events:


        analyzed.append(

            assign_threat_level(

                event

            )

        )



    return analyzed