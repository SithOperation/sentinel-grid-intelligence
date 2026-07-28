"""Official National Weather Service active-alert adapter."""

from api.bounded_json import BoundedJSONTransport, JSONResponse

USER_AGENT = (
    "SentinelGridIntelligence/1.0 "
    "(public-safety collector; https://github.com/newho/sentinel-grid-intelligence)"
)


def fetch(
    url: str,
    *,
    connection_timeout_seconds: float,
    request_timeout_seconds: float,
    max_response_bytes: int,
    transport: BoundedJSONTransport | None = None,
) -> JSONResponse:
    client = transport or BoundedJSONTransport(
        connect_timeout_seconds=connection_timeout_seconds,
        read_timeout_seconds=request_timeout_seconds,
        max_response_bytes=max_response_bytes,
        headers={
            "Accept": "application/geo+json",
            "User-Agent": USER_AGENT,
        },
    )
    return client.get(url)
