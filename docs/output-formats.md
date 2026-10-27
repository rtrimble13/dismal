# Output formats and schemas

Every record-producing command of every source supports `--format
json|jsonl|csv|parquet|table`, `--output PATH` and `--columns`. The same
records feed all formats; only the encoding changes. The formats are
implemented once, in `dismal.core.output`
([ADR 0004](adr/0004-tidy-records-and-output-formats.md)), so a consumer
that reads one source's output reads the others' too. What differs per
source is the set of columns; see the schema section at the end.

## Default format

| stdout is | default |
| --- | --- |
| a terminal | `table` |
| a pipe or file | `json` |

Override with `--format` or the source's `<SOURCE>_FORMAT` variable
(`BLS_FORMAT`, `BEA_FORMAT`, `FRED_FORMAT`). Automations should pass
`--format` explicitly.

## Options

| Option | Effect |
| --- | --- |
| `-f, --format FORMAT` | One of `json`, `jsonl`, `csv`, `parquet`, `table`. |
| `-o, --output PATH` | Write to a file instead of stdout (`-` = stdout). A note `wrote N row(s) to PATH` goes to stderr. Parquet to stdout writes the binary file. |
| `--columns a,b,c` | Emit only these columns, in this order, in every format. Unknown names are a usage error (exit 2). |

## Long and wide layout

`data` and `latest` default to the **long** layout: one row per (series,
period), core columns first and in a fixed order, optional columns appended
in a fixed order when requested. Rows are chronological per series
(`--descending` reverses).

`--layout wide` pivots to one row per period with one value column per
series id:

```
date, <period columns>, <SERIES_ID_1>, <SERIES_ID_2>, ...
```

Missing values are `null`/empty. Mixing frequencies produces rows for every
distinct period. Metadata, dimension, note, vintage and calculation columns
are not available in wide layout; use the long layout to map ids to titles.

Every source's long layout shares three columns:

| Column | Type (JSON / Parquet) | Description |
| --- | --- | --- |
| `series_id` | string | The source's series id, upper-case |
| `date` | ISO date string / `date32` | First day of the period (`2024-04-01` for Q2 2024, `2024-01-01` for annual); the actual day for daily and weekly FRED series |
| `value` | number or null / `double` | The observation; `null` where the source reports a missing value |

## Formats

### `json`

A pretty-printed array of objects. Dates are ISO strings, numbers are
numbers, missing values are `null`.

### `jsonl`

One compact JSON object per line; ideal for streaming into `jq` or appending
to files, and the safest choice when a single malformed row must not spoil a
batch.

### `csv`

RFC 4180 with a header row and `\n` line endings. Booleans are
`true`/`false`, nulls are empty strings, lists/dicts are JSON strings.

### `parquet`

Snappy-compressed, one row group. Types: strings as `string`, integers as
`int64`, floats as `double`, booleans as `bool`, dates as `date32[day]`;
columns that are entirely null are `string`. Writing to stdout emits the
binary file (`dismal fred data ... -f parquet > x.parquet`). The typing rules
are identical for every source, so files from different sources can be
concatenated on their shared columns.

### `table`

A box-drawn table (rich). Colour only when stdout is a terminal and
`NO_COLOR` is unset. When piped, the table is rendered at its natural width
with no ANSI escapes. Intended for people, not parsers.

## `--raw`

`data` in every source accepts `--raw`, which bypasses record flattening and
prints the API's own shape (merged across split requests, after client-side
filtering, with any key removed). JSON only; the exact shape is documented
per source.

## JSON-only commands

`config`, `doctor` (per source and top level) and the single-object commands
(`dismal bls surveys show`, `dismal fred releases show`) always print JSON
objects and accept only `--output`.

## Record schema per source

| Source | Long-layout core columns | Reference |
| --- | --- | --- |
| `bls` | `series_id, date, year, period, period_name, frequency, value, footnotes, latest` (+ `annual_average`, catalog fields, `net_change_N`/`pct_change_N`, `aspects` on request) | [bls/output-formats.md](bls/output-formats.md) |
| `bea` | `dataset, series_id, series_title, date, year, period, frequency, value, unit, unit_mult, note_ref` (+ `notes` and the dataset's dimension columns) | [bea/output-formats.md](bea/output-formats.md) |
| `fred` | `series_id, date, value` (+ `realtime_start`/`realtime_end` with `--as-of`, `title, units, frequency, seasonal_adjustment, last_updated` with `--meta`) | [fred/output-formats.md](fred/output-formats.md) |

The per-source pages also list the columns of every discovery command and
show the `--raw` shape. `dismal cache info` at the top level prints
`source, file, bytes`; per source it prints `file, bytes`.
