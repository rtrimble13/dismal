"""Serialisers for records: JSON, JSON Lines, CSV, Parquet and a rich table.

Shared by every source. Callers normally pass ``columns`` (computed by the
source's ``column_order``); without it columns appear in first-seen order.
"""

from __future__ import annotations

import csv
import io
import json
import sys
from collections.abc import Sequence
from datetime import date
from enum import Enum
from pathlib import Path
from typing import IO, Any

from dismal.core.records import Record, first_seen_columns, jsonable, stringify


class OutputFormat(str, Enum):
    JSON = "json"
    JSONL = "jsonl"
    CSV = "csv"
    PARQUET = "parquet"
    TABLE = "table"

    def __str__(self) -> str:  # pragma: no cover - trivial
        return self.value


BINARY_FORMATS = {OutputFormat.PARQUET}
_NUMERIC_COLUMNS = {
    "value",
    "year",
    "score",
    "unit_mult",
    "line_number",
    "bytes",
    "latest_value",
    "popularity",
}


def write_records(
    records: Sequence[Record],
    fmt: OutputFormat,
    destination: str | Path | None = None,
    *,
    columns: Sequence[str] | None = None,
    title: str | None = None,
    no_color: bool = False,
) -> None:
    """Write ``records`` to ``destination`` (``None``/``"-"`` means stdout)."""
    cols = list(columns) if columns is not None else first_seen_columns(records)
    if columns is not None:  # project every format onto the requested columns, in order
        records = [{c: rec.get(c) for c in cols} for rec in records]
    to_stdout = destination is None or str(destination) == "-"

    if fmt is OutputFormat.PARQUET:
        data = records_to_parquet(records, cols)
        if to_stdout:
            sys.stdout.buffer.write(data)
            sys.stdout.buffer.flush()
        else:
            Path(destination).write_bytes(data)  # type: ignore[arg-type]
        return

    if fmt is OutputFormat.TABLE:
        text = records_to_table(records, cols, title=title, no_color=no_color or not to_stdout)
    elif fmt is OutputFormat.CSV:
        text = records_to_csv(records, cols)
    elif fmt is OutputFormat.JSONL:
        text = records_to_jsonl(records)
    else:
        text = records_to_json(records)

    if to_stdout:
        sys.stdout.write(text)
        sys.stdout.flush()
    else:
        Path(destination).write_text(text, encoding="utf-8")  # type: ignore[arg-type]


def write_json(obj: Any, destination: str | Path | None = None) -> None:
    text = json.dumps(obj, indent=2, default=jsonable) + "\n"
    if destination is None or str(destination) == "-":
        sys.stdout.write(text)
        sys.stdout.flush()
    else:
        Path(destination).write_text(text, encoding="utf-8")


def records_to_json(records: Sequence[Record]) -> str:
    return json.dumps([_jsonable_record(r) for r in records], indent=2, default=jsonable) + "\n"


def records_to_jsonl(records: Sequence[Record]) -> str:
    buf = io.StringIO()
    for rec in records:
        buf.write(json.dumps(_jsonable_record(rec), default=jsonable, separators=(",", ":")))
        buf.write("\n")
    return buf.getvalue()


def records_to_csv(records: Sequence[Record], columns: Sequence[str]) -> str:
    buf = io.StringIO()
    writer = csv.writer(buf, lineterminator="\n")
    writer.writerow(columns)
    for rec in records:
        writer.writerow([stringify(rec.get(c)) for c in columns])
    return buf.getvalue()


def records_to_parquet(records: Sequence[Record], columns: Sequence[str]) -> bytes:
    import pyarrow as pa
    import pyarrow.parquet as pq

    arrays: dict[str, Any] = {}
    for col in columns:
        values = [rec.get(col) for rec in records]
        arrays[col] = _arrow_array(col, values)
    table = pa.table(arrays) if arrays else pa.table({})
    sink = pa.BufferOutputStream()
    pq.write_table(table, sink, compression="snappy")
    return bytes(sink.getvalue().to_pybytes())


def _arrow_array(name: str, values: list[Any]) -> Any:
    import pyarrow as pa

    non_null = [v for v in values if v is not None]
    if not non_null:
        return pa.array(values, type=pa.string())
    sample = non_null[0]
    if all(isinstance(v, bool) for v in non_null):
        return pa.array(values, type=pa.bool_())
    if all(isinstance(v, int) and not isinstance(v, bool) for v in non_null):
        return pa.array(values, type=pa.int64())
    if all(isinstance(v, (int, float)) and not isinstance(v, bool) for v in non_null):
        return pa.array([float(v) if v is not None else None for v in values], type=pa.float64())
    if isinstance(sample, date) and all(isinstance(v, date) for v in non_null):
        return pa.array(values, type=pa.date32())
    if all(isinstance(v, (list, dict)) for v in non_null):
        return pa.array(
            [json.dumps(v, default=jsonable) if v is not None else None for v in values],
            type=pa.string(),
        )
    return pa.array([stringify(v) if v is not None else None for v in values], type=pa.string())


def records_to_table(
    records: Sequence[Record],
    columns: Sequence[str],
    *,
    title: str | None = None,
    no_color: bool = False,
    width: int | None = None,
) -> str:
    from rich.console import Console
    from rich.table import Table

    table = Table(title=title, show_lines=False, header_style="bold", expand=False)
    for col in columns:
        numeric = col in _NUMERIC_COLUMNS or col.startswith(("net_", "pct_"))
        table.add_column(col, justify="right" if numeric else "left", overflow="fold")
    for rec in records:
        table.add_row(*[stringify(rec.get(c)) for c in columns])
    if not records:
        table.caption = "(no rows)"
    is_tty = sys.stdout.isatty()
    color = is_tty and not no_color
    if width is None and not is_tty:
        # Not a terminal: render at the table's natural width so nothing folds.
        probe = Console(file=io.StringIO(), width=4000, no_color=True, force_terminal=False)
        width = max(20, probe.measure(table).maximum)
    buf = io.StringIO()
    console = Console(
        file=buf,
        force_terminal=color,
        color_system="auto" if color else None,
        width=width,
        no_color=not color,
    )
    console.print(table)
    return buf.getvalue()


def _jsonable_record(rec: Record) -> dict[str, Any]:
    return {k: jsonable(v) for k, v in rec.items()}


def open_output(destination: str | Path | None, binary: bool = False) -> IO[Any]:
    if destination is None or str(destination) == "-":
        return sys.stdout.buffer if binary else sys.stdout
    return Path(destination).open("wb" if binary else "w", encoding=None if binary else "utf-8")
