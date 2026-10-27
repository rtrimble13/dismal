from __future__ import annotations

import csv
import io
import json
from datetime import date

import pyarrow.parquet as pq

from dismal.bls.filters import ObservationFilter
from dismal.bls.models import Observation, Series
from dismal.bls.output import (
    OutputFormat,
    records_to_csv,
    records_to_json,
    records_to_jsonl,
    records_to_parquet,
    records_to_table,
    write_records,
)
from dismal.bls.periods import Frequency, YearMonth
from dismal.bls.records import CORE_COLUMNS, column_order, stringify, to_records, to_wide


def _series() -> Series:
    obs = [
        Observation(2023, "M11", "November", "1", 1.0),
        Observation(2023, "M12", "December", "2", 2.0),
        Observation(2023, "M13", "Annual", "1.5", 1.5),
        Observation(
            2024,
            "M01",
            "January",
            "3",
            3.0,
            latest=True,
            calculations={"net_changes": {"1": "1.0", "12": "2.0"}, "pct_changes": {"1": "50.0"}},
        ),
        Observation(2024, "Q01", "1st Quarter", "9", 9.0),
    ]
    return Series(
        "S1",
        obs,
        catalog={"series_id": "S1", "series_title": "Title", "seasonality": "SA", "x": ""},
    )


def test_filter_date_range_and_frequency() -> None:
    s = _series()
    f = ObservationFilter(start=YearMonth(2023, 12), end=YearMonth(2024, 1))
    kept = f.apply([s])[0].data
    assert [(o.year, o.period) for o in kept] == [
        (2023, "M12"),
        (2023, "M13"),
        (2024, "M01"),
        (2024, "Q01"),
    ]
    f = ObservationFilter(frequencies=frozenset({Frequency.MONTHLY}))
    assert [o.period for o in f.apply([s])[0].data] == ["M11", "M12", "M01"]
    f = ObservationFilter(frequencies=frozenset({Frequency.ANNUAL}))
    assert [o.period for o in f.apply([s])[0].data] == ["M13"]
    f = ObservationFilter(include_annual_average=False)
    assert "M13" not in [o.period for o in f.apply([s])[0].data]
    assert ObservationFilter().is_noop and not f.is_noop
    assert [o.period for o in ObservationFilter(only_latest=True).apply([s])[0].data] == ["M01"]


def test_to_records_core_columns_and_extras() -> None:
    recs = to_records(
        [_series()],
        include_catalog=True,
        include_calculations=True,
        include_annual_average_flag=True,
    )
    cols = column_order(recs)
    assert tuple(cols[: len(CORE_COLUMNS)]) == CORE_COLUMNS
    assert cols[len(CORE_COLUMNS) :][:2] == ["annual_average", "series_title"]
    assert "x" not in cols  # empty catalog values dropped
    first = recs[0]
    assert first["date"] == date(2023, 11, 1)
    assert first["frequency"] == "monthly"
    assert first["net_change_1"] is None
    jan = next(r for r in recs if r["period"] == "M01")
    assert jan["net_change_1"] == 1.0 and jan["pct_change_1"] == 50.0 and jan["latest"] is True
    assert next(r for r in recs if r["period"] == "M13")["annual_average"] is True


def test_to_wide_pivots_series() -> None:
    a = Series(
        "A",
        [
            Observation(2024, "M01", "January", "1", 1.0),
            Observation(2024, "M02", "February", "2", 2.0),
        ],
    )
    b = Series("B", [Observation(2024, "M01", "January", "10", 10.0)])
    wide = to_wide(to_records([a, b]))
    assert list(wide[0]) == ["date", "year", "period", "period_name", "A", "B"]
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
    assert stringify(["a"]) == '["a"]'


def test_serialisers_roundtrip() -> None:
    recs = to_records([_series()], include_calculations=True)
    cols = column_order(recs)
    rows = list(csv.DictReader(io.StringIO(records_to_csv(recs, cols))))
    assert (
        rows[0]["date"] == "2023-11-01"
        and rows[0]["value"] == "1.0"
        and rows[0]["latest"] == "false"
    )
    assert rows[0]["net_change_1"] == ""
    data = json.loads(records_to_json(recs))
    assert data[0]["date"] == "2023-11-01" and data[0]["value"] == 1.0
    lines = records_to_jsonl(recs).splitlines()
    assert len(lines) == len(recs) and json.loads(lines[-1])["period"] == "Q01"
    table = pq.read_table(io.BytesIO(records_to_parquet(recs, cols)))
    assert table.num_rows == len(recs)
    assert str(table.schema.field("date").type) == "date32[day]"
    assert str(table.schema.field("value").type) == "double"
    assert str(table.schema.field("year").type) == "int64"
    assert str(table.schema.field("latest").type) == "bool"
    assert table.column("date")[0].as_py() == date(2023, 11, 1)
    text = records_to_table(recs, cols, title="t", no_color=True, width=400)
    assert "series_id" in text and "\x1b[" not in text


def test_parquet_all_null_column_is_string() -> None:
    table = pq.read_table(io.BytesIO(records_to_parquet([{"a": None}, {"a": None}], ["a"])))
    assert str(table.schema.field("a").type) == "string"


def test_write_records_to_file(tmp_path) -> None:
    recs = to_records([_series()])
    out = tmp_path / "x.csv"
    write_records(recs, OutputFormat.CSV, out)
    assert out.read_text().startswith("series_id,date,year")
    out2 = tmp_path / "x.parquet"
    write_records(recs, OutputFormat.PARQUET, out2)
    assert pq.read_table(out2).num_rows == len(recs)
    out3 = tmp_path / "x.txt"
    write_records(recs, OutputFormat.TABLE, out3)
    assert "\x1b[" not in out3.read_text()
