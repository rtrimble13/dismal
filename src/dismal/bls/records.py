"""Flatten :class:`~dismal.bls.models.Series` into tidy records and optional wide tables.

The *long* layout has one row per (series, period). Core columns always come
first and in a fixed order so downstream consumers (spreadsheets, agents, jq)
can rely on them; catalog metadata and calculations are appended as extra
columns when requested.
"""

from __future__ import annotations

from collections.abc import Iterable, Sequence
from datetime import date
from typing import Any

from dismal.bls.models import Series
from dismal.core.records import Record, jsonable, stringify

CORE_COLUMNS: tuple[str, ...] = (
    "series_id",
    "date",
    "year",
    "period",
    "period_name",
    "frequency",
    "value",
    "footnotes",
    "latest",
)
CALCULATION_COLUMNS: tuple[str, ...] = (
    "net_change_1",
    "net_change_3",
    "net_change_6",
    "net_change_12",
    "pct_change_1",
    "pct_change_3",
    "pct_change_6",
    "pct_change_12",
)
_CATALOG_SKIP = {"series_id"}  # already a core column


def _num(value: Any) -> float | None:
    if value is None:
        return None
    try:
        return float(str(value).replace(",", ""))
    except ValueError:
        return None


def to_records(
    series: Iterable[Series],
    *,
    include_catalog: bool = False,
    include_calculations: bool = False,
    include_aspects: bool = False,
    include_annual_average_flag: bool = False,
) -> list[Record]:
    """Convert series into a list of flat dictionaries (long layout)."""
    records: list[Record] = []
    for s in series:
        catalog_cols: dict[str, Any] = {}
        if include_catalog and s.catalog:
            catalog_cols = {
                k: v for k, v in s.catalog.items() if k not in _CATALOG_SKIP and v not in ("", None)
            }
            if "series_title" in catalog_cols:  # put the title right after the id
                catalog_cols = {
                    "series_title": catalog_cols.pop("series_title"),
                    **catalog_cols,
                }
        for o in s.data:
            rec: Record = {
                "series_id": s.series_id,
                "date": o.date,
                "year": o.year,
                "period": o.period,
                "period_name": o.period_name,
                "frequency": o.frequency.value,
                "value": o.value,
                "footnotes": "; ".join(str(fn) for fn in o.footnotes),
                "latest": o.latest,
            }
            if include_annual_average_flag:
                rec["annual_average"] = o.annual_average
            if catalog_cols:
                rec.update(catalog_cols)
            if include_calculations:
                calc = o.calculations or {}
                net = calc.get("net_changes") or {}
                pct = calc.get("pct_changes") or {}
                for span in ("1", "3", "6", "12"):
                    rec[f"net_change_{span}"] = _num(net.get(span))
                    rec[f"pct_change_{span}"] = _num(pct.get(span))
            if include_aspects:
                rec["aspects"] = o.aspects or []
            records.append(rec)
    return records


def column_order(records: Sequence[Record]) -> list[str]:
    """Stable column order: core, then catalog/extra columns in first-seen order."""
    seen: dict[str, None] = {}
    for rec in records:
        for key in rec:
            seen.setdefault(key, None)
    if "value" not in seen or "series_id" not in seen:
        return list(seen)  # not data records: keep first-seen order
    core = [c for c in CORE_COLUMNS if c in seen]
    rest = [c for c in seen if c not in CORE_COLUMNS]
    return core + rest


def to_wide(records: Sequence[Record], value_column: str = "value") -> list[Record]:
    """Pivot long records to one row per period with a column per series."""
    rows: dict[tuple[date, int, str], Record] = {}
    series_ids: dict[str, None] = {}
    for rec in records:
        key = (rec["date"], rec["year"], rec["period"])
        row = rows.setdefault(
            key,
            {
                "date": rec["date"],
                "year": rec["year"],
                "period": rec["period"],
                "period_name": rec["period_name"],
            },
        )
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
