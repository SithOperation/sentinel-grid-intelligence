"""Official X API v2 transport with bounded retry behavior."""

from __future__ import annotations

import json
import random
import time
from collections.abc import Callable, Mapping
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen


class XCollectionError(RuntimeError):
    """Base error for a failed X collection boundary."""


class XAuthenticationError(XCollectionError):
    """X credentials are absent or rejected."""


class XRateLimitError(XCollectionError):
    """X rate limiting remained exhausted."""


class XProviderError(XCollectionError):
    """X returned unavailable or malformed provider data."""


class XApiTransport:
    """Fetch JSON objects from X without exposing credentials."""

    def __init__(
        self,
        retries: int = 3,
        backoff_seconds: float = 1.0,
        timeout_seconds: float = 30.0,
        *,
        sleeper: Callable[[float], None] = time.sleep,
    ) -> None:
        self.retries = retries
        self.backoff_seconds = backoff_seconds
        self.timeout_seconds = timeout_seconds
        self.sleeper = sleeper

    def get(self, url: str, bearer_token: str) -> Mapping[str, Any]:
        for attempt in range(self.retries + 1):
            request = Request(
                url,
                headers={
                    "Authorization": f"Bearer {bearer_token}",
                    "Accept": "application/json",
                    "User-Agent": "SentinelGrid/1.0",
                },
            )
            try:
                with urlopen(request, timeout=self.timeout_seconds) as response:
                    value = json.load(response)
                if not isinstance(value, dict):
                    raise XProviderError("X API response must be a JSON object")
                return value
            except HTTPError as error:
                if error.code in {401, 403}:
                    raise XAuthenticationError(
                        f"X API authentication failed with HTTP {error.code}"
                    ) from error
                retryable = error.code == 429 or 500 <= error.code < 600
                if not retryable or attempt == self.retries:
                    error_type = (
                        XRateLimitError if error.code == 429 else XProviderError
                    )
                    raise error_type(
                        f"X API request failed with HTTP {error.code}"
                    ) from error
            except (json.JSONDecodeError, UnicodeDecodeError, TypeError) as error:
                raise XProviderError("X API returned malformed JSON") from error
            except (TimeoutError, URLError, OSError) as error:
                if attempt == self.retries:
                    raise XProviderError(f"X API request failed: {error}") from error
            delay = self.backoff_seconds * (2**attempt) + random.uniform(0, 0.25)
            self.sleeper(delay)
        raise AssertionError("X retry loop exhausted")
