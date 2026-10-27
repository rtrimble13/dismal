from __future__ import annotations

import csv
import io
import json
from datetime import date

import pyarrow.parquet as pq

from dismal.bea.filters import ObservationFilter
from dismal.bea.models import Observation, Series
from dismal.bea.output import (
    OutputFormat,
    records_to_csv,
    records_to_json,
    records_to_jsonl,
    records_to_parquet,
    records_to_table,
    write_records,
)
from dismal.bea.periods import Frequency, YearMonth
from dismal.bea.records import CORE_COLUMNS, column_order, stringify, to_records, to_wide


def _series() -> Series:
    obs = [
        Observation("2023Q4", "1", 1.0, "Level", 6, "T1"),
        Observation("2023", "1.5", 1.5, "Level", 6, "T1"),
        Observation("2024Q1", "3", 3.0, "Level", 6, "T1"),
        Observation("2024M01", "9", 9.0, "Level", 6, ""),
        Observation("2024Q2", "(D)", None, "Level", 6, "T1"),
    ]
    s = Series("S1", "Title", obs, {"table_name": "T1", "line_number": 1})
    s.sort()
    return s


def test_filter_date_range_frequency_latest() -> None:
    s = _series()
    f = ObservationFilter(start=YearMonth(2023, 12), end=YearMonth(2024, 1))
    assert [o.period for o in f.apply([s])[0].data] == ["2023Q4", "2023", "2024M01", "2024Q1"]
    f = ObservationFilter(frequencies=frozenset({Frequency.QUARTERLY}))
    assert [o.period for o in f.apply([s])[0].data] == ["2023Q4", "2024Q1", "2024Q2"]
    f = ObservationFilter(frequencies=frozenset({Frequency.ANNUAL}))
    assert [o.period for o in f.apply([s])[0].data] == ["2023"]
    assert ObservationFilter().is_noop and not f.is_noop
    latest = ObservationFilter(only_latest=True).apply([s])[0]
    assert [o.period for o in latest.data] == ["2024Q2"] and latest.attributes == s.attributes


def test_to_records_core_columns_and_extras() -> None:
    recs = to_records(
        [_series()], dataset="NIPA", include_notes=True, note_text=lambda r: f"note {r}"
    )
    cols = column_order(recs)
    assert tuple(cols[: len(CORE_COLUMNS)]) == CORE_COLUMNS
    assert cols[len(CORE_COLUMNS) :] == ["notes", "table_name", "line_number"]
    first = recs[0]
    assert first["date"] == date(2023, 10, 1) and first["frequency"] == "quarterly"
    assert first["notes"] == "note T1" and first["unit_mult"] == 6 and first["dataset"] == "NIPA"
    suppressed = next(r for r in recs if r["period"] == "2024Q2")
    assert suppressed["value"] is None
    jan = next(r for r in recs if r["period"] == "2024M01")
    assert jan["notes"] == "" and jan["frequency"] == "monthly"


def test_to_wide_pivots_series() -> None:
    a = Series("A", "", [Observation("2024Q1", "1", 1.0), Observation("2024Q2", "2", 2.0)])
    b = Series("B", "", [Observation("2024Q1", "10", 10.0)])
    wide = to_wide(to_records([a, b], dataset="X"))
    assert list(wide[0]) == ["date", "year", "period", "A", "B"]
    assert wide[0]["A"] == 1.0 and wide[0]["B"] == 10.0
    assert wide[1]["A"] == 2.0 and wide[1]["B"] is None


def test_column_order_for_non_data_records() -> None:
    assert column_order([{"kind": "x", "id": "y", "frequency": "z"}]) == ["kind", "id", "frequency"]


def test_stringify() -> None:
    assert stringify(None) == ""
    assert stringify(True) == "true"
    assert stringify(date(2024, 1, 1)) == "2024-01-01"
    assert stringify(3.0) == "3.0"
    assert stringify(1234.5) == "1234.5"
    assert stringify(1e16) == "1e+16"
    assert stringify(["a"]) == '["a"]'


def test_serialisers_roundtrip() -> None:
    recs = to_records([_series()], dataset="NIPA")
    cols = column_order(recs)
    rows = list(csv.DictReader(io.StringIO(records_to_csv(recs, cols))))
    assert (
        rows[0]["date"] == "2023-10-01"
        and rows[0]["value"] == "1.0"
        and rows[0]["unit_mult"] == "6"
    )
    assert rows[-1]["value"] == ""
    data = json.loads(records_to_json(recs))
    assert data[0]["date"] == "2023-10-01" and data[0]["value"] == 1.0
    lines = records_to_jsonl(recs).splitlines()
    assert len(lines) == len(recs) and json.loads(lines[-1])["period"] == "2024Q2"
    table = pq.read_table(io.BytesIO(records_to_parquet(recs, cols)))
    assert table.num_rows == len(recs)
    assert str(table.schema.field("date").type) == "date32[day]"
    assert str(table.schema.field("value").type) == "double"
    assert str(table.schema.field("year").type) == "int64"
    assert str(table.schema.field("unit_mult").type) == "int64"
    assert table.column("date")[0].as_py() == date(2023, 10, 1)
    text = records_to_table(recs, cols, title="t", no_color=True, width=400)
    assert "series_id" in text and "\x1b[" not in text
    assert "rows)" in records_to_table([], ["a"], no_color=True, width=400)  # caption wraps


def test_parquet_column_types() -> None:
    table = pq.read_table(io.BytesIO(records_to_parquet([{"a": None}, {"a": None}], ["a"])))
    assert str(table.schema.field("a").type) == "string"
    table = pq.read_table(io.BytesIO(records_to_parquet([{"b": True}, {"b": None}], ["b"])))
    assert str(table.schema.field("b").type) == "bool"
    table = pq.read_table(io.BytesIO(records_to_parquet([{"c": ["x"]}, {"c": {"k": 1}}], ["c"])))
    assert table.column("c")[1].as_py() == '{"k": 1}'


def test_write_records_to_file(tmp_path) -> None:
    recs = to_records([_series()], dataset="NIPA")
    out = tmp_path / "x.csv"
    write_records(recs, OutputFormat.CSV, out)
    assert out.read_text().startswith("dataset,series_id,series_title,date,year")
    out2 = tmp_path / "x.parquet"
    write_records(recs, OutputFormat.PARQUET, out2)
    assert pq.read_table(out2).num_rows == len(recs)
    out3 = tmp_path / "x.txt"
    write_records(recs, OutputFormat.TABLE, out3, columns=["period", "value"])
    text = out3.read_text()
    assert "\x1b[" not in text and "period" in text and "series_id" not in text
    out4 = tmp_path / "x.jsonl"
    write_records(recs, OutputFormat.JSONL, out4)
    assert len(out4.read_text().splitlines()) == len(recs)
