from __future__ import annotations

from datetime import date

from dismal.bls.models import DataResponse, Observation, Series, Survey, parse_value


def test_observation_from_api_handles_empty_footnotes_and_missing_value() -> None:
    obs = Observation.from_api(
        {"year": "2024", "period": "M03", "periodName": "March", "value": "-", "footnotes": [{}]}
    )
    assert obs.value is None
    assert obs.raw_value == "-"
    assert obs.footnotes == []
    assert obs.latest is False
    assert obs.date == date(2024, 3, 1)
    assert obs.frequency.value == "monthly"


def test_observation_latest_and_footnotes() -> None:
    obs = Observation.from_api(
        {
            "year": "2024",
            "period": "M13",
            "periodName": "Annual",
            "latest": "true",
            "value": "1,234.5",
            "footnotes": [{"code": "P", "text": "Preliminary"}],
        }
    )
    assert obs.latest is True
    assert obs.value == 1234.5
    assert str(obs.footnotes[0]) == "P: Preliminary"
    assert obs.annual_average is True


def test_parse_value_variants() -> None:
    assert parse_value("3.7") == 3.7
    assert parse_value("") is None
    assert parse_value("(NA)") is None
    assert parse_value("abc") is None


def test_series_merge_dedupes_and_keeps_catalog() -> None:
    a = Series("X", [Observation(2020, "M01", "January", "1", 1.0)])
    b = Series(
        "X",
        [
            Observation(2020, "M01", "January", "1", 1.0),
            Observation(2020, "M02", "February", "2", 2.0),
        ],
        catalog={"series_title": "t"},
    )
    a.merge(b)
    assert [o.period for o in a.data] == ["M01", "M02"]
    assert a.title == "t"


def test_data_response_roundtrip_to_api_dict() -> None:
    resp = DataResponse(
        series=[Series("X", [Observation(2020, "M01", "January", "1.5", 1.5, latest=True)])],
        messages=["hi"],
        response_time_ms=7,
    )
    raw = resp.to_api_dict()
    assert raw["status"] == "REQUEST_SUCCEEDED"
    assert raw["Results"]["series"][0]["data"][0] == {
        "year": "2020",
        "period": "M01",
        "periodName": "January",
        "latest": "true",
        "value": "1.5",
        "footnotes": [{}],
    }
    assert resp.get("X") is not None and resp.get("Y") is None


def test_survey_from_api_uppercases() -> None:
    assert Survey.from_api({"survey_abbreviation": "cu", "survey_name": "CPI"}) == Survey(
        "CU", "CPI"
    )
