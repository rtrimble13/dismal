"""Typed representations of FRED API responses."""

from __future__ import annotations

import datetime as _dt
from collections.abc import Mapping
from dataclasses import dataclass, field
from typing import Any


def parse_value(raw: Any) -> float | None:
    """Convert the API's string value to a float; ``.`` (missing) and blanks become ``None``."""
    if raw is None:
        return None
    if isinstance(raw, (int, float)) and not isinstance(raw, bool):
        return float(raw)
    text = str(raw).strip().replace(",", "")
    if text in {"", ".", "-", "NA", "N/A", "n/a"}:
        return None
    try:
        return float(text)
    except ValueError:
        return None


def parse_date(raw: Any) -> _dt.date | None:
    if raw in (None, ""):
        return None
    try:
        return _dt.date.fromisoformat(str(raw)[:10])
    except ValueError:
        return None


def _int(raw: Any) -> int | None:
    if raw in (None, ""):
        return None
    try:
        return int(raw)
    except (TypeError, ValueError):
        return None


@dataclass
class Observation:
    """One data point of a series."""

    date: _dt.date
    raw_value: str
    value: float | None
    realtime_start: _dt.date | None = None
    realtime_end: _dt.date | None = None

    @classmethod
    def from_api(cls, raw: Mapping[str, Any]) -> Observation | None:
        d = parse_date(raw.get("date"))
        if d is None:
            return None
        raw_value = "" if raw.get("value") is None else str(raw.get("value"))
        return cls(
            date=d,
            raw_value=raw_value,
            value=parse_value(raw_value),
            realtime_start=parse_date(raw.get("realtime_start")),
            realtime_end=parse_date(raw.get("realtime_end")),
        )

    def to_api_dict(self) -> dict[str, Any]:
        out: dict[str, Any] = {}
        if self.realtime_start:
            out["realtime_start"] = self.realtime_start.isoformat()
        if self.realtime_end:
            out["realtime_end"] = self.realtime_end.isoformat()
        out["date"] = self.date.isoformat()
        out["value"] = self.raw_value
        return out


@dataclass(frozen=True)
class SeriesInfo:
    """Metadata of a series (the ``series`` endpoint and search results)."""

    id: str
    title: str = ""
    observation_start: _dt.date | None = None
    observation_end: _dt.date | None = None
    frequency: str = ""
    frequency_short: str = ""
    units: str = ""
    units_short: str = ""
    seasonal_adjustment: str = ""
    seasonal_adjustment_short: str = ""
    last_updated: str = ""
    popularity: int | None = None
    group_popularity: int | None = None
    notes: str = ""
    realtime_start: _dt.date | None = None
    realtime_end: _dt.date | None = None

    @classmethod
    def from_api(cls, raw: Mapping[str, Any]) -> SeriesInfo:
        return cls(
            id=str(raw.get("id", "")).strip().upper(),
            title=str(raw.get("title", "") or ""),
            observation_start=parse_date(raw.get("observation_start")),
            observation_end=parse_date(raw.get("observation_end")),
            frequency=str(raw.get("frequency", "") or ""),
            frequency_short=str(raw.get("frequency_short", "") or ""),
            units=str(raw.get("units", "") or ""),
            units_short=str(raw.get("units_short", "") or ""),
            seasonal_adjustment=str(raw.get("seasonal_adjustment", "") or ""),
            seasonal_adjustment_short=str(raw.get("seasonal_adjustment_short", "") or ""),
            last_updated=str(raw.get("last_updated", "") or ""),
            popularity=_int(raw.get("popularity")),
            group_popularity=_int(raw.get("group_popularity")),
            notes=str(raw.get("notes", "") or ""),
            realtime_start=parse_date(raw.get("realtime_start")),
            realtime_end=parse_date(raw.get("realtime_end")),
        )

    def to_record(self, *, include_notes: bool = False) -> dict[str, Any]:
        rec: dict[str, Any] = {
            "id": self.id,
            "title": self.title,
            "frequency": self.frequency,
            "units": self.units,
            "seasonal_adjustment": self.seasonal_adjustment_short or self.seasonal_adjustment,
            "observation_start": self.observation_start,
            "observation_end": self.observation_end,
            "last_updated": self.last_updated,
            "popularity": self.popularity,
        }
        if include_notes:
            rec["notes"] = self.notes
        return rec


