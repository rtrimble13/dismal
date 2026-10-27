# Output formats and schemas

Every record-producing command supports `--format json|jsonl|csv|parquet|table`
and `--output PATH`. The same records feed all formats; only the encoding
changes. `--columns` projects and orders columns identically in every format.

## Default format

| stdout is | default |
| --- | --- |
| a terminal | `table` |
| a pipe or file | `json` |

Override with `BEA_FORMAT` or `--format`. Automations should pass `--format`
explicitly.

## Long layout (default for `dismal bea data`)

One row per (series, period). Core columns, always first and in this order:

| Column | Type (JSON / Parquet) | Description |
| --- | --- | --- |
| `dataset` | string | Dataset name as BEA spells it (`NIPA`, `Regional`) |
| `series_id` | string | BEA's series code when the dataset has one (`A191RL` for NIPA/NIUnderlyingDetail/FixedAssets, `TimeSeriesId` for ITA/IIP/IntlServ*); otherwise the dimension values joined with `:` (`SAINC1-1:06000` for Regional `Code:GeoFips`, `1:11` for GDPbyIndustry `TableID:Industry`, `TableID:RowCode:ColCode` for InputOutput, `SeriesID:RowCode:ColumnCode` for MNE) |
| `series_title` | string | `LineDescription`, `GeoName`, `IndustrYDescription`, `TimeSeriesDescription`, `RowDescr / ColDescr` or `SeriesName / Row / Column`, by dataset |
| `date` | ISO date string / `date32` | First day of the period (`2024-04-01` for 2024Q2, `2024-01-01` for annual) |
| `year` | integer / `int64` | Calendar year |
| `period` | string | BEA time period (`2024`, `2024Q2`, `2024M03`); `Year`/`Quarter` columns are normalised to this form |
| `frequency` | string | `annual`, `quarterly`, `monthly` |
| `value` | number or null / `double` | `DataValue` with thousands separators removed; `null` for `(D)`, `(NA)`, `(*)`, `n.a.`, `---` and blanks |
| `unit` | string or null | `CL_UNIT` (`Level`, `Percent change, annual rate`, `Thousands of dollars`, ...) |
| `unit_mult` | integer or null / `int64` | `UNIT_MULT`: the power of ten the value is expressed in (`6` = millions) |
| `note_ref` | string | `NoteRef`: comma-separated references into the table notes |

Optional and dataset-specific columns, appended in this order:

| Source | Columns |
| --- | --- |
| `--notes` | `notes`: the text of the notes referenced by `note_ref`, joined with `; ` |
| NIPA, NIUnderlyingDetail, FixedAssets | `table_name`, `line_number` (integer), `metric_name` |
| Regional | `code` (`TableName-LineCode`), `geo_fips` |
| GDPbyIndustry, UnderlyingGDPbyIndustry | `frequency_code` (the API's `Frequency`), `table_id`, `industry` |
| ITA, IIP, IntlServTrade, IntlServSTA | `frequency_code`, `indicator`, `area_or_country`, `type_of_investment`, `component`, ... |
| InputOutput | `table_id`, `row_code`, `row_type`, `col_code`, `col_type` |
| MNE | `api_series_id`, `row_code`, `column_code`, `table_scale`, ... |
| other / future datasets | every column of the row that is not consumed above, in snake_case |

Column names are the API's names converted to snake_case (`TableID` ->
`table_id`, `METRIC_NAME` -> `metric_name`, `IndustrYDescription` ->
`industry_description`). A dataset column that would collide with a core
column is prefixed `api_` (MNE's `SeriesID` -> `api_series_id`). Columns whose
value is the series id itself (`SeriesCode`, `TimeSeriesId`) and the column
used for `series_title` are not repeated.

Rows are sorted chronologically per series (an annual value sorts after the
quarters/months of its year); `--descending` reverses. Series appear in the
order the API returned them.

## Wide layout (`--layout wide`)

One row per period, one column per series id:

```
date, year, period, <SERIES_ID_1>, <SERIES_ID_2>, ...
```

Missing values are `null`/empty. Mixing frequencies produces rows for every
distinct period. Dimension and note columns are not available in wide layout;
use the long layout (or `dismal bea tables show`) to map ids to titles.

## Formats

### `json`

A pretty-printed array of objects. Dates are ISO strings.

```json
[
  {
    "dataset": "NIPA",
    "series_id": "A191RL",
    "series_title": "Gross domestic product",
    "date": "2024-07-01",
    "year": 2024,
    "period": "2024Q3",
    "frequency": "quarterly",
    "value": 3.1,
    "unit": "Percent change, annual rate",
    "unit_mult": 0,
    "note_ref": "T10101",
    "table_name": "T10101",
    "line_number": 1,
    "metric_name": "Fisher Quantity Index"
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
file (`dismal bea data ... -f parquet > x.parquet`).

### `table`

A box-drawn table (rich). Colour only when stdout is a terminal and `NO_COLOR`
is unset. When piped, the table is rendered at its natural width with no ANSI
escapes. Intended for people, not parsers.

## `--raw`

Bypasses record flattening and prints the API's own shape, merged across
tables, after client-side filters, and without the `UserID`:

```json
{
  "BEAAPI": {
    "Request": {"RequestParam": [{"ParameterName": "METHOD", "ParameterValue": "GETDATA"}, {"ParameterName": "DATASETNAME", "ParameterValue": "NIPA"}, {"ParameterName": "FREQUENCY", "ParameterValue": "Q"}, {"ParameterName": "YEAR", "ParameterValue": "2024"}, {"ParameterName": "TABLENAME", "ParameterValue": "T10101"}]},
    "Results": {
      "Statistic": "NIPA Table",
      "UTCProductionTime": "2026-10-25T12:00:00.000",
      "Dimensions": [{"Ordinal": "1", "Name": "TableName", "DataType": "string", "IsValue": "0"}],
      "Data": [{"TableName": "T10101", "SeriesCode": "A191RL", "LineNumber": "1", "LineDescription": "Gross domestic product", "TimePeriod": "2024Q3", "METRIC_NAME": "Fisher Quantity Index", "CL_UNIT": "Percent change, annual rate", "UNIT_MULT": "0", "DataValue": "3.1", "NoteRef": "T10101"}],
      "Notes": [{"NoteRef": "T10101", "NoteText": "Table 1.1.1. Percent Change From Preceding Period in Real Gross Domestic Product - LastRevised: ..."}]
    }
  }
}
```

## Other commands

| Command | Columns |
| --- | --- |
| `search` | `kind, id, title, dataset, score, frequency, units, command` |
| `datasets` | `dataset, description` (+ `score` with `--query`) |
| `datasets show` | `parameter, required, multiple, all_value, default, type, description` |
| `tables list` | `table, title` (+ `score` with `--query`), then extra API columns |
| `tables show` | `series_id, series_title`, dimension columns, `unit, unit_mult, frequencies, latest_period, latest_value` (Regional: `line_code, description`) |
| `values` | `key, description` (+ `score` with `--query`), then extra API columns |
| `cache info` | `file, bytes` |

`config` and `doctor` always print JSON objects.
