"""Bounded atomic cache for normalized discovery evidence."""

from __future__ import annotations

import json
import os
import re
from datetime import UTC, datetime, timedelta
from pathlib import Path

_SAFE_ID = re.compile(r"^[a-z][a-z0-9_]{2,63}$")


class SourceCache:
    def __init__(
        self,
        root: str | Path,
        *,
        max_bytes: int = 1_000_000,
        max_age_hours: int = 168,
    ) -> None:
        if max_bytes < 1024 or max_age_hours < 1:
            raise ValueError("source cache limits are invalid")
        self.root = Path(root)
        self.max_bytes = max_bytes
        self.max_age = timedelta(hours=max_age_hours)

    def path_for(self, source_id: str) -> Path:
        if _SAFE_ID.fullmatch(source_id) is None:
            raise ValueError("unsafe source cache identifier")
        return self.root / f"{source_id}.json"

    def load(self, source_id: str, now: datetime) -> dict[str, object] | None:
        path = self.path_for(source_id)
        if not path.is_file() or path.stat().st_size > self.max_bytes:
            return None
        value = json.loads(path.read_text(encoding="utf-8"))
        if not isinstance(value, dict) or value.get("schema_version") != "1.0":
            return None
        cached_at = datetime.fromisoformat(str(value.get("cached_at", "")))
        if (
            cached_at.tzinfo is None
            or now.astimezone(UTC) - cached_at.astimezone(UTC) > self.max_age
        ):
            return None
        return value

    def save(self, source_id: str, value: dict[str, object]) -> None:
        path = self.path_for(source_id)
        payload = json.dumps(value, indent=2, ensure_ascii=False).encode()
        if len(payload) > self.max_bytes:
            raise ValueError("source cache payload exceeds its size limit")
        path.parent.mkdir(parents=True, exist_ok=True)
        temporary = path.with_name(f".{path.name}.{os.getpid()}.tmp")
        try:
            temporary.write_bytes(payload)
            os.replace(temporary, path)
        finally:
            temporary.unlink(missing_ok=True)
