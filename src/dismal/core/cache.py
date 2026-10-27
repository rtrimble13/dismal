"""Tiny file-based cache for slowly-changing metadata (survey, dataset and release lists)."""

from __future__ import annotations

import json
import time
from pathlib import Path
from typing import Any


class FileCache:
    def __init__(self, directory: Path) -> None:
        self.directory = directory

    def path(self, name: str) -> Path:
        return self.directory / name

    def is_fresh(self, name: str, ttl_seconds: float) -> bool:
        p = self.path(name)
        if not p.is_file():
            return False
        return (time.time() - p.stat().st_mtime) < ttl_seconds

    def read_text(self, name: str) -> str | None:
        p = self.path(name)
        return p.read_text(encoding="utf-8") if p.is_file() else None

    def write_text(self, name: str, text: str) -> Path:
        p = self.path(name)
        p.parent.mkdir(parents=True, exist_ok=True)
        tmp = p.with_suffix(p.suffix + ".tmp")
        tmp.write_text(text, encoding="utf-8")
        tmp.replace(p)
        return p

    def read_json(self, name: str) -> Any | None:
        text = self.read_text(name)
        if text is None:
            return None
        try:
            return json.loads(text)
        except json.JSONDecodeError:
            return None

    def write_json(self, name: str, obj: Any) -> Path:
        return self.write_text(name, json.dumps(obj, indent=2))

    def clear(self) -> int:
        """Delete all cached files; returns the number removed."""
        if not self.directory.is_dir():
            return 0
        removed = 0
        for p in sorted(self.directory.rglob("*")):
            if p.is_file():
                p.unlink()
                removed += 1
        return removed
