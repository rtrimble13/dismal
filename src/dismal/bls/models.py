"""Typed representations of BLS API responses."""

from __future__ import annotations

import datetime as _dt
from dataclasses import dataclass, field
from typing import Any

from dismal.bls.periods import Frequency, PeriodInfo, parse_period


@dataclass(frozen=True)
class Footnote:
    code: str
    text: str

    def __str__(self) -> str:
        return f"{self.code}: {self.text}" if self.code else self.text


@dataclass
class Observation:
    """One data point of a series."""

    year: int
    period: str
    period_name: str
    raw_value: str
    value: float | None
    footnotes: list[Footnote] = field(default_factory=list)
    latest: bool = False
    calculations: dict[str, dict[str, str]] | None = None
    aspects: list[dict[str, Any]] | None = None

    @property
    def period_info(self) -> PeriodInfo:
        return parse_period(self.period)

    @property
    def frequency(self) -> Frequency:
        return self.period_info.frequency

    @property
    def annual_average(self) -> bool:
        return self.period_info.annual_average

    @property
    def date(self) -> _dt.date:
        """First day of the observation period."""
        return self.period_info.start_date(self.year)

    @property
    def end_date(self) -> _dt.date:
        return self.period_info.end_date(self.year)

    @classmethod
    def from_api(cls, raw: dict[str, Any]) -> Observation:
        footnotes = [
            Footnote(code=str(fn.get("code", "") or ""), text=str(fn.get("text", "") or ""))
            for fn in raw.get("footnotes") or []
            if isinstance(fn, dict) and (fn.get("code") or fn.get("text"))
        ]
        raw_value = str(raw.get("value", ""))
        return cls(
            year=int(raw["year"]),
            period=str(raw["period"]),
            period_name=str(raw.get("periodName", "")),
            raw_value=raw_value,
            value=parse_value(raw_value),
            footnotes=footnotes,
            latest=str(raw.get("latest", "")).lower() == "true",
            calculations=raw.get("calculations") or None,
            aspects=raw.get("aspects") or None,
        )


def parse_value(raw: str) -> float | None:
    """Convert the API's string value to a float; ``-`` and blanks become ``None``."""
    text = raw.strip().replace(",", "")
    if text in {"", "-", "\u2013", "(NA)", "NA", "N/A"}:
        return None
    try:
        return float(text)
    except ValueError:
        return None


@dataclass
class Series:
    """A BLS time series with optional catalog metadata."""

    series_id: str
    data: list[Observation] = field(default_factory=list)
    catalog: dict[str, Any] | None = None

    @property
    def title(self) -> str | None:
        if self.catalog:
            title = self.catalog.get("series_title")
            return str(title) if title else None
        return None

    @classmethod
    def from_api(cls, raw: dict[str, Any]) -> Series:
        return cls(
            series_id=str(raw["seriesID"]),
            data=[Observation.from_api(d) for d in raw.get("data") or []],
            catalog=raw.get("catalog") or None,
        )

    def merge(self, other: Series) -> None:
        """Merge observations from ``other`` (same series) without duplicates."""
        seen = {(o.year, o.period) for o in self.data}
        for obs in other.data:
            key = (obs.year, obs.period)
            if key not in seen:
                self.data.append(obs)
                seen.add(key)
        if other.catalog and not self.catalog:
            self.catalog = other.catalog


@dataclass
class DataResponse:
    """Normalised result of one logical data request (possibly many HTTP calls)."""

    series: list[Series] = field(default_factory=list)
    messages: list[str] = field(default_factory=list)
    request_count: int = 0
    response_time_ms: int = 0

    def get(self, series_id: str) -> Series | None:
        for s in self.series:
            if s.series_id == series_id:
                return s
        return None

    def to_api_dict(self) -> dict[str, Any]:
        """Re-serialise in the shape of a raw API response (used by ``--raw``)."""
        return {
            "status": "REQUEST_SUCCEEDED",
            "responseTime": self.response_time_ms,
            "message": list(self.messages),
            "Results": {
                "series": [
                    {
                        "seriesID": s.series_id,
                        **({"catalog": s.catalog} if s.catalog else {}),
                        "data": [
                            {
                                "year": str(o.year),
                                "period": o.period,
                                "periodName": o.period_name,
                                **({"latest": "true"} if o.latest else {}),
                                "value": o.raw_value,
                                "footnotes": [
                                    {"code": fn.code, "text": fn.text} for fn in o.footnotes
                                ]
                                or [{}],
                                **({"calculations": o.calculations} if o.calculations else {}),
                                **({"aspects": o.aspects} if o.aspects else {}),
                            }
                            for o in s.data
                        ],
                    }
                    for s in self.series
                ]
            },
        }


@dataclass(frozen=True)
class Survey:
    abbreviation: str
    name: str

    @classmethod
    def from_api(cls, raw: dict[str, Any]) -> Survey:
        return cls(
            abbreviation=str(raw.get("survey_abbreviation", "")).upper(),
            name=str(raw.get("survey_name", "")),
        )
