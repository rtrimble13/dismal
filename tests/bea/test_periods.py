from __future__ import annotations

from datetime import date

import pytest

from dismal.bea.periods import (
    Frequency,
    PeriodError,
    YearMonth,
    parse_date_spec,
    parse_period,
    period_from_row,
    period_in_range,
    sort_key,
)


@pytest.mark.parametrize(
    ("code", "freq", "start", "end", "label"),
    [
        ("2024", Frequency.ANNUAL, 1, 12, "2024"),
        ("2024Q1", Frequency.QUARTERLY, 1, 3, "2024Q1"),
        ("2024Q4", Frequency.QUARTERLY, 10, 12, "2024Q4"),
        ("2024q2", Frequency.QUARTERLY, 4, 6, "2024Q2"),
        ("2024-Q3", Frequency.QUARTERLY, 7, 9, "2024Q3"),
        ("2024M01", Frequency.MONTHLY, 1, 1, "2024M01"),
        ("2024M12", Frequency.MONTHLY, 12, 12, "2024M12"),
        ("2024m7", Frequency.MONTHLY, 7, 7, "2024M07"),
        (2023, Frequency.ANNUAL, 1, 12, "2023"),
    ],
)
def test_parse_period(code: str | int, freq: Frequency, start: int, end: int, label: str) -> None:
    info = parse_period(code)
    assert info.frequency is freq
    assert (info.start_month, info.end_month) == (start, end)
    assert info.code == label and info.label == label


@pytest.mark.parametrize("code", ["2024Q5", "2024M13", "2024M00", "24", "abc", "", "2024X1"])
def test_parse_period_invalid(code: str) -> None:
    with pytest.raises(PeriodError):
        parse_period(code)


def test_period_dates_and_sort() -> None:
    q2 = parse_period("2024Q2")
    assert q2.start_date() == date(2024, 4, 1) and q2.end_date() == date(2024, 6, 30)
    assert parse_period("2024M02").end_date() == date(2024, 2, 29)
    assert parse_period("2023").end_date() == date(2023, 12, 31)
    keys = sorted(["2024", "2024Q1", "2023Q4", "2024M12", "2024Q4", "2023"], key=sort_key)
    assert keys == ["2023Q4", "2023", "2024Q1", "2024M12", "2024Q4", "2024"]


def test_frequency_codes() -> None:
    assert Frequency.from_code("A") is Frequency.ANNUAL and Frequency.ANNUAL.code == "A"
    assert Frequency.from_code("quarterly") is Frequency.QUARTERLY
    assert Frequency.from_code("QSA") is Frequency.QUARTERLY
    assert Frequency.from_code("m") is Frequency.MONTHLY
    assert Frequency.from_code("weird") is None and Frequency.from_code("") is None


def test_period_from_row() -> None:
    assert period_from_row({"TimePeriod": "2024Q3"}).code == "2024Q3"
    assert period_from_row({"Year": "2022", "Quarter": "2022"}).frequency is Frequency.ANNUAL
    assert period_from_row({"Year": "2022", "Quarter": "III"}).code == "2022Q3"
    assert period_from_row({"Year": "2022", "Quarter": "Q2"}).code == "2022Q2"
    assert period_from_row({"Year": "2022"}).code == "2022"
    assert period_from_row({"Year": "2022", "Quarter": "bogus"}).code == "2022"
    assert period_from_row({"TimePeriod": "nope"}) is None
    assert period_from_row({"Year": "x"}) is None and period_from_row({}) is None


@pytest.mark.parametrize(
    ("spec", "end", "expected"),
    [
        ("2020", False, YearMonth(2020, 1)),
        ("2020", True, YearMonth(2020, 12)),
        ("2020-03", False, YearMonth(2020, 3)),
        ("2020-3", False, YearMonth(2020, 3)),
        ("2020/11", False, YearMonth(2020, 11)),
        ("2020-03-15", False, YearMonth(2020, 3)),
        ("2020M03", False, YearMonth(2020, 3)),
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
    annual = parse_period("2020")
    q2 = parse_period("2020Q2")
    m5 = parse_period("2020M05")
    start, end = YearMonth(2020, 6), YearMonth(2020, 6)
    assert period_in_range(annual, start, end)  # overlaps June
    assert period_in_range(q2, start, None)  # Apr-Jun touches June
    assert not period_in_range(q2, YearMonth(2020, 7), None)
    assert not period_in_range(m5, start, None)
    assert period_in_range(m5, None, end)
    assert not period_in_range(parse_period("2021M05"), None, end)
    assert period_in_range(parse_period("1999M05"), None, None)
    assert str(YearMonth(2020, 3)) == "2020-03"
