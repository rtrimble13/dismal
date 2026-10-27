"""Flatten :class:`~dismal.fred.models.Series` into tidy records and optional wide tables.

The *long* layout has one row per (series, date). Core columns always come
first and in a fixed order so downstream consumers (spreadsheets, agents, jq)
can rely on them; vintage columns and series metadata are appended when
requested.
"""

from __future__ import annotations

from collections.abc import Iterable, Sequence
from datetime import date
from typing import Any

from dismal.core.records import Record, jsonable, stringify
from dismal.fred.models import Series

CORE_COLUMNS: tuple[str, ...] = ("series_id", "date", "value")
REALTIME_COLUMNS: tuple[str, ...] = ("realtime_start", "realtime_end")
META_COLUMNS: tuple[str, ...] = (
    "title",
    "units",
    "frequency",
    "seasonal_adjustment",
    "last_updated",
)
_ORDERED = CORE_COLUMNS + REALTIME_COLUMNS + META_COLUMNS


def to_records(
    series: Iterable[Series],
    *,
    include_meta: bool = False,
    include_realtime: bool = False,
) -> list[Record]:
    """Convert series into a list of flat dictionaries (long layout)."""
    records: list[Record] = []
    for s in series:
        meta: dict[str, Any] = {}
        if include_meta and s.info:
            meta = {
                "title": s.info.title,
                "units": s.info.units,
                "frequency": s.info.frequency,
                "seasonal_adjustment": s.info.seasonal_adjustment_short
                or s.info.seasonal_adjustment,
                "last_updated": s.info.last_updated,
            }
        for o in s.data:
            rec: Record = {"series_id": s.series_id, "date": o.date, "value": o.value}
            if include_realtime:
                rec["realtime_start"] = o.realtime_start
                rec["realtime_end"] = o.realtime_end
            if meta:
                rec.update(meta)
            records.append(rec)
    return records


def column_order(records: Sequence[Record]) -> list[str]:
    """Stable column order: core, vintage, metadata, then extras in first-seen order."""
    seen: dict[str, None] = {}
    for rec in records:
        for key in rec:
            seen.setdefault(key, None)
    if "value" not in seen or "series_id" not in seen:
        return list(seen)  # not data records: keep first-seen order
    head = [c for c in _ORDERED if c in seen]
    rest = [c for c in seen if c not in _ORDERED]
    return head + rest


def to_wide(records: Sequence[Record], value_column: str = "value") -> list[Record]:
    """Pivot long records to one row per date with a column per series."""
    rows: dict[date, Record] = {}
    series_ids: dict[str, None] = {}
    for rec in records:
        row = rows.setdefault(rec["date"], {"date": rec["date"]})
        row[rec["series_id"]] = rec.get(value_column)
        series_ids.setdefault(rec["series_id"], None)
    out: list[Record] = []
    for key in sorted(rows):
        row = rows[key]
        for sid in series_ids:
            row.setdefault(sid, None)
        out.append(row)
    return out


__all__ = [
    "CORE_COLUMNS",
    "Record",
    "column_order",
    "jsonable",
    "stringify",
    "to_records",
    "to_wide",
]
