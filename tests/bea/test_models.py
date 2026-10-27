from __future__ import annotations

from datetime import date

from dismal.bea.datasets import DatasetInfo, canonical_name, dataset_info
from dismal.bea.models import (
    DataResponse,
    Dataset,
    Note,
    Observation,
    Parameter,
    Series,
    group_rows,
    parse_unit_mult,
    parse_value,
    snake_case,
)


def test_parse_value_variants() -> None:
    assert parse_value("3.7") == 3.7
    assert parse_value("27,720,709") == 27720709.0
    assert parse_value("-1,234.5") == -1234.5
    assert parse_value(12) == 12.0
    for raw in ("", "-", "---", "(D)", "(NA)", "(*)", "n.a.", "N/A", None, "abc"):
        assert parse_value(raw) is None, raw
    assert (
        parse_unit_mult("6") == 6 and parse_unit_mult("") is None and parse_unit_mult("x") is None
    )


def test_snake_case() -> None:
    assert snake_case("TableName") == "table_name"
    assert snake_case("TableID") == "table_id"
    assert snake_case("METRIC_NAME") == "metric_name"
    assert snake_case("GeoFips") == "geo_fips"
    assert snake_case("IndustrYDescription") == "industry_description"
    assert snake_case("TimeSeriesId") == "time_series_id"
    assert snake_case("DataValueUnformatted") == "data_value_unformatted"
    assert snake_case("Code") == "code"


def test_observation_from_row() -> None:
    obs = Observation.from_row(
        {
            "TimePeriod": "2024Q2",
            "DataValue": "1,234.5",
            "CL_UNIT": "Level",
            "UNIT_MULT": "6",
            "NoteRef": "T1",
        }
    )
    assert obs is not None
    assert obs.value == 1234.5 and obs.raw_value == "1,234.5" and obs.unit == "Level"
    assert obs.unit_mult == 6 and obs.note_ref == "T1"
    assert obs.date == date(2024, 4, 1) and obs.end_date == date(2024, 6, 30)
    assert obs.frequency.value == "quarterly" and obs.year == 2024
    assert Observation.from_row({"DataValue": "1"}) is None
    mne = Observation.from_row(
        {"Year": "2022", "DataValue": "(D)", "DataValueUnformatted": "12345"}
    )
    assert mne is not None and mne.value == 12345.0 and mne.raw_value == "(D)"


def test_group_rows_by_dataset() -> None:
    nipa = group_rows(
        "NIPA",
        [
            {
                "TableName": "T1",
                "SeriesCode": "A",
                "LineNumber": "1",
                "LineDescription": "GDP",
                "TimePeriod": "2024Q2",
                "DataValue": "2",
                "CL_UNIT": "L",
                "UNIT_MULT": "6",
                "NoteRef": "T1",
            },
            {
                "TableName": "T1",
                "SeriesCode": "A",
                "LineNumber": "1",
                "LineDescription": "GDP",
                "TimePeriod": "2024Q1",
                "DataValue": "1",
                "CL_UNIT": "L",
                "UNIT_MULT": "6",
                "NoteRef": "T1",
            },
            {
                "TableName": "T1",
                "SeriesCode": "B",
                "LineNumber": "2",
                "LineDescription": "PCE",
                "TimePeriod": "2024Q1",
                "DataValue": "3",
                "CL_UNIT": "L",
                "UNIT_MULT": "6",
                "NoteRef": "T1",
            },
            {"TableName": "T1", "SeriesCode": "C", "LineNumber": "3"},  # no period: skipped
        ],
    )
    assert [s.series_id for s in nipa] == ["A", "B"]
    assert nipa[0].title == "GDP" and nipa[0].attributes == {"table_name": "T1", "line_number": 1}
    nipa[0].sort()
    assert [o.period for o in nipa[0].data] == ["2024Q1", "2024Q2"]
    regional = group_rows(
        "Regional",
        [
            {
                "Code": "SAINC1-1",
                "GeoFips": "01000",
                "GeoName": "Alabama",
                "TimePeriod": "2023",
                "DataValue": "5",
            }
        ],
    )
    assert regional[0].series_id == "SAINC1-1:01000" and regional[0].title == "Alabama"
    assert regional[0].attributes == {"code": "SAINC1-1", "geo_fips": "01000"}
    io_rows = group_rows(
        "InputOutput",
        [
            {
                "TableID": 5,
                "Year": "2022",
                "RowCode": "11",
                "RowDescr": "Farms",
                "ColCode": "T1",
                "ColDescr": "Total",
                "DataValue": "9",
            }
        ],
    )
    assert io_rows[0].series_id == "5:11:T1" and io_rows[0].title == "Farms / Total"
    mne = group_rows(
        "MNE",
        [
            {
                "Year": "2022",
                "SeriesID": "7",
                "SeriesName": "Sales",
                "RowCode": "1",
                "ColumnCode": "2",
                "Row": "All",
                "Column": "Canada",
                "DataValue": "1",
            }
        ],
    )
    assert mne[0].series_id == "7:1:2" and mne[0].title == "Sales / All / Canada"
    assert "api_series_id" in mne[0].attributes  # SeriesID is reserved for our own column
    generic = group_rows(
        "Mystery",
        [
            {
                "Thing": "x",
                "ThingDescription": "X things",
                "Frequency": "A",
                "TimePeriod": "2020",
                "DataValue": "1",
            }
        ],
    )
    assert generic[0].series_id == "x" and generic[0].title == "X things"
    assert generic[0].attributes == {"frequency_code": "A"}
    assert (
        group_rows("Mystery", [{"TimePeriod": "2020", "DataValue": "1"}])[0].series_id == "Mystery"
    )


