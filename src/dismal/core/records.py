"""The record type shared by every source and the value renderers used for output.

A *record* is a flat ``dict`` with JSON-friendly values: one row of tidy output.
Each source decides which columns its records carry (see its ``records`` module);
this module only knows how to render individual values.
"""

from __future__ import annotations

import json
from datetime import date
from typing import Any

Record = dict[str, Any]


def jsonable(value: Any) -> Any:
    """Make a record value JSON/CSV friendly."""
    if isinstance(value, date):
        return value.isoformat()
    return value


def stringify(value: Any) -> str:
    """Render a value for CSV / table output."""
    if value is None:
        return ""
    if isinstance(value, bool):
        return "true" if value else "false"
    if isinstance(value, date):
        return value.isoformat()
    if isinstance(value, (list, dict)):
        return json.dumps(value, separators=(",", ":"))
    if isinstance(value, float):
        return f"{value:.10g}" if abs(value) >= 1e15 else repr(value)
    return str(value)


def first_seen_columns(records: Any) -> list[str]:
    """Column names in first-seen order (the fallback when no source-specific order applies)."""
    seen: dict[str, None] = {}
    for rec in records:
        for key in rec:
            seen.setdefault(key, None)
    return list(seen)
