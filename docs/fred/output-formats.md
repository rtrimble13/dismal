# Output formats and schemas

Every record-producing command supports `--format json|jsonl|csv|parquet|table`
and `--output PATH`. The same records feed all formats; only the encoding
changes. `--columns` projects and orders columns identically in every format.

## Default format

| stdout is | default |
| --- | --- |
| a terminal | `table` |
| a pipe or file | `json` |

Override with `FRED_FORMAT` or `--format`. Automations should pass `--format`
explicitly.

## Long layout (default for `dismal fred data`)

One row per (series, date). Core columns, always first and in this order:

| Column | Type (JSON / Parquet) | Description |
| --- | --- | --- |
| `series_id` | string | FRED series id, upper-case |
| `date` | ISO date string / `date32` | Observation date: the first day of the period for monthly, quarterly and annual series, the actual day for daily and weekly ones |
| `value` | number or null / `double` | Observation after any `--units` transformation; `null` where FRED reports `.` |

Optional columns, appended in this order when requested:

| Flag | Columns |
| --- | --- |
| `--as-of` | `realtime_start`, `realtime_end` (ISO dates): the period during which this value was the published one; `9999-12-31` means "still current" |
| `--meta` | `title`, `units`, `frequency`, `seasonal_adjustment` (short code: `SA`, `NSA`, `SAAR`), `last_updated` |

Rows are sorted by date per series; `--descending` reverses. Series appear in
the order requested.

## Wide layout (`--layout wide`)

One row per date, one column per series id:

```
date, <SERIES_ID_1>, <SERIES_ID_2>, ...
```

Missing values are `null`/empty. Mixing frequencies produces rows for every
distinct date (a daily series next to a monthly one leaves the monthly column
empty on most days; use `--frequency` to align them). Metadata and vintage
columns are not available in wide layout.

## Formats

### `json`

A pretty-printed array of objects. Dates are ISO strings.

```json
[
  {
    "series_id": "UNRATE",
    "date": "2024-03-01",
    "value": 3.8
  }
]
```

### `jsonl`

One compact JSON object per line; ideal for streaming into `jq` or appending to
files.

### `csv`

RFC 4180 with a header row and `\n` line endings. Booleans are `true`/`false`,
nulls are empty strings, lists/dicts are JSON strings.

### `parquet`

Snappy-compressed, one row group. Types: strings as `string`, integers as
`int64`, floats as `double`, booleans as `bool`, dates as `date32[day]`;
columns that are entirely null are `string`. Writing to stdout emits the binary
file (`dismal fred data ... -f parquet > x.parquet`).

### `table`

A box-drawn table (rich). Colour only when stdout is a terminal and `NO_COLOR`
is unset. When piped, the table is rendered at its natural width with no ANSI
escapes. Intended for people, not parsers.

## `--raw`

Bypasses record flattening and prints the request parameters, any messages,
and each series' observations with their original string values (close to
the API's own shape, with the key removed):

```json
{
  "params": {"observation_start": "2024-11-01", "observation_end": "2024-12-31", "units": "pc1"},
  "messages": [],
  "series": [
    {
      "series_id": "UNRATE",
      "count": 2,
      "observations": [
        {"realtime_start": "2026-10-25", "realtime_end": "2026-10-25", "date": "2024-11-01", "value": "4.2"},
        {"realtime_start": "2026-10-25", "realtime_end": "2026-10-25", "date": "2024-12-01", "value": "4.1"}
      ]
    }
  ]
}
```

## Other commands

| Command | Columns |
| --- | --- |
| `search` | `kind, id, title, score, frequency, seasonal, units, source` |
| `series info`, `series search`, `series updates`, `releases series`, `categories series` | `id, title, frequency, units, seasonal_adjustment, observation_start, observation_end, last_updated, popularity` (+ `notes` with `--notes` on `series info`) |
| `series vintages` | `series_id, vintage_date` |
| `releases` | `id, name, press_release, link` (+ `score` with `--query`) |
| `releases dates` | `date, release_id, release_name` |
| `categories`, `categories children` | `id, name, parent_id` (+ `score` with `--query`) |
| `cache info` | `file, bytes` |

`config`, `doctor` and `releases show` always print JSON objects.
