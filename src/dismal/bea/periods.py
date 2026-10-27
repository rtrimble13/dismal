"""BEA time-period codes, frequencies and date-range parsing.

The BEA API encodes the period of each observation in ``TimePeriod``:

==========  =================  ==========
Code        Meaning            Frequency
==========  =================  ==========
``2024``    Calendar year      annual
``2024Q1``  Calendar quarter   quarterly
``2024M03`` Calendar month     monthly
==========  =================  ==========

A few datasets (GDPbyIndustry, InputOutput, MNE) carry ``Year`` and ``Quarter``
columns instead; :func:`period_from_row` normalises both shapes.
"""

from __future__ import annotations

import re
from collections.abc import Mapping
from dataclasses import dataclass
from datetime import date
from enum import Enum
from typing import Any

from dismal.core.errors import PeriodError


class Frequency(str, Enum):
    """Observation frequency of a BEA time period."""

    ANNUAL = "annual"
    QUARTERLY = "quarterly"
    MONTHLY = "monthly"

    def __str__(self) -> str:  # pragma: no cover - trivial
        return self.value

    @property
    def code(self) -> str:
        """The single-letter code the API uses in ``Frequency`` parameters."""
        return _FREQ_CODES[self]

    @classmethod
    def from_code(cls, code: str) -> Frequency | None:
        """Map ``A``/``Q``/``M`` (and words, ``QSA``/``QNSA``) to a frequency; None if unknown."""
        text = code.strip().lower()
        if not text:
            return None
        if text in {"a", "annual", "annually", "year", "yearly"}:
            return cls.ANNUAL
        if text in {"q", "quarterly", "quarter", "qsa", "qnsa"}:
            return cls.QUARTERLY
        if text in {"m", "monthly", "month"}:
            return cls.MONTHLY
        return None


_FREQ_CODES = {Frequency.ANNUAL: "A", Frequency.QUARTERLY: "Q", Frequency.MONTHLY: "M"}


@dataclass(frozen=True)
class PeriodInfo:
    """Decoded information about a BEA period code."""

    code: str
    year: int
    frequency: Frequency
    start_month: int
    end_month: int

    @property
    def span(self) -> int:
        return self.end_month - self.start_month + 1

    def start_date(self) -> date:
        return date(self.year, self.start_month, 1)

    def end_date(self) -> date:
        """Last day of the period."""
        if self.end_month == 12:
            return date(self.year, 12, 31)
        return date(self.year, self.end_month + 1, 1) - _ONE_DAY

    @property
    def sort_key(self) -> tuple[int, int, int]:
        """Chronological key; an annual value sorts after the quarters/months it covers."""
        return (self.year, self.end_month, self.span)

    @property
    def label(self) -> str:
        if self.frequency is Frequency.ANNUAL:
            return str(self.year)
        if self.frequency is Frequency.QUARTERLY:
            return f"{self.year}Q{(self.start_month - 1) // 3 + 1}"
        return f"{self.year}M{self.start_month:02d}"


_ONE_DAY = date(2000, 1, 2) - date(2000, 1, 1)
_PERIOD_RE = re.compile(
    r"""^\s*(?P<year>\d{4})
        (?:\s*[-/]?\s*(?:
            [Qq](?P<quarter>[1-4])
          | [Mm](?P<month>0?[1-9]|1[0-2])
        ))?\s*$""",
    re.VERBOSE,
)
_ROMAN_QUARTERS = {"I": 1, "II": 2, "III": 3, "IV": 4}


def parse_period(code: str | int) -> PeriodInfo:
    """Decode a BEA period code such as ``2024``, ``2024Q2`` or ``2024M03``."""
    text = str(code)
    match = _PERIOD_RE.match(text)
    if not match:
        raise PeriodError(f"unrecognised BEA time period: {text!r}")
    year = int(match.group("year"))
    if match.group("quarter"):
        q = int(match.group("quarter"))
        start = (q - 1) * 3 + 1
        return PeriodInfo(f"{year}Q{q}", year, Frequency.QUARTERLY, start, start + 2)
    if match.group("month"):
        m = int(match.group("month"))
        return PeriodInfo(f"{year}M{m:02d}", year, Frequency.MONTHLY, m, m)
    return PeriodInfo(str(year), year, Frequency.ANNUAL, 1, 12)


def period_from_row(row: Mapping[str, Any]) -> PeriodInfo | None:
    """Derive the period of an API data row from ``TimePeriod`` or ``Year``/``Quarter``.

    Returns ``None`` when the row carries no recognisable time information.
    """
    time_period = row.get("TimePeriod")
    if time_period not in (None, ""):
        try:
            return parse_period(str(time_period))
        except PeriodError:
            return None
    year = row.get("Year")
    if year in (None, ""):
        return None
    try:
        y = int(str(year).strip())
    except ValueError:
        return None
    quarter = str(row.get("Quarter") or "").strip().upper()
    if quarter in _ROMAN_QUARTERS:
        return parse_period(f"{y}Q{_ROMAN_QUARTERS[quarter]}")
    if quarter and quarter != str(y):
        try:
            return parse_period(f"{y}{quarter}" if quarter[0] in "QM" else f"{y}Q{quarter}")
        except PeriodError:
            return PeriodInfo(str(y), y, Frequency.ANNUAL, 1, 12)
    return PeriodInfo(str(y), y, Frequency.ANNUAL, 1, 12)


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
            [Mm]?(?P<month>1[0-2]|0?[1-9])(?:[-/]\d{1,2})?  # YYYY-MM, YYYY-MM-DD, YYYYM03
          | [Qq](?P<quarter>[1-4])                          # YYYY-Q3 / 2024Q3
          | [HhSs](?P<half>[12])                            # YYYY-H2
        ))?\s*$""",
    re.VERBOSE,
)


def parse_date_spec(spec: str, *, end: bool = False) -> YearMonth:
    """Parse a user-supplied date bound into a :class:`YearMonth`.

    Accepted forms: ``2020``, ``2020-03``, ``2020-03-15``, ``2020-Q2``,
    ``2020Q2``, ``2020M03``, ``2020-H1``. When ``end`` is true, a coarse spec
    resolves to the *last* month it covers (``2020`` -> December 2020,
    ``2020-Q2`` -> June).
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
    info: PeriodInfo,
    start: YearMonth | None,
    end: YearMonth | None,
) -> bool:
    """Return True when the period *overlaps* the inclusive ``[start, end]`` range.

    A period counts as inside the range when any part of it does: ``--start
    2020-06`` keeps the 2020 annual value and Q2 2020, because both extend to or
    past June 2020.
    """
    p_start = YearMonth(info.year, info.start_month)
    p_end = YearMonth(info.year, info.end_month)
    if start is not None and p_end < start:
        return False
    return not (end is not None and p_start > end)


def sort_key(period: str) -> tuple[int, int, int]:
    """Chronological sort key for a period code (annual values after their quarters)."""
    return parse_period(period).sort_key
