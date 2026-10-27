from __future__ import annotations

from datetime import date

import pytest

from dismal.bls.periods import (
    Frequency,
    PeriodError,
    YearMonth,
    parse_date_spec,
    parse_period,
    period_in_range,
    sort_key,
)


@pytest.mark.parametrize(
    ("code", "freq", "start", "end", "avg"),
    [
        ("M01", Frequency.MONTHLY, 1, 1, False),
        ("M12", Frequency.MONTHLY, 12, 12, False),
        ("M13", Frequency.ANNUAL, 1, 12, True),
        ("Q01", Frequency.QUARTERLY, 1, 3, False),
        ("Q04", Frequency.QUARTERLY, 10, 12, False),
        ("Q05", Frequency.ANNUAL, 1, 12, True),
        ("S01", Frequency.SEMIANNUAL, 1, 6, False),
        ("S02", Frequency.SEMIANNUAL, 7, 12, False),
        ("S03", Frequency.ANNUAL, 1, 12, True),
        ("A01", Frequency.ANNUAL, 1, 12, False),
        ("m03", Frequency.MONTHLY, 3, 3, False),
    ],
)
def test_parse_period(code: str, freq: Frequency, start: int, end: int, avg: bool) -> None:
    info = parse_period(code)
    assert info.frequency is freq
    assert (info.start_month, info.end_month, info.annual_average) == (start, end, avg)


@pytest.mark.parametrize("code", ["M00", "M14", "Q06", "S04", "A02", "X01", "", "M1"])
def test_parse_period_invalid(code: str) -> None:
    with pytest.raises(PeriodError):
        parse_period(code)


def test_period_dates() -> None:
    q2 = parse_period("Q02")
    assert q2.start_date(2024) == date(2024, 4, 1)
    assert q2.end_date(2024) == date(2024, 6, 30)
    assert parse_period("M02").end_date(2024) == date(2024, 2, 29)
    assert parse_period("A01").end_date(2023) == date(2023, 12, 31)


@pytest.mark.parametrize(
    ("spec", "end", "expected"),
    [
        ("2020", False, YearMonth(2020, 1)),
        ("2020", True, YearMonth(2020, 12)),
        ("2020-03", False, YearMonth(2020, 3)),
        ("2020-3", False, YearMonth(2020, 3)),
        ("2020/11", False, YearMonth(2020, 11)),
        ("2020-03-15", False, YearMonth(2020, 3)),
        ("2020-Q2", False, YearMonth(2020, 4)),
        ("2020-Q2", True, YearMonth(2020, 6)),
        ("2020q4", True, YearMonth(2020, 12)),
        ("2020-H1", True, YearMonth(2020, 6)),
        ("2020-S2", False, YearMonth(2020, 7)),
    ],
)
def test_parse_date_spec(spec: str, end: bool, expected: YearMonth) -> None:
    assert parse_date_spec(spec, end=end) == expected


@pytest.mark.parametrize("spec", ["20", "2020-13", "2020-Q5", "abc", "2020-00"])
def test_parse_date_spec_invalid(spec: str) -> None:
    with pytest.raises(PeriodError):
        parse_date_spec(spec)


def test_period_in_range_overlap_semantics() -> None:
    annual = parse_period("A01")
    q2 = parse_period("Q02")
    m5 = parse_period("M05")
    start, end = YearMonth(2020, 6), YearMonth(2020, 6)
    assert period_in_range(2020, annual, start, end)  # overlaps June
    assert period_in_range(2020, q2, start, None)  # Apr-Jun touches June
    assert not period_in_range(2020, q2, YearMonth(2020, 7), None)
    assert not period_in_range(2020, m5, start, None)
    assert period_in_range(2020, m5, None, end)
    assert not period_in_range(2021, m5, None, end)
    assert period_in_range(1999, m5, None, None)


def test_sort_key_places_annual_average_last() -> None:
    keys = sorted(
        [(2020, "M13"), (2020, "M01"), (2020, "M12"), (2019, "M12")], key=lambda t: sort_key(*t)
    )
    assert keys == [(2019, "M12"), (2020, "M01"), (2020, "M12"), (2020, "M13")]
