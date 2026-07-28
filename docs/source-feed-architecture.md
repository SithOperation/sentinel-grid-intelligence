# Sentinel Source Feed architecture

The Source Feed is an optional discovery capability inside a mandatory,
versioned publication artifact. `source_feed.json` exists in every release,
even when no adapter returns a usable item.

> Feed inclusion is based on source usefulness. Map inclusion is based on
> defensible event geography. Claim verification is evaluated independently
> from location confidence.

The map remains Sentinel's primary interface. Location confidence, claim
confidence, and event-association confidence are separate fields. An adapter
failure degrades source-feed health and cannot prevent core Sentinel
publication.

All public records use the release publication ID from `manifest.json`.
Internal response evidence is bounded and never published. Active feed
retention is based on `published_at`; a documented discovery-time fallback is
permitted only when the adapter cannot establish an original timestamp.

## Reddit discovery policy

Sentinel polls one combined public Reddit search RSS feed for the controlled
subreddit allowlist. One request covers all configured communities, which
limits traffic and avoids making one community's availability a publication
dependency. A bounded last-known-good Atom response may be used when Reddit
rate-limits a run; cached items still pass the normal 72-hour retention gate
and the feed reports `stale` or `partial`.

Every Reddit source has a tier from 1 (breaking-news or verification focused)
through 3 (analysis). The tier affects only the initial claim-confidence
baseline. It never verifies a claim.

The search vocabulary includes regional actors, military and disaster
indicators, and the terms `nuclear` and `nuke`. Keyword matches make a post
relevant to the feed but do not independently make it map eligible. A Reddit
post becomes a `reddit_report` map event only when it also contains a
recognized city-level location and an event indicator. Such events remain
source-reported and unverified.

