"""Shared bounded JSON transport for unauthenticated official APIs."""

from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Any, Protocol

import requests


class ProviderError(RuntimeError):
    """A safe, user-facing provider retrieval error."""


@dataclass(frozen=True, slots=True)
class JSONResponse:
    data: Any
    size_bytes: int


class HTTPSession(Protocol):
    def get(self, url: str, **kwargs: Any) -> Any: ...


class BoundedJSONTransport:
    """Retrieve one HTTPS JSON document with explicit time and size limits."""

    def __init__(
        self,
        *,
        connect_timeout_seconds: float,
        read_timeout_seconds: float,
        max_response_bytes: int,
        headers: dict[str, str],
        session: HTTPSession | None = None,
    ) -> None:
        self.connect_timeout_seconds = connect_timeout_seconds
        self.read_timeout_seconds = read_timeout_seconds
        self.max_response_bytes = max_response_bytes
        self.headers = headers
        self.session = session or requests.Session()

    def get(self, url: str) -> JSONResponse:
        response = None
        try:
            response = self.session.get(
                url,
                headers=self.headers,
                timeout=(self.connect_timeout_seconds, self.read_timeout_seconds),
                stream=True,
            )
            response.raise_for_status()
            declared = response.headers.get("Content-Length")
            if declared and int(declared) > self.max_response_bytes:
                raise ProviderError("provider response exceeds configured size limit")
            chunks: list[bytes] = []
            size = 0
            for chunk in response.iter_content(chunk_size=65_536):
                size += len(chunk)
                if size > self.max_response_bytes:
                    raise ProviderError(
                        "provider response exceeds configured size limit"
                    )
                chunks.append(chunk)
        except requests.Timeout as error:
            raise ProviderError("provider request timed out") from error
        except requests.RequestException as error:
            raise ProviderError(f"provider request failed: {error}") from error
        except (TypeError, ValueError) as error:
            raise ProviderError(
                "provider returned an invalid content length"
            ) from error
        finally:
            if response is not None:
                response.close()

        try:
            return JSONResponse(json.loads(b"".join(chunks)), size)
        except (UnicodeDecodeError, json.JSONDecodeError) as error:
            raise ProviderError("provider returned malformed JSON") from error
