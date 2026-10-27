"""BLS period codes, frequencies and date-range parsing.

The BLS API encodes the observation period of each data point as a short code:

================  ===================================  =========
Code              Meaning                              Frequency
================  ===================================  =========
``M01``-``M12``   Calendar month                       monthly
``M13``           Annual average of a monthly series   annual*
``Q01``-``Q04``   Calendar quarter                     quarterly
``Q05``           Annual average of a quarterly series annual*
``S01``-``S02``   Half year (Jan-Jun, Jul-Dec)         semiannual
``S03``           Annual average of a semiannual series annual*
``A01``           Calendar year                        annual
================  ===================================  =========

Rows marked ``*`` are flagged ``annual_average=True`` so callers can tell a true
annual series from an annual average that the API appends to a sub-annual one.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import date
from enum import Enum

from dismal.core.errors import PeriodError


class Frequency(str, Enum):
    """Observation frequency of a BLS period code."""

    MONTHLY = "monthly"
    QUARTERLY = "quarterly"
    SEMIANNUAL = "semiannual"
    ANNUAL = "annual"

    def __str__(self) -> str:  # pragma: no cover - trivial
        return self.value


@dataclass(frozen=True)
class PeriodInfo:
    """Decoded information about a BLS period code."""

    code: str
    frequency: Frequency
    start_month: int
    end_month: int
    annual_average: bool = False

    def start_date(self, year: int) -> date:
        return date(year, self.start_month, 1)

    def end_date(self, year: int) -> date:
        """Last day of the period."""
        if self.end_month == 12:
            return date(year, 12, 31)
        return date(year, self.end_month + 1, 1).replace(day=1) - _ONE_DAY


_ONE_DAY = date(2000, 1, 2) - date(2000, 1, 1)
_PERIOD_RE = re.compile(r"^(?P<kind>[MQSA])(?P<num>\d{2})$")


def parse_period(code: str) -> PeriodInfo:
    """Decode a BLS period code such as ``M03``, ``Q02`` or ``A01``."""
    match = _PERIOD_RE.match(code.strip().upper())
    if not match:
        raise PeriodError(f"unrecognised BLS period code: {code!r}")
    kind, num = match.group("kind"), int(match.group("num"))
    code = match.group(0)
    if kind == "M":
        if 1 <= num <= 12:
            return PeriodInfo(code, Frequency.MONTHLY, num, num)
        if num == 13:
            return PeriodInfo(code, Frequency.ANNUAL, 1, 12, annual_average=True)
    elif kind == "Q":
        if 1 <= num <= 4:
            start = (num - 1) * 3 + 1
            return PeriodInfo(code, Frequency.QUARTERLY, start, start + 2)
        if num == 5:
            return PeriodInfo(code, Frequency.ANNUAL, 1, 12, annual_average=True)
    elif kind == "S":
        if num in (1, 2):
            start = 1 if num == 1 else 7
            return PeriodInfo(code, Frequency.SEMIANNUAL, start, start + 5)
        if num == 3:
            return PeriodInfo(code, Frequency.ANNUAL, 1, 12, annual_average=True)
    elif kind == "A" and num == 1:
        return PeriodInfo(code, Frequency.ANNUAL, 1, 12)
    raise PeriodError(f"unrecognised BLS period code: {code!r}")


@dataclass(frozen=True, order=True)
class YearMonth:
    """A calendar month used as a bound of a date range."""

    year: int
    month: int

    def __str__(self) -> str:
        return f"{self.year:04d}-{self.month:02d}"


_DATE_SPEC_RE = re.compile(
    r"""^\s*(?P<year>\d{4})
        (?:[-/]?(?:
            (?P<month>1[0-2]|0?[1-9])(?:[-/]\d{1,2})?    # YYYY-MM or YYYY-MM-DD
          | [Qq](?P<quarter>[1-4])                       # YYYY-Q3
          | [HhSs](?P<half>[12])                         # YYYY-H2 / YYYY-S2
        ))?\s*$""",
    re.VERBOSE,
)


def parse_date_spec(spec: str, *, end: bool = False) -> YearMonth:
    """Parse a user-supplied date bound into a :class:`YearMonth`.

    Accepted forms: ``2020``, ``2020-03``, ``2020-03-15``, ``2020-Q2``,
    ``2020-H1`` / ``2020-S1``. When ``end`` is true, a coarse spec resolves to
    the *last* month it covers (``2020`` -> December 2020, ``2020-Q2`` -> June).
    """
    match = _DATE_SPEC_RE.match(spec)
    if not match:
        raise PeriodError(
            f"unrecognised date {spec!r}; use YYYY, YYYY-MM, YYYY-MM-DD, YYYY-Qn or YYYY-Hn"
        )
    year = int(match.group("year"))
    if match.group("month"):
        return YearMonth(year, int(match.group("month")))
    if match.group("quarter"):
        q = int(match.group("quarter"))
        return YearMonth(year, q * 3 if end else (q - 1) * 3 + 1)
    if match.group("half"):
        h = int(match.group("half"))
        return YearMonth(year, 12 if end else 7) if h == 2 else YearMonth(year, 6 if end else 1)
    return YearMonth(year, 12 if end else 1)


def period_in_range(
    year: int,
    info: PeriodInfo,
    start: YearMonth | None,
    end: YearMonth | None,
) -> bool:
    """Return True when the period *overlaps* the inclusive ``[start, end]`` range.

    A period counts as inside the range when any part of it does: ``--start
    2020-06`` keeps the 2020 annual value and Q2 2020, because both extend to or
    past June 2020.
    """
    p_start = YearMonth(year, info.start_month)
    p_end = YearMonth(year, info.end_month)
    if start is not None and p_end < start:
        return False
    return not (end is not None and p_start > end)


def sort_key(year: int, period: str) -> tuple[int, int, int]:
    """Chronological sort key; annual averages sort after the periods they summarise."""
    info = parse_period(period)
    return (year, 13 if info.annual_average else info.start_month, 0)
