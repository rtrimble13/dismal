from __future__ import annotations

from datetime import date

import pytest

from dismal.fred.periods import (
    AGGREGATION_METHODS,
    FREQUENCY_CODES,
    UNITS,
    Frequency,
    PeriodError,
    normalise_aggregation,
    normalise_frequency,
    normalise_units,
    parse_date_spec,
    parse_iso_date,
)


def test_frequency_codes() -> None:
    assert Frequency.from_code("m") is Frequency.MONTHLY and Frequency.MONTHLY.code == "m"
    assert Frequency.from_code("Quarterly") is Frequency.QUARTERLY
    assert (
        Frequency.from_code("A") is Frequency.ANNUAL
        and Frequency.from_code("yearly") is Frequency.ANNUAL
    )
    assert (
        Frequency.from_code("BW") is Frequency.BIWEEKLY
        and Frequency.from_code("sa") is Frequency.SEMIANNUAL
    )
    assert Frequency.from_code("hourly") is None and Frequency.from_code("") is None
    assert normalise_frequency("monthly") == "m" and normalise_frequency("Q") == "q"
    assert normalise_frequency("wef") == "wef" and "wef" in FREQUENCY_CODES
    with pytest.raises(PeriodError):
        normalise_frequency("hourly")
    assert normalise_units("PC1") == "pc1" and set(UNITS) >= {"lin", "pch", "pc1", "log"}
    with pytest.raises(PeriodError):
        normalise_units("sqrt")
    assert normalise_aggregation("EOP") == "eop" and AGGREGATION_METHODS == ("avg", "sum", "eop")
    with pytest.raises(PeriodError):
        normalise_aggregation("median")


@pytest.mark.parametrize(
    ("spec", "start", "end"),
    [
        ("2020", date(2020, 1, 1), date(2020, 12, 31)),
        ("2020-03", date(2020, 3, 1), date(2020, 3, 31)),
        ("2020-3", date(2020, 3, 1), date(2020, 3, 31)),
        ("2024/02", date(2024, 2, 1), date(2024, 2, 29)),
        ("2020-03-15", date(2020, 3, 15), date(2020, 3, 15)),
        ("2020-Q2", date(2020, 4, 1), date(2020, 6, 30)),
        ("2020q4", date(2020, 10, 1), date(2020, 12, 31)),
        ("2020-H1", date(2020, 1, 1), date(2020, 6, 30)),
        ("2020-S2", date(2020, 7, 1), date(2020, 12, 31)),
    ],
)
def test_parse_date_spec(spec: str, start: date, end: date) -> None:
    parsed = parse_date_spec(spec)
    assert (parsed.start, parsed.end) == (start, end)


@pytest.mark.parametrize("spec", ["20", "2020-13", "2020-Q5", "abc", "2020-00", "2021-02-30"])
def test_parse_date_spec_invalid(spec: str) -> None:
    with pytest.raises(PeriodError):
        parse_date_spec(spec)


def test_parse_iso_date() -> None:
    assert parse_iso_date(" 2024-02-29 ") == date(2024, 2, 29)
    with pytest.raises(PeriodError):
        parse_iso_date("yesterday")
