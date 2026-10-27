"""Typed representations of BEA API responses."""

from __future__ import annotations

import datetime as _dt
import re
from collections.abc import Iterable, Mapping
from dataclasses import dataclass, field
from typing import Any

from dismal.bea.datasets import (
    FREQUENCY,
    TIME_COLUMNS,
    VALUE_COLUMNS,
    DatasetInfo,
    dataset_info,
    series_key_columns,
    title_columns,
)
from dismal.bea.periods import Frequency, PeriodInfo, parse_period, period_from_row

SERIES_ID_SEPARATOR = ":"


@dataclass(frozen=True)
class Dataset:
    """One entry of ``GetDataSetList``."""

    name: str
    description: str

    @classmethod
    def from_api(cls, raw: Mapping[str, Any]) -> Dataset:
        return cls(
            name=str(raw.get("DatasetName", "")).strip(),
            description=str(raw.get("DatasetDescription", "")).strip(),
        )


def _flag(value: Any) -> bool:
    return str(value).strip().lower() in {"1", "true", "yes", "y"}


@dataclass(frozen=True)
class Parameter:
    """One entry of ``GetParameterList``."""

    name: str
    data_type: str = ""
    description: str = ""
    required: bool = False
    default: str = ""
    multiple: bool = False
    all_value: str = ""

    @classmethod
    def from_api(cls, raw: Mapping[str, Any]) -> Parameter:
        return cls(
            name=str(raw.get("ParameterName", "")).strip(),
            data_type=str(raw.get("ParameterDataType", "") or ""),
            description=str(raw.get("ParameterDescription", "") or ""),
            required=_flag(raw.get("ParameterIsRequiredFlag")),
            default=str(raw.get("ParameterDefaultValue", "") or ""),
            multiple=_flag(raw.get("MultipleAcceptedFlag")),
            all_value=str(raw.get("AllValue", "") or ""),
        )

    def to_record(self) -> dict[str, Any]:
        return {
            "parameter": self.name,
            "required": self.required,
            "multiple": self.multiple,
            "all_value": self.all_value,
            "default": self.default,
            "type": self.data_type,
            "description": self.description,
        }


@dataclass(frozen=True)
class Note:
    ref: str
    text: str

    @classmethod
    def from_api(cls, raw: Mapping[str, Any]) -> Note:
        return cls(ref=str(raw.get("NoteRef", "") or ""), text=str(raw.get("NoteText", "") or ""))

    def __str__(self) -> str:
        return f"{self.ref}: {self.text}" if self.ref else self.text


_NULL_VALUES = {
    "",
    "-",
    "--",
    "---",
    "(d)",
    "(na)",
    "(n/a)",
    "(*)",
    "(x)",
    "(l)",
    "(s)",
    "(**)",
    "n.a.",
    "n/a",
    "na",
    "(not available)",
}


def parse_value(raw: Any) -> float | None:
    """Convert the API's ``DataValue`` to a float; suppressed/missing markers become ``None``."""
    if raw is None:
        return None
    if isinstance(raw, bool):
        return float(raw)
    if isinstance(raw, (int, float)):
        return float(raw)
    text = str(raw).strip().replace(",", "")
    if text.lower() in _NULL_VALUES:
        return None
    try:
        return float(text)
    except ValueError:
        return None


def parse_unit_mult(raw: Any) -> int | None:
    if raw in (None, ""):
        return None
    try:
        return int(str(raw).strip())
    except ValueError:
        return None


_SNAKE_RE_1 = re.compile(r"(?<=[a-z0-9])(?=[A-Z])")
_SNAKE_RE_2 = re.compile(r"(?<=[A-Z])(?=[A-Z][a-z])")
_SNAKE_OVERRIDES = {
    "IndustrYDescription": "industry_description",  # sic, the API's own spelling
    "CL_UNIT": "unit",
    "UNIT_MULT": "unit_mult",
    "NoteRef": "note_ref",
    "DataValue": "value",
}


def snake_case(name: str) -> str:
    """Convert an API column name: ``TableName`` -> ``table_name``, ``TableID`` -> ``table_id``."""
    if name in _SNAKE_OVERRIDES:
        return _SNAKE_OVERRIDES[name]
    text = _SNAKE_RE_2.sub("_", _SNAKE_RE_1.sub("_", name))
    return re.sub(r"__+", "_", text).strip("_").lower()


@dataclass
class Observation:
    """One data point of a series."""

    period: str  # BEA time period code: 2024, 2024Q1, 2024M03
    raw_value: str
    value: float | None
    unit: str | None = None
    unit_mult: int | None = None
    note_ref: str = ""
    raw: dict[str, Any] = field(default_factory=dict)

    @property
    def period_info(self) -> PeriodInfo:
        return parse_period(self.period)

    @property
    def frequency(self) -> Frequency:
        return self.period_info.frequency

    @property
    def year(self) -> int:
        return self.period_info.year

    @property
    def date(self) -> _dt.date:
        """First day of the observation period."""
        return self.period_info.start_date()

    @property
    def end_date(self) -> _dt.date:
        return self.period_info.end_date()

    @classmethod
    def from_row(cls, row: Mapping[str, Any]) -> Observation | None:
        """Build an observation from an API data row; ``None`` if it has no time period."""
        info = period_from_row(row)
        if info is None:
            return None
        raw_value = row.get("DataValue")
        if raw_value in (None, "") and "DataValueUnformatted" in row:
            raw_value = row.get("DataValueUnformatted")
        unit = row.get("CL_UNIT")
        return cls(
            period=info.code,
            raw_value="" if raw_value is None else str(raw_value),
            value=parse_value(row.get("DataValueUnformatted", raw_value)),
            unit=str(unit) if unit not in (None, "") else None,
            unit_mult=parse_unit_mult(row.get("UNIT_MULT")),
            note_ref=str(row.get("NoteRef", "") or ""),
            raw=dict(row),
        )


