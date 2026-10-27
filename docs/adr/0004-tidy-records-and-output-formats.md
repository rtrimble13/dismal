# 0004. Tidy records as the canonical shape; JSON, JSONL, CSV, Parquet, table

Date: 2026-10-24
Status: accepted

## Context

Each API returns its own nested, string-typed JSON: BLS
`Results.series[].data[]` with period codes, newest-first ordering and
optional `catalog`/`calculations` sub-objects; BEA `Results.Data[]` rows whose
columns differ by dataset, with thousands separators and markers such as
`(D)`; FRED `{realtime_start, realtime_end, date, value}` observations with
`.` for missing data. Consumers want spreadsheets, dataframes, `jq` pipelines
and data lakes, and the same output flags whichever source they query.

## Decision

Normalise every observation of every source into a flat **record** with a
fixed core column order per source, typed values (`date` as a real date,
`value` as float or null), chronological order, and optional extra columns
appended in a defined order. All formats serialise the same records, with the
serialisers shared in `dismal.core.output`:

| format | purpose |
| --- | --- |
| `json` | default for pipes; array of objects |
| `jsonl` | streaming / append-friendly |
| `csv` | spreadsheets, pandas |
| `parquet` | typed columnar storage (pyarrow, snappy) |
| `table` | humans; default on a TTY |

A `--layout wide` pivot and a `--raw` escape hatch (API-shaped JSON, after
filtering, with any key removed) are provided; `--columns` projects
identically in every format.

The core columns differ per source because the APIs carry different
attributes on an observation:

- `dismal bls`: `series_id, date, year, period, period_name, frequency, value,
  footnotes, latest`, with catalog columns appended when `--catalog` is used.
- `dismal bea`: `dataset, series_id, series_title, date, year, period,
  frequency, value, unit, unit_mult, note_ref`, with the dataset's own
  dimension columns appended in snake_case and `--notes` adding table notes;
  `series_id` is derived as described in ADR 0017.
- `dismal fred`: `series_id, date, value`, with `realtime_start`/`realtime_end`
  appended under `--as-of` and the series metadata (`title, units, frequency,
  seasonal_adjustment, last_updated`) under `--meta`, because FRED observations
  carry no period code, frequency or footnotes of their own (ADR 0018).

## Consequences

- Column names and order are part of the contract; adding columns is a minor
  change, renaming or reordering core columns is major.
- `date` is the *first day* of the period for monthly, quarterly and annual
  data; quarterly/annual consumers must not read it as a period end. FRED
  daily and weekly series carry their actual observation date.
- Extra columns vary by survey or dataset and may be empty; CSV takes the
  union of keys. BEA's `unit_mult` must be applied by the consumer
  (`value * 10 ** unit_mult`); FRED's `--units` transformations change what
  `value` means without changing the column name.