def test_series_merge_and_latest() -> None:
    a = Series("X", "t", [Observation("2020", "1", 1.0)], {"k": "v"})
    b = Series(
        "X", "", [Observation("2020", "1", 1.0), Observation("2021", "2", 2.0)], {"k": "w", "z": 1}
    )
    a.merge(b)
    assert [o.period for o in a.data] == ["2020", "2021"] and a.attributes == {"k": "v", "z": 1}
    assert a.latest is not None and a.latest.period == "2021"
    assert Series("E").latest is None


def test_data_response_roundtrip_and_notes() -> None:
    resp = DataResponse(
        dataset="NIPA",
        series=[
            Series(
                "X",
                "t",
                [
                    Observation(
                        "2020Q1", "1.5", 1.5, raw={"TimePeriod": "2020Q1", "DataValue": "1.5"}
                    )
                ],
            )
        ],
        notes=[Note("T1", "first"), Note("T2", "second")],
        params={"TableName": "T1", "Year": "2020", "UserID": "secret"},
        statistic="NIPA Table",
        production_time="now",
    )
    raw = resp.to_api_dict()
    assert raw["BEAAPI"]["Results"]["Data"] == [{"TimePeriod": "2020Q1", "DataValue": "1.5"}]
    assert raw["BEAAPI"]["Results"]["Statistic"] == "NIPA Table"
    names = [p["ParameterName"] for p in raw["BEAAPI"]["Request"]["RequestParam"]]
    assert names == ["METHOD", "DATASETNAME", "TABLENAME", "YEAR"]
    assert resp.note_text("T1, T2") == "first; second" and resp.note_text("ZZ") == ""
    assert resp.get("X") is not None and resp.get("Y") is None
    assert str(Note("A", "b")) == "A: b" and str(Note("", "b")) == "b"


def test_dataset_and_parameter_models() -> None:
    assert Dataset.from_api({"DatasetName": " NIPA ", "DatasetDescription": "x"}) == Dataset(
        "NIPA", "x"
    )
    p = Parameter.from_api(
        {
            "ParameterName": "Year",
            "ParameterIsRequiredFlag": "1",
            "MultipleAcceptedFlag": "0",
            "AllValue": "X",
        }
    )
    assert p.required and not p.multiple and p.to_record()["all_value"] == "X"


def test_dataset_info_helpers() -> None:
    assert canonical_name("nipa") == "NIPA" and canonical_name("gdpbyindustry") == "GDPbyIndustry"
    assert canonical_name("Unknown") == "Unknown"
    info = dataset_info("regional")
    assert info.table_param == "TableName" and "LineCode" in info.required and info.known
    unknown = dataset_info("Mystery")
    assert isinstance(unknown, DatasetInfo) and not unknown.known and unknown.all_years == "ALL"
    assert dataset_info("NIPA").all_years == "X" and dataset_info("NIPA").year_param == "Year"
