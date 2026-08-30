# Europe security collector

The collector in `src/collectors/europe_security.py` aggregates only public
RSS/Atom reporting. It does not access private, credential-protected, hacked,
or classified information. Feed HTML is reduced to plain text and is never
executed.

## Sources and polling

`config/europe_security.yaml` is the source of truth. It lists official NATO,
European media, and eight public subreddit Atom feeds with their perspective,
reliability, and conservative 10–15 minute polling guidance. Russian state
media is explicitly tagged `russian_state_media`; its candidate feed is off by
default pending an operator review of publication terms. NATO and Polish BBN
candidate URLs are also off by default because live checks on 2026-08-30 did
not return a valid syndication feed; dead endpoints are not silently treated as
healthy sources. Add a feed or
subreddit by adding one mapping with a stable ID, public HTTPS URL, source type,
perspective, reliability, polling interval, and optional subreddit name.

The workflow runs every 15 minutes. Each request has connect/read timeouts, a
bounded response size, a descriptive User-Agent, conditional ETag/Last-Modified
requests, atomic local seen-item state, and per-source failure isolation. Source
totals and failures are exported in collection health.

## Correlation and confidence

Reddit is discovery evidence, not confirmation. The parser extracts the linked
external article and canonicalizes its URL by normalizing scheme/host/trailing
slashes and removing tracking parameters. Four subreddits linking one Reuters
article remain four observations but one source and one independent domain.

Exact canonical URLs cluster first. Otherwise reports need compatible category,
time, location, and strong normalized-title similarity. Every event retains its
reports, cluster ID, first/last seen, source types/domains, source count, and
independent source count.

Confidence starts from configured source reliability, increases only for
independent underlying domains, and is capped at 0.92. Official reporting is
labelled `officially_reported`, not automatically confirmed. Reddit votes and
comment counts never affect confidence. `actor_reporting` identifies who made
the report; `actor_subject` identifies who the report discusses.

## Classification and mapping

Term groups are editable in YAML. Event categories are normalized, while
coordinates come solely from a controlled place table and carry city, region,
or country precision. Reports without a supported location remain in the world
event and intelligence-brief outputs but are not placed on the map.
