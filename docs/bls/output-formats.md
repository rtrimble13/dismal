# Output formats and schemas

Every record-producing command supports `--format json|jsonl|csv|parquet|table`
and `--output PATH`. The same records feed all formats; only the encoding
changes. `--columns` projects and orders columns identically in every format.

## Default format

| stdout is | default |
| --- | --- |
| a terminal | `table` |
| a pipe or file | `json` |

Override with `BLS_FORMAT` or `--format`. Automations should pass `--format`
explicitly.

## Long layout (default for `dismal bls data`)

One row per (series, period). Core columns, always first and in this order:

| Column | Type (JSON / Parquet) | Description |
| --- | --- | --- |
| `series_id` | string | BLS series id, upper-case |
| `date` | ISO date string / `date32` | First day of the period (`2024-04-01` for Q2 2024, `2024-01-01` for annual) |
| `year` | integer / `int64` | Calendar year |
| `period` | string | BLS period code (`M03`, `Q02`, `S01`, `A01`, `M13`) |
| `period_name` | string | BLS label (`March`, `2nd Quarter`, `Annual`) |
| `frequency` | string | `monthly`, `quarterly`, `semiannual`, `annual` |
| `value` | number or null / `double` | Observation; `null` when BLS reports `-` |
| `footnotes` | string | `CODE: text; CODE: text` or empty |
| `latest` | boolean / `bool` | `true` on the newest observation returned by the API |

Optional columns, appended in this order when requested:

| Flag | Columns |
| --- | --- |
| `--annual-average` | `annual_average` (boolean; `true` for `M13`/`Q05`/`S03`) |
| `--catalog` | `series_title`, then the remaining catalog fields as returned by the API (`survey_name`, `survey_abbreviation`, `seasonality`, `measure_data_type`, `area`, `item`, ...). Empty fields are omitted; the set varies by survey. |
| `--calculations` | `net_change_1`, `pct_change_1`, `net_change_3`, `pct_change_3`, `net_change_6`, `pct_change_6`, `net_change_12`, `pct_change_12` (numbers or null) |
| `--aspects` | `aspects` (list in JSON, JSON string in CSV/Parquet) |

Rows are sorted chronologically per series (annual averages after the periods
they summarise); `--descending` reverses. Series appear in the order requested.

## Wide layout (`--layout wide`)

One row per period, one column per series:

```
date, year, period, period_name, <SERIES_ID_1>, <SERIES_ID_2>, ...
```

Missing values are `null`/empty. Mixing frequencies produces rows for every
distinct period. Catalog and calculation columns are not available in wide
layout.

## Formats

### `json`

A pretty-printed array of objects. Dates are ISO strings.

```json
[
  {
    "series_id": "LNS14000000",
    "date": "2024-03-01",
    "year": 2024,
    "period": "M03",
    "period_name": "March",
    "frequency": "monthly",
    "value": 3.8,
    "footnotes": "",
    "latest": false
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
file (`dismal bls data ... -f parquet > x.parquet`).

### `table`

A box-drawn table (rich). Colour only when stdout is a terminal and `NO_COLOR`
is unset. When piped, the table is rendered at its natural width with no ANSI
escapes. Intended for people, not parsers.

## `--raw`

Bypasses record flattening and prints the API's own shape, merged across split
requests and after client-side filters:

```json
{
  "status": "REQUEST_SUCCEEDED",
  "responseTime": 42,
  "message": [],
  "Results": {
    "series": [
      {"seriesID": "LNS14000000", "data": [{"year": "2024", "period": "M03", "periodName": "March", "value": "3.8", "footnotes": [{}]}]}
    ]
  }
}
```

## Other commands

| Command | Columns |
| --- | --- |
| `search` | `kind, id, title, survey, score, frequency, seasonal, units` |
| `surveys` | `abbreviation, name` (+ `score` with `--query`) |
| `popular` | `series_id, survey, survey_name` (+ `title` with `--catalog`) |
| `series list` | `series_id, title` (+ `score` with `--query`), then the flat file's columns |
| `series info` | `series_id`, catalog fields, `latest_year, latest_period, latest_value` |
| `cache info` | `file, bytes` |

`config`, `doctor` and `surveys show` always print JSON objects.
