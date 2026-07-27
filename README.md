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
- Explicitly configured public X/Twitter status reports


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
AISStream maritime collection is disabled by default and is not configured in
the scheduled workflow. Generated frontend datasets are written to the
configured output directory, while historical deduplicated events are stored
in `data/database/events.json`.

Each run builds and validates a staged release before publishing it. The
website can use `data/output/manifest.json` as its update signal and
`data/output/health.json` to display stale or degraded source coverage. The
complete file contract is documented in `docs/data-contract.md`.

Retention, maximum map-event count, and maximum artifact size are configured
in `config.yaml`. The backend enforces one shared hard 48-hour event window,
retains at most 5,000 events, publishes at most 2,000 map points, and rejects
any artifact over 25 MB.

The scheduled GitHub workflow runs every six hours and uses repository storage.
X collection needs no secret: it reads only the explicit public status URLs in
`sources.x.urls`. It does not crawl timelines or use the official X API.
Maritime tracking remains disabled. A failed optional source degrades health
without preventing other collectors or discarding valid retained X reports in
favor of an invented empty result.

Configure each X post with operator-supplied classification and location data:

```yaml
sources:
  x:
    enabled: true
    connection_timeout_seconds: 5
    request_timeout_seconds: 10
    request_interval_seconds: 2
    max_response_bytes: 1000000
    max_urls_per_run: 25
    cache_file: data/cache/x_public_posts.json
    urls:
      - url: https://x.com/example/status/1234567890123456789
        source_class: official
        location_name: Example City
        latitude: 0.0
        longitude: 0.0
        location_precision: city
        event_type: early_report
```

Accepted `x.com` and `twitter.com` variants are normalized to
`https://x.com/<account>/status/<status_id>`. Only public JSON-LD or Open Graph
metadata is consumed; inaccessible, login-gated, deleted, malformed, or stale
posts are rejected independently.

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
