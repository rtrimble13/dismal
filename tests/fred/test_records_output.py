from __future__ import annotations

import csv
import io
import json
from datetime import date

import pyarrow.parquet as pq

from dismal.fred.models import Observation, Series, SeriesInfo
from dismal.fred.output import (
    OutputFormat,
    records_to_csv,
    records_to_json,
    records_to_jsonl,
    records_to_parquet,
    records_to_table,
    write_records,
)
from dismal.fred.records import CORE_COLUMNS, column_order, stringify, to_records, to_wide


def _series() -> Series:
    obs = [
        Observation(date(2023, 11, 1), "1", 1.0, date(2024, 1, 1), date(9999, 12, 31)),
        Observation(date(2023, 12, 1), ".", None, date(2024, 1, 1), date(9999, 12, 31)),
        Observation(date(2024, 1, 1), "3", 3.0, date(2024, 1, 1), date(9999, 12, 31)),
    ]
    info = SeriesInfo(
        "S1",
        "Title",
        units="Percent",
        frequency="Monthly",
        seasonal_adjustment_short="SA",
        last_updated="2024-02-02 07:46:02-05",
    )
    return Series("S1", obs, info)


def test_to_records_core_columns_and_extras() -> None:
    recs = to_records([_series()], include_meta=True, include_realtime=True)
    cols = column_order(recs)
    assert tuple(cols[:3]) == CORE_COLUMNS
    assert cols[3:] == [
        "realtime_start",
        "realtime_end",
        "title",
        "units",
        "frequency",
        "seasonal_adjustment",
        "last_updated",
    ]
    assert (
        recs[1]["value"] is None
        and recs[0]["title"] == "Title"
        and recs[0]["realtime_start"] == date(2024, 1, 1)
    )
    plain = to_records([_series()])
    assert list(plain[0]) == ["series_id", "date", "value"]
    assert (
        to_records([Series("E", [Observation(date(2020, 1, 1), "1", 1.0)])], include_meta=True)[
            0
        ].get("title")
        is None
    )


def test_to_wide_pivots_series() -> None:
    a = Series(
        "A", [Observation(date(2024, 1, 1), "1", 1.0), Observation(date(2024, 2, 1), "2", 2.0)]
    )
    b = Series("B", [Observation(date(2024, 1, 1), "10", 10.0)])
    wide = to_wide(to_records([a, b]))
    assert list(wide[0]) == ["date", "A", "B"]
    assert wide[0]["A"] == 1.0 and wide[0]["B"] == 10.0 and wide[1]["B"] is None


def test_column_order_for_non_data_records() -> None:
    assert column_order([{"kind": "x", "id": "y", "frequency": "z"}]) == ["kind", "id", "frequency"]


def test_stringify() -> None:
    assert (
        stringify(None) == ""
        and stringify(True) == "true"
        and stringify(date(2024, 1, 1)) == "2024-01-01"
    )
    assert stringify(3.0) == "3.0" and stringify(1e16) == "1e+16" and stringify(["a"]) == '["a"]'


def test_serialisers_roundtrip() -> None:
    recs = to_records([_series()], include_realtime=True)
    cols = column_order(recs)
    rows = list(csv.DictReader(io.StringIO(records_to_csv(recs, cols))))
    assert rows[0]["date"] == "2023-11-01" and rows[0]["value"] == "1.0" and rows[1]["value"] == ""
    data = json.loads(records_to_json(recs))
    assert data[0]["date"] == "2023-11-01" and data[0]["realtime_end"] == "9999-12-31"
    lines = records_to_jsonl(recs).splitlines()
    assert len(lines) == 3 and json.loads(lines[-1])["value"] == 3.0
    table = pq.read_table(io.BytesIO(records_to_parquet(recs, cols)))
    assert table.num_rows == 3
    assert str(table.schema.field("date").type) == "date32[day]"
    assert str(table.schema.field("value").type) == "double"
    assert table.column("value")[1].as_py() is None
    text = records_to_table(recs, cols, title="t", no_color=True, width=400)
    assert "series_id" in text and "\x1b[" not in text
    assert "rows)" in records_to_table([], ["a"], no_color=True, width=400)


def test_parquet_column_types() -> None:
    table = pq.read_table(io.BytesIO(records_to_parquet([{"a": None}, {"a": None}], ["a"])))
    assert str(table.schema.field("a").type) == "string"
    table = pq.read_table(io.BytesIO(records_to_parquet([{"b": True}, {"b": None}], ["b"])))
    assert str(table.schema.field("b").type) == "bool"
    table = pq.read_table(io.BytesIO(records_to_parquet([{"c": 1}, {"c": 2}], ["c"])))
    assert str(table.schema.field("c").type) == "int64"
    table = pq.read_table(io.BytesIO(records_to_parquet([{"d": ["x"]}, {"d": {"k": 1}}], ["d"])))
    assert table.column("d")[1].as_py() == '{"k": 1}'


def test_write_records_to_file(tmp_path) -> None:
    recs = to_records([_series()])
    out = tmp_path / "x.csv"
    write_records(recs, OutputFormat.CSV, out)
    assert out.read_text().startswith("series_id,date,value")
    out2 = tmp_path / "x.parquet"
    write_records(recs, OutputFormat.PARQUET, out2)
    assert pq.read_table(out2).num_rows == 3
    out3 = tmp_path / "x.txt"
    write_records(recs, OutputFormat.TABLE, out3, columns=["date", "value"])
    assert "\x1b[" not in out3.read_text() and "series_id" not in out3.read_text()
    out4 = tmp_path / "x.jsonl"
    write_records(recs, OutputFormat.JSONL, out4)
    assert len(out4.read_text().splitlines()) == 3