@dataclass
class Series:
    """A FRED time series with optional metadata."""

    series_id: str
    data: list[Observation] = field(default_factory=list)
    info: SeriesInfo | None = None

    @property
    def title(self) -> str | None:
        return self.info.title if self.info and self.info.title else None

    def merge(self, other: Series) -> None:
        """Merge observations from ``other`` (same series) without duplicates."""
        seen = {(o.date, o.realtime_start) for o in self.data}
        for obs in other.data:
            key = (obs.date, obs.realtime_start)
            if key not in seen:
                self.data.append(obs)
                seen.add(key)
        if other.info and not self.info:
            self.info = other.info

    def sort(self) -> None:
        self.data.sort(key=lambda o: (o.date, o.realtime_start or _dt.date.min))

    @property
    def latest(self) -> Observation | None:
        return self.data[-1] if self.data else None


@dataclass
class DataResponse:
    """Normalised result of one logical data request (one HTTP call per series)."""

    series: list[Series] = field(default_factory=list)
    messages: list[str] = field(default_factory=list)
    request_count: int = 0
    params: dict[str, str] = field(default_factory=dict)

    def get(self, series_id: str) -> Series | None:
        for s in self.series:
            if s.series_id == series_id:
                return s
        return None

    def to_api_dict(self) -> dict[str, Any]:
        """Re-serialise close to the API's shape (used by ``--raw``); the key is never included."""
        return {
            "params": dict(self.params),
            "messages": list(self.messages),
            "series": [
                {
                    "series_id": s.series_id,
                    **({"info": s.info.to_record(include_notes=True)} if s.info else {}),
                    "count": len(s.data),
                    "observations": [o.to_api_dict() for o in s.data],
                }
                for s in self.series
            ],
        }


@dataclass(frozen=True)
class Release:
    id: int
    name: str
    press_release: bool = False
    link: str = ""
    notes: str = ""

    @classmethod
    def from_api(cls, raw: Mapping[str, Any]) -> Release:
        return cls(
            id=_int(raw.get("id")) or 0,
            name=str(raw.get("name", "") or ""),
            press_release=bool(raw.get("press_release", False)),
            link=str(raw.get("link", "") or ""),
            notes=str(raw.get("notes", "") or ""),
        )

    def to_record(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "name": self.name,
            "press_release": self.press_release,
            "link": self.link,
        }


@dataclass(frozen=True)
class ReleaseDate:
    release_id: int
    release_name: str
    date: _dt.date

    @classmethod
    def from_api(cls, raw: Mapping[str, Any]) -> ReleaseDate | None:
        d = parse_date(raw.get("date"))
        if d is None:
            return None
        return cls(
            release_id=_int(raw.get("release_id")) or 0,
            release_name=str(raw.get("release_name", "") or ""),
            date=d,
        )

    def to_record(self) -> dict[str, Any]:
        return {"date": self.date, "release_id": self.release_id, "release_name": self.release_name}


@dataclass(frozen=True)
class Category:
    id: int
    name: str
    parent_id: int | None = None

    @classmethod
    def from_api(cls, raw: Mapping[str, Any]) -> Category:
        return cls(
            id=_int(raw.get("id")) or 0,
            name=str(raw.get("name", "") or ""),
            parent_id=_int(raw.get("parent_id")),
        )

    def to_record(self) -> dict[str, Any]:
        return {"id": self.id, "name": self.name, "parent_id": self.parent_id}


@dataclass(frozen=True)
class Source:
    id: int
    name: str
    link: str = ""

    @classmethod
    def from_api(cls, raw: Mapping[str, Any]) -> Source:
        return cls(
            id=_int(raw.get("id")) or 0,
            name=str(raw.get("name", "") or ""),
            link=str(raw.get("link", "") or ""),
        )

    def to_record(self) -> dict[str, Any]:
        return {"id": self.id, "name": self.name, "link": self.link}
