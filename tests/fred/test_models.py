from __future__ import annotations

from datetime import date

from dismal.fred.models import (
    Category,
    DataResponse,
    Observation,
    Release,
    ReleaseDate,
    Series,
    SeriesInfo,
    Source,
    parse_date,
    parse_value,
)


def test_parse_value_and_date() -> None:
    assert (
        parse_value("3.7") == 3.7 and parse_value("1,234.5") == 1234.5 and parse_value(12) == 12.0
    )
    for raw in (".", "", "-", "NA", None, "abc"):
        assert parse_value(raw) is None, raw
    assert parse_date("2024-03-01") == date(2024, 3, 1) and parse_date("2024-03-01 12:00") == date(
        2024, 3, 1
    )
    assert parse_date("") is None and parse_date("bogus") is None


def test_observation_from_api() -> None:
    obs = Observation.from_api(
        {
            "realtime_start": "2024-01-01",
            "realtime_end": "9999-12-31",
            "date": "2023-12-01",
            "value": ".",
        }
    )
    assert (
        obs is not None
        and obs.value is None
        and obs.raw_value == "."
        and obs.realtime_end == date(9999, 12, 31)
    )
    assert obs.to_api_dict() == {
        "realtime_start": "2024-01-01",
        "realtime_end": "9999-12-31",
        "date": "2023-12-01",
        "value": ".",
    }
    assert Observation.from_api({"value": "1"}) is None
    bare = Observation.from_api({"date": "2020-01-01", "value": "2.5"})
    assert bare is not None and bare.to_api_dict() == {"date": "2020-01-01", "value": "2.5"}


def test_series_info() -> None:
    info = SeriesInfo.from_api(
        {
            "id": "unrate",
            "title": "Unemployment Rate",
            "observation_start": "1948-01-01",
            "frequency": "Monthly",
            "frequency_short": "M",
            "units": "Percent",
            "seasonal_adjustment": "Seasonally Adjusted",
            "seasonal_adjustment_short": "SA",
            "popularity": "95",
            "notes": "n",
        }
    )
    assert (
        info.id == "UNRATE" and info.observation_start == date(1948, 1, 1) and info.popularity == 95
    )
    rec = info.to_record()
    assert rec["seasonal_adjustment"] == "SA" and "notes" not in rec
    assert info.to_record(include_notes=True)["notes"] == "n"
    assert SeriesInfo.from_api({"id": "X", "popularity": "x"}).popularity is None


def test_series_merge_sort_latest() -> None:
    a = Series(
        "X", [Observation(date(2020, 2, 1), "2", 2.0), Observation(date(2020, 1, 1), "1", 1.0)]
    )
    b = Series(
        "X",
        [Observation(date(2020, 2, 1), "2", 2.0), Observation(date(2020, 3, 1), "3", 3.0)],
        info=SeriesInfo("X", "t"),
    )
    a.merge(b)
    a.sort()
    assert [o.date for o in a.data] == [date(2020, 1, 1), date(2020, 2, 1), date(2020, 3, 1)]
    assert a.title == "t" and a.latest is not None and a.latest.value == 3.0
    assert Series("E").latest is None and Series("E").title is None


def test_data_response_roundtrip() -> None:
    resp = DataResponse(
        series=[Series("X", [Observation(date(2020, 1, 1), "1.5", 1.5)])],
        messages=["hi"],
        params={"units": "pch"},
    )
    raw = resp.to_api_dict()
    assert raw["params"] == {"units": "pch"} and raw["messages"] == ["hi"]
    assert raw["series"] == [
        {"series_id": "X", "count": 1, "observations": [{"date": "2020-01-01", "value": "1.5"}]}
    ]
    assert resp.get("X") is not None and resp.get("Y") is None


def test_other_models() -> None:
    rel = Release.from_api(
        {"id": "53", "name": "GDP", "press_release": True, "link": "l", "notes": "n"}
    )
    assert (
        rel.to_record() == {"id": 53, "name": "GDP", "press_release": True, "link": "l"}
        and rel.notes == "n"
    )
    rd = ReleaseDate.from_api({"release_id": 53, "release_name": "GDP", "date": "2026-10-30"})
    assert rd is not None and rd.to_record()["date"] == date(2026, 10, 30)
    assert ReleaseDate.from_api({"release_id": 1}) is None
    cat = Category.from_api({"id": 12, "name": "CPS", "parent_id": 10})
    assert cat.to_record() == {"id": 12, "name": "CPS", "parent_id": 10}
    assert Category.from_api({"id": 0, "name": "root", "parent_id": None}).parent_id is None
    assert Source.from_api({"id": 1, "name": "Fed", "link": "x"}).to_record()["link"] == "x"
