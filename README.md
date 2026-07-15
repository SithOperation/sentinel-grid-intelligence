# Sentinel Grid Intelligence

## Open Source Global Conflict & Security Intelligence Platform

Sentinel Grid Intelligence is an OSINT/GEOINT collection and processing
platform designed to gather publicly available global security information,
normalize intelligence events, and provide structured data for visualization
through MapLibre.

---

## Purpose

The system collects and processes:

- Conflict events
- Military activity reports
- Aircraft activity
- Maritime activity
- Satellite observations
- Cyber security events
- Humanitarian events


---

## Architecture

Public Sources

↓

Collectors

↓

Processing Engine

↓

Confidence Scoring

↓

JSON / GeoJSON Output

↓

Sentinel Grid MapLibre Frontend


---

## Technology Stack

Backend:

- Python
- Requests
- Pandas
- BeautifulSoup
- GeoJSON


Automation:

- GitHub Actions


Frontend:

- MapLibre GL JS


Future:

- PostgreSQL
- PostGIS
- FastAPI


---

## Disclaimer

This project uses publicly available information.
It is designed for research, education, and OSINT analysis.
It does not provide classified or real-time military intelligence.