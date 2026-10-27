# Python API

The CLI is a thin layer over `dismal.bea.BEAClient`; everything the CLI does is
available programmatically.

```python
from dismal.bea import BEAClient, Settings
from dismal.bea.filters import ObservationFilter
from dismal.bea.periods import Frequency, parse_date_spec
from dismal.bea.records import to_records, to_wide

settings = Settings.from_env()            # reads BEA_API_KEY etc.
with BEAClient.from_settings(settings) as client:
    resp = client.fetch(
        "NIPA",
        {"Frequency": "Q", "Year": "2019,2020,2021,2022,2023,2024"},
        table_param="TableName",
        tables=["T10101", "T10105"],      # one request per table, merged
    )

print(resp.request_count, [n.ref for n in resp.notes])
flt = ObservationFilter(
    start=parse_date_spec("2020-03"),
    end=parse_date_spec("2024-Q2", end=True),
    frequencies=frozenset({Frequency.QUARTERLY}),
)
series = flt.apply(resp.series)
records = to_records(series, dataset="NIPA", include_notes=True, note_text=resp.note_text)
wide = to_wide(records)
```

## `BEAClient`

```python
BEAClient(api_key=None, *, base_url=..., timeout=60.0, max_retries=3,
          user_agent=None, transport=None)
BEAClient.from_settings(settings, *, transport=None)
```

| Method | Returns | Notes |
| --- | --- | --- |
| `datasets()` | `list[Dataset]` | `GetDataSetList` |
| `parameters(dataset)` | `list[Parameter]` | `GetParameterList` |
| `parameter_values(dataset, parameter)` | `list[dict]` | `GetParameterValues`; raw rows (`Key`/`Desc`, `TableName`/`Description`, ...) |
| `parameter_values_filtered(dataset, target, filters)` | `list[dict]` | `GetParameterValuesFiltered` |
| `get_data(dataset, params)` | `DataResponse` | One `GetData` request, rows grouped into series and sorted chronologically. |
| `fetch(dataset, params, *, table_param=None, tables=None)` | `DataResponse` | One request per table, merged by series id. |
| `limits` | `Limits` | 100 requests / 100 MB / 30 errors per minute, 60-minute block. |
| `request_count` | `int` | HTTP requests issued so far (includes retries). |
| `close()` / context manager | | |

`transport` accepts any `httpx.BaseTransport`, e.g. `httpx.MockTransport` for
tests. The key is sent as the `UserID` query parameter and never logged or
echoed back.

## Models (`dismal.bea.models`)

- `DataResponse(dataset, series, notes, dimensions, params, statistic,
  production_time, request_count)` with `.get(series_id)`, `.note_text(refs)`,
  `.rows()` and `.to_api_dict()`.
- `Series(series_id, title, data, attributes)` with `.merge()`, `.sort()` and
  `.latest`. `attributes` holds the snake_cased dimension columns.
- `Observation(period, raw_value, value, unit, unit_mult, note_ref, raw)` with
  `.date`, `.end_date`, `.year`, `.frequency`, `.period_info`.
- `Dataset(name, description)`, `Parameter(name, data_type, description,
  required, default, multiple, all_value)`, `Note(ref, text)`.
- `group_rows(dataset, rows)` turns raw `Data` rows into series using the
  per-dataset rules in `dismal.bea.datasets`; `parse_value` and `snake_case` are the
  helpers behind it.

## Errors (`dismal.bea.errors`)

All derive from `BEAError` and carry `.exit_code` (an `ExitCode` enum) and an
optional `.hint`:

| Exception | Exit code | When |
| --- | --- | --- |
| `BEAConfigError` | 7 | no key, or the API rejected the key |
| `BEANetworkError` | 5 | no HTTP response (timeout, DNS, reset) after retries |
| `BEAHTTPError` | 3 | HTTP 4xx/5xx or non-JSON body |
| `BEAAPIError` | 3 | the API returned an `Error` object (`.code`, `.description`) |
| `BEAQuotaError` | 4 | rate limit (error text or HTTP 429) |
| `BEANoDataError` | 6 | raised by the CLI in `--strict` mode |

## Other modules

| Module | Purpose |
| --- | --- |
| `dismal.bea.periods` | `parse_period`, `period_from_row`, `parse_date_spec`, `period_in_range`, `Frequency`, `YearMonth` |
| `dismal.bea.datasets` | `DatasetInfo`, `dataset_info`, `canonical_name`: per-dataset parameters, series keys, titles |
| `dismal.bea.filters` | `ObservationFilter` |
| `dismal.bea.records` | `to_records`, `to_wide`, `column_order`, `stringify` |
| `dismal.bea.output` | `write_records`, `records_to_csv/json/jsonl/parquet/table`, `OutputFormat` |
| `dismal.bea.search` | `score_text`, `search_tables`, `search_datasets`, `search_rows` |
| `dismal.bea.catalog` | bundled `table_catalog()` and `bundled_datasets()` |
| `dismal.bea.config` | `Settings` |

The public surface is what `dismal.bea.__all__` exports plus the modules above;
other names may change between minor versions. `dismal.__version__` is the
package version.
