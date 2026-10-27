"""Serialisers for records (shared with every source; see :mod:`dismal.core.output`)."""

from dismal.core.output import (
    BINARY_FORMATS,
    OutputFormat,
    open_output,
    records_to_csv,
    records_to_json,
    records_to_jsonl,
    records_to_parquet,
    records_to_table,
    write_json,
    write_records,
)

__all__ = [
    "BINARY_FORMATS",
    "OutputFormat",
    "open_output",
    "records_to_csv",
    "records_to_json",
    "records_to_jsonl",
    "records_to_parquet",
    "records_to_table",
    "write_json",
    "write_records",
]
