# Python API

The CLI is a thin layer over `dismal.fred.FREDClient`; everything the CLI does is
available programmatically.

```python
from datetime import date

from dismal.fred import FREDClient, Settings
from dismal.fred.records import to_records, to_wide

settings = Settings.from_env()            # reads FRED_API_KEY etc.
with FREDClient.from_settings(settings) as client:
    resp = client.fetch(
        ["UNRATE", "CPIAUCSL"],
        start=date(2015, 1, 1),
        units="pc1",            # percent change from a year ago, computed by the API
        meta=True,              # one extra request per series for title/units/...
    )

print(resp.request_count, resp.messages)   # requests issued, unknown-series notes
records = to_records(resp.series, include_meta=True)   # list[dict]
wide = to_wide(records)
```

## `FREDClient`

```python
FREDClient(api_key=None, *, base_url=..., timeout=30.0, max_retries=3,
           user_agent=None, transport=None, on_message=None)
FREDClient.from_settings(settings, *, transport=None, on_message=None)
```

| Method | Returns | Notes |
| --- | --- | --- |
| `fetch(series_ids, *, start=None, end=None, units=None, frequency=None, aggregation=None, as_of=None, latest=False, meta=False)` | `DataResponse` | One request per series; unknown ids become messages. |
| `observations(series_id, *, start, end, units, frequency, aggregation, realtime_start, realtime_end, sort_order, limit, output_type)` | `(list[Observation], dict)` | One series, paginated; the dict is the response's own metadata (`count`, `units`, ...). |
| `series_info(series_id)` | `SeriesInfo` | Raises `FREDNotFoundError` for unknown ids. |
| `search(text, *, search_type, limit, offset, order_by, sort_order, filter_variable, filter_value, tag_names, exclude_tag_names)` | `(list[SeriesInfo], int)` | Hits and the total count. |
| `vintage_dates(series_id)` | `list[date]` | |
| `updates(limit, offset)` | `list[SeriesInfo]` | |
| `releases()`, `release(id)`, `release_series(id, limit, offset)`, `release_dates(start, end)` | | |
| `category(id)`, `category_children(id)`, `category_series(id, limit, offset)`, `sources()` | | |
| `limits` | `Limits` | 120 requests/minute, 100,000 observations and 1,000 search results per request. |
| `request_count` | `int` | HTTP requests issued so far (includes retries). |
| `close()` / context manager | | |

`transport` accepts any `httpx.BaseTransport`, e.g. `httpx.MockTransport` for
tests. `on_message` receives informational messages ("series X does not
exist"). The key is sent as the `api_key` query parameter and never logged or
echoed back.

## Models (`dismal.fred.models`)

- `DataResponse(series, messages, request_count, params)` with
  `.get(series_id)` and `.to_api_dict()`.
- `Series(series_id, data, info)` with `.title`, `.merge()`, `.sort()` and
  `.latest`.
- `Observation(date, raw_value, value, realtime_start, realtime_end)`.
- `SeriesInfo(id, title, observation_start, observation_end, frequency,
  frequency_short, units, units_short, seasonal_adjustment,
  seasonal_adjustment_short, last_updated, popularity, group_popularity,
  notes, ...)` with `.to_record()`.
- `Release`, `ReleaseDate`, `Category`, `Source`.

## Errors (`dismal.fred.errors`)

All derive from `FREDError` and carry `.exit_code` (an `ExitCode` enum) and an
optional `.hint`:

| Exception | Exit code | When |
| --- | --- | --- |
| `FREDConfigError` | 7 | no key, or the API rejected the key |
| `FREDNetworkError` | 5 | no HTTP response (timeout, DNS, reset) after retries |
| `FREDHTTPError` | 3 | unexpected HTTP status or non-JSON body |
| `FREDAPIError` | 3 | the API rejected the request (HTTP 400 with `error_message`) |
| `FREDNotFoundError` | 3 | a series, release or category does not exist (subclass of `FREDAPIError`) |
| `FREDQuotaError` | 4 | HTTP 429, after retries |
| `FREDNoDataError` | 6 | raised by the CLI in `--strict` mode |

## Other modules

| Module | Purpose |
| --- | --- |
| `dismal.fred.periods` | `parse_date_spec`, `parse_iso_date`, `Frequency`, `normalise_frequency/units/aggregation`, the `UNITS` and `FREQUENCY_CODES` vocabularies |
| `dismal.fred.records` | `to_records`, `to_wide`, `column_order`, `stringify` |
| `dismal.fred.output` | `write_records`, `records_to_csv/json/jsonl/parquet/table`, `OutputFormat` |
| `dismal.fred.search` | `score_text`, `phrase_key`, `search_series`, `search_rows` |
| `dismal.fred.catalog` | bundled `series_catalog()`, `catalog_entry()` |
| `dismal.fred.config` | `Settings` |

The public surface is what `dismal.fred.__all__` exports plus the modules above; other
names may change between minor versions.
