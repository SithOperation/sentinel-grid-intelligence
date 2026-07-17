"""Sanitize untrusted feed text before it reaches static frontend data."""

from html import unescape
from html.parser import HTMLParser
from urllib.parse import urlparse


class _TextExtractor(HTMLParser):
    def __init__(self):
        super().__init__()
        self.parts = []

    def handle_data(self, data):
        self.parts.append(data)


def plain_text(value, max_length):
    parser = _TextExtractor()
    try:
        parser.feed(str(value or ""))
        value = " ".join(parser.parts)
    except (TypeError, ValueError):
        value = str(value or "")
    return " ".join(unescape(value).split())[:max_length]


def safe_url(value):
    value = str(value or "").strip()
    parsed = urlparse(value)
    return value if parsed.scheme in {"http", "https"} and parsed.netloc else ""