@dataclass
class Series:
    """A BEA time series: the rows of one ``GetData`` response that share a key."""

    series_id: str
    title: str = ""
    data: list[Observation] = field(default_factory=list)
    attributes: dict[str, Any] = field(default_factory=dict)

    def merge(self, other: Series) -> None:
        """Merge observations from ``other`` (same series) without duplicates."""
        seen = {o.period for o in self.data}
        for obs in other.data:
            if obs.period not in seen:
                self.data.append(obs)
                seen.add(obs.period)
        if other.title and not self.title:
            self.title = other.title
        for k, v in other.attributes.items():
            self.attributes.setdefault(k, v)

    def sort(self) -> None:
        self.data.sort(key=lambda o: o.period_info.sort_key)

    @property
    def latest(self) -> Observation | None:
        return self.data[-1] if self.data else None


def _attribute_columns(info: DatasetInfo, row: Mapping[str, Any], key_cols: list[str]) -> list[str]:
    skip = set(TIME_COLUMNS) | (set(VALUE_COLUMNS) - {"METRIC_NAME"})
    skip |= set(title_columns(info, row))
    if len(key_cols) == 1:  # the key *is* the series id; keep composite parts
        skip.add(key_cols[0])
    return [c for c in row if c not in skip]


def series_id_of(info: DatasetInfo, row: Mapping[str, Any]) -> str:
    cols = series_key_columns(info, row)
    parts = [str(row[c]).strip() for c in cols]
    return SERIES_ID_SEPARATOR.join(parts) if parts else info.name


def series_title_of(info: DatasetInfo, row: Mapping[str, Any]) -> str:
    cols = title_columns(info, row)
    return " / ".join(str(row[c]).strip() for c in cols)


def _attribute_value(name: str, value: Any) -> Any:
    if name == "LineNumber":
        try:
            return int(str(value).strip())
        except ValueError:
            return value
    return value


def group_rows(dataset: str, rows: Iterable[Mapping[str, Any]]) -> list[Series]:
    """Group raw ``Data`` rows into :class:`Series` (in first-seen order)."""
    info = dataset_info(dataset)
    by_id: dict[str, Series] = {}
    for row in rows:
        obs = Observation.from_row(row)
        if obs is None:
            continue
        sid = series_id_of(info, row)
        series = by_id.get(sid)
        if series is None:
            key_cols = series_key_columns(info, row)
            attrs: dict[str, Any] = {}
            for col in _attribute_columns(info, row, key_cols):
                name = "frequency_code" if col == FREQUENCY else snake_case(col)
                if name in RESERVED_COLUMNS:
                    name = f"api_{name}"
                attrs[name] = _attribute_value(col, row[col])
            series = Series(series_id=sid, title=series_title_of(info, row), attributes=attrs)
            by_id[sid] = series
        series.data.append(obs)
    return list(by_id.values())


RESERVED_COLUMNS = frozenset(
    {
        "dataset",
        "series_id",
        "series_title",
        "date",
        "year",
        "period",
        "frequency",
        "value",
        "unit",
        "unit_mult",
        "note_ref",
        "notes",
    }
)


@dataclass
class DataResponse:
    """Normalised result of one logical data request (possibly several HTTP calls)."""

    dataset: str
    series: list[Series] = field(default_factory=list)
    notes: list[Note] = field(default_factory=list)
    dimensions: list[dict[str, Any]] = field(default_factory=list)
    params: dict[str, str] = field(default_factory=dict)
    statistic: str | None = None
    production_time: str | None = None
    request_count: int = 0
    series_tables: dict[str, set[str]] = field(default_factory=dict)  # series id -> tables

    def get(self, series_id: str) -> Series | None:
        for s in self.series:
            if s.series_id == series_id:
                return s
        return None

    def note_text(self, refs: str) -> str:
        """Resolve a ``NoteRef`` value (comma separated refs) to the notes' text."""
        wanted = [r.strip() for r in refs.split(",") if r.strip()]
        by_ref = {n.ref: n.text for n in self.notes}
        return "; ".join(by_ref[r] for r in wanted if r in by_ref)

    def rows(self) -> list[dict[str, Any]]:
        return [o.raw for s in self.series for o in s.data]

    def to_api_dict(self) -> dict[str, Any]:
        """Re-serialise in the shape of a raw API response (used by ``--raw``).

        The ``UserID`` is deliberately not echoed back.
        """
        request = [
            {"ParameterName": k.upper(), "ParameterValue": v}
            for k, v in {"METHOD": "GETDATA", "DATASETNAME": self.dataset, **self.params}.items()
            if k.lower() != "userid"
        ]
        results: dict[str, Any] = {}
        if self.statistic is not None:
            results["Statistic"] = self.statistic
        if self.production_time is not None:
            results["UTCProductionTime"] = self.production_time
        results["Dimensions"] = list(self.dimensions)
        results["Data"] = self.rows()
        results["Notes"] = [{"NoteRef": n.ref, "NoteText": n.text} for n in self.notes]
        return {"BEAAPI": {"Request": {"RequestParam": request}, "Results": results}}
