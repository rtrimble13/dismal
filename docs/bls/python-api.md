# Python API

The CLI is a thin layer over `dismal.bls.BLSClient`; everything the CLI does is
available programmatically.

```python
from dismal.bls import BLSClient, Settings
from dismal.bls.filters import ObservationFilter
from dismal.bls.periods import Frequency, parse_date_spec
from dismal.bls.records import to_records, to_wide

settings = Settings.from_env()            # reads BLS_API_KEY etc.
with BLSClient.from_settings(settings) as client:
    resp = client.fetch(
        ["LNS14000000", "CUUR0000SA0"],
        start_year=2015,
        end_year=2024,
        calculations=True,
    )

print(resp.request_count, resp.messages)   # requests issued, API notes
flt = ObservationFilter(
    start=parse_date_spec("2020-03"),
    end=parse_date_spec("2024-Q2", end=True),
    frequencies=frozenset({Frequency.MONTHLY}),
)
series = flt.apply(resp.series)
records = to_records(series, include_calculations=True)   # list[dict]
wide = to_wide(records)
```

## `BLSClient`

```python
BLSClient(api_key=None, *, base_url=..., timeout=30.0, max_retries=3,
          user_agent=None, transport=None, on_message=None)
BLSClient.from_settings(settings, *, transport=None, on_message=None)
```

| Method | Returns | Notes |
| --- | --- | --- |
| `fetch(series_ids, *, start_year=None, end_year=None, latest=False, catalog=False, calculations=False, annual_average=False, aspects=False)` | `DataResponse` | Splits by series/year limits, merges, sorts chronologically. `start_year`/`end_year` must be given together. |
| `surveys()` | `list[Survey]` | |
| `survey(abbreviation)` | `dict` | Raw API object. |
| `popular(survey=None)` | `list[str]` | |
| `limits` | `Limits` | `REGISTERED_LIMITS` or `UNREGISTERED_LIMITS` depending on the key. |
| `request_count` | `int` | HTTP requests issued so far (includes retries). |
| `close()` / context manager | | |

`transport` accepts any `httpx.BaseTransport`, e.g. `httpx.MockTransport` for
tests. `on_message` receives informational API messages ("No Data Available
for Series ... Year: ...").

## Models (`dismal.bls.models`)

- `DataResponse(series, messages, request_count, response_time_ms)` with
  `.get(series_id)` and `.to_api_dict()`.
- `Series(series_id, data, catalog)` with `.title` and `.merge()`.
- `Observation(year, period, period_name, raw_value, value, footnotes, latest,
  calculations, aspects)` with `.date`, `.end_date`, `.frequency`,
  `.annual_average`, `.period_info`.
- `Survey(abbreviation, name)`.

## Errors (`dismal.bls.errors`)

All derive from `BLSError` and carry `.exit_code` (an `ExitCode` enum) and an
optional `.hint`:

| Exception | Exit code | When |
| --- | --- | --- |
| `BLSConfigError` | 7 | bad configuration |
| `BLSNetworkError` | 5 | no HTTP response (timeout, DNS, reset) after retries |
| `BLSHTTPError` | 3 | HTTP 4xx/5xx or non-JSON body |
| `BLSAPIError` | 3 | `status != REQUEST_SUCCEEDED` |
| `BLSQuotaError` | 4 | daily threshold / HTTP 429 |
| `BLSNoDataError` | 6 | raised by the CLI in `--strict` mode |

## Other modules

| Module | Purpose |
| --- | --- |
| `dismal.bls.periods` | `parse_period`, `parse_date_spec`, `period_in_range`, `Frequency`, `YearMonth` |
| `dismal.bls.filters` | `ObservationFilter` |
| `dismal.bls.records` | `to_records`, `to_wide`, `column_order`, `stringify` |
| `dismal.bls.output` | `write_records`, `records_to_csv/json/jsonl/parquet/table`, `OutputFormat` |
| `dismal.bls.search` | `score_text`, `search_series`, `search_surveys`, `search_rows` |
| `dismal.bls.catalog` | bundled `series_catalog()` and `bundled_surveys()` |
| `dismal.bls.flatfiles` | `fetch_series_file`, `parse_series_file` |
| `dismal.bls.config` | `Settings` |

The public surface is what `dismal.bls.__all__` exports plus the modules above; other
names may change between minor versions.
