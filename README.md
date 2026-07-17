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

## Setup and operation

Create a virtual environment, install `requirements.txt`, and run the engine
from the repository root:

```powershell
python -m venv venv
.\venv\Scripts\python.exe -m pip install -r requirements.txt
$env:PYTHONPATH = "src"
.\venv\Scripts\python.exe src\main.py
```

Source switches and the output directory are controlled by `config.yaml`.
AISStream is optional and requires `AISSTREAM_API_KEY`; when it is absent, the
other enabled collectors continue normally. Generated frontend datasets are
written to the configured output directory, while historical deduplicated
events are stored in `data/database/events.json`.

Each run builds and validates a staged release before publishing it. The
website can use `data/output/manifest.json` as its update signal and
`data/output/health.json` to display stale or degraded source coverage. The
complete file contract is documented in `docs/data-contract.md`.

Retention, maximum map-event count, and maximum artifact size are configured
in `config.yaml`. The defaults retain 30 days and at most 5,000 historical
events, publish at most 2,000 map points, and reject any artifact over 25 MB.

The scheduled GitHub workflow runs every six hours and uses only public sources
and repository storage. AISStream remains disabled automatically unless the
optional `AISSTREAM_API_KEY` repository secret is provided.

Run the local verification suite with:

```powershell
$env:PYTHONPATH = "src"
.\venv\Scripts\python.exe -m unittest discover -s tests -v
```

Publish the retained database without contacting external sources with:

```powershell
$env:PYTHONPATH = "src"
.\venv\Scripts\python.exe src\main.py --publish-existing
```


---

## Disclaimer

This project uses publicly available information.
It is designed for research, education, and OSINT analysis.
It does not provide classified or real-time military intelligence.
