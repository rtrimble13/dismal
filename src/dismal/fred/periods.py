"""Dates, frequencies and the API's transformation codes.

FRED observations are dated with the *first day* of their period (``2024-04-01``
for 2024Q2, ``2024-01-01`` for 2024). The API filters by ISO dates, aggregates
to lower frequencies (``frequency``/``aggregation_method``) and transforms
values (``units``); this module holds the vocabulary for those parameters and
parses the user-friendly date specs the CLI accepts.
"""

from __future__ import annotations

import calendar
import re
from dataclasses import dataclass
from datetime import date
from enum import Enum

from dismal.core.errors import PeriodError


class Frequency(str, Enum):
    """Observation frequency words, mapped to the API's one- or two-letter codes."""

    DAILY = "daily"
    WEEKLY = "weekly"
    BIWEEKLY = "biweekly"
    MONTHLY = "monthly"
    QUARTERLY = "quarterly"
    SEMIANNUAL = "semiannual"
    ANNUAL = "annual"

    def __str__(self) -> str:  # pragma: no cover - trivial
        return self.value

    @property
    def code(self) -> str:
        return _FREQ_CODES[self]

    @classmethod
    def from_code(cls, code: str) -> Frequency | None:
        """Map ``d``/``w``/``m``/``q``/``a``, words or FRED's ``frequency_short`` to a value."""
        text = code.strip().lower()
        return _FREQ_LOOKUP.get(text)


_FREQ_CODES = {
    Frequency.DAILY: "d",
    Frequency.WEEKLY: "w",
    Frequency.BIWEEKLY: "bw",
    Frequency.MONTHLY: "m",
    Frequency.QUARTERLY: "q",
    Frequency.SEMIANNUAL: "sa",
    Frequency.ANNUAL: "a",
}
_FREQ_LOOKUP: dict[str, Frequency] = {}
for _f, _c in _FREQ_CODES.items():
    _FREQ_LOOKUP[_c] = _f
    _FREQ_LOOKUP[_f.value] = _f
_FREQ_LOOKUP.update(
    {
        "day": Frequency.DAILY,
        "week": Frequency.WEEKLY,
        "month": Frequency.MONTHLY,
        "quarter": Frequency.QUARTERLY,
        "year": Frequency.ANNUAL,
        "yearly": Frequency.ANNUAL,
        "annually": Frequency.ANNUAL,
        "semiannually": Frequency.SEMIANNUAL,
        "biweekly": Frequency.BIWEEKLY,
    }
)

# Every frequency value the API accepts (week-ending and biweek variants included).
FREQUENCY_CODES: tuple[str, ...] = (
    "d",
    "w",
    "bw",
    "m",
    "q",
    "sa",
    "a",
    "wef",
    "weth",
    "wew",
    "wetu",
    "wem",
    "wesu",
    "wesa",
    "bwew",
    "bwem",
)
AGGREGATION_METHODS: tuple[str, ...] = ("avg", "sum", "eop")
UNITS: dict[str, str] = {
    "lin": "levels (no transformation)",
    "chg": "change from the previous observation",
    "ch1": "change from a year ago",
    "pch": "percent change from the previous observation",
    "pc1": "percent change from a year ago",
    "pca": "compounded annual rate of change",
    "cch": "continuously compounded rate of change",
    "cca": "continuously compounded annual rate of change",
    "log": "natural log",
}


def normalise_frequency(text: str) -> str:
    """Return the API code for a frequency word or code; raise :class:`PeriodError` if unknown."""
    code = text.strip().lower()
    freq = Frequency.from_code(code)
    if freq is not None:
        return freq.code
    if code in FREQUENCY_CODES:
        return code
    raise PeriodError(
        f"unknown frequency {text!r}; use d, w, bw, m, q, sa, a (or daily, weekly, ..., annual)"
    )


def normalise_units(text: str) -> str:
    code = text.strip().lower()
    if code in UNITS:
        return code
    raise PeriodError(f"unknown units {text!r}; use one of {', '.join(UNITS)}")


def normalise_aggregation(text: str) -> str:
    code = text.strip().lower()
    if code in AGGREGATION_METHODS:
        return code
    raise PeriodError(f"unknown aggregation {text!r}; use avg, sum or eop")


_DATE_SPEC_RE = re.compile(
    r"""^\s*(?P<year>\d{4})
        (?:[-/]?(?:
            (?P<month>1[0-2]|0?[1-9])(?:[-/](?P<day>\d{1,2}))?   # YYYY-MM or YYYY-MM-DD
          | [Qq](?P<quarter>[1-4])                              # YYYY-Q3
          | [HhSs](?P<half>[12])                                # YYYY-H2
        ))?\s*$""",
    re.VERBOSE,
)


@dataclass(frozen=True)
class DateSpec:
    """A parsed date bound: the first (or, for ``end``, last) day it covers."""

    start: date
    end: date


def parse_date_spec(spec: str) -> DateSpec:
    """Parse ``2020``, ``2020-03``, ``2020-03-15``, ``2020-Q2`` or ``2020-H1`` into a date span."""
    match = _DATE_SPEC_RE.match(spec)
    if not match:
        raise PeriodError(
            f"unrecognised date {spec!r}; use YYYY, YYYY-MM, YYYY-MM-DD, YYYY-Qn or YYYY-Hn"
        )
    year = int(match.group("year"))
    if match.group("month"):
        month = int(match.group("month"))
        if match.group("day"):
            day = int(match.group("day"))
            try:
                d = date(year, month, day)
            except ValueError as exc:
                raise PeriodError(f"invalid date {spec!r}") from exc
            return DateSpec(d, d)
        return DateSpec(date(year, month, 1), _month_end(year, month))
    if match.group("quarter"):
        q = int(match.group("quarter"))
        first = (q - 1) * 3 + 1
        return DateSpec(date(year, first, 1), _month_end(year, first + 2))
    if match.group("half"):
        h = int(match.group("half"))
        first = 1 if h == 1 else 7
        return DateSpec(date(year, first, 1), _month_end(year, first + 5))
    return DateSpec(date(year, 1, 1), date(year, 12, 31))


def _month_end(year: int, month: int) -> date:
    return date(year, month, calendar.monthrange(year, month)[1])


def parse_iso_date(text: str) -> date:
    """Parse ``YYYY-MM-DD`` strictly (the shape the API uses everywhere)."""
    try:
        return date.fromisoformat(text.strip())
    except ValueError as exc:
        raise PeriodError(f"unrecognised date {text!r}; use YYYY-MM-DD") from exc
