# Python API

The CLI is a thin layer over three typed clients; everything it does is
available programmatically from one package.

```bash
pip install git+https://github.com/rtrimble13/dismal
```

```python
import dismal
from dismal.bls import BLSClient
from dismal.bea import BEAClient
from dismal.fred import FREDClient

print(dismal.__version__)   # the package version, same for every source
print(dismal.SOURCES)       # ("bls", "bea", "fred")
```

Each source is a subpackage with the same shape (`client`, `config`,
`models`, `periods`, `records`, `search`, `catalog`, `errors`); the module
paths of the former stand-alone packages map one to one (`bls.client` ->
`dismal.bls.client`, `fred.models` -> `dismal.fred.models`). The per-source
pages document every method, model and error:

- [bls/python-api.md](bls/python-api.md) - `BLSClient`
- [bea/python-api.md](bea/python-api.md) - `BEAClient`
- [fred/python-api.md](fred/python-api.md) - `FREDClient`

## Shared pieces (`dismal.core`)

| Module | Contents |
| --- | --- |
| `dismal.core.errors` | `DismalError`, the base class of every source's exceptions (`BLSError`, `BEAError`, `FREDError` and their subclasses); each carries `.exit_code` and an optional `.hint`. `ExitCode` is the `IntEnum` of CLI exit codes (`OK`, `ERROR`, `USAGE`, `API`, `QUOTA`, `NETWORK`, `NO_DATA`, `CONFIG`). `PeriodError` for unparsable dates. |
| `dismal.core.output` | `OutputFormat` (`json`, `jsonl`, `csv`, `parquet`, `table`), `write_records`, `records_to_json/jsonl/csv/parquet/table`, `write_json`. The per-source `output` modules re-export these. |
| `dismal.core.records` | `Record` (a `dict[str, Any]`), `jsonable`, `stringify`, `first_seen_columns`. Every source's `to_records` returns a `list[Record]`. |
| `dismal.core.config` | `BaseSettings`, `EnvNames`, `settings_kwargs_from_env`, `default_cache_dir(source)`, `default_user_agent()`. Each source's `Settings` extends `BaseSettings`. |
| `dismal.core.cache` | `FileCache`, the metadata cache every source uses. |
| `dismal.core.cli` | The CLI plumbing (`State`, `error_handler`, `emit_records`, ...); not part of the public API. |

Because every error derives from `DismalError`, one handler covers any
source:

```python
from dismal.core.errors import DismalError, ExitCode

try:
    ...
except DismalError as exc:
    print(exc.message, exc.hint, int(exc.exit_code))
    if exc.exit_code is ExitCode.QUOTA:
        ...
```

Records from any source serialise the same way:

```python
from dismal.core.output import OutputFormat, write_records

write_records(records, OutputFormat.CSV, "out.csv", columns=list(records[0]))
```

## `dismal.bls`

```python
from dismal.bls import BLSClient, Settings
from dismal.bls.records import to_records

settings = Settings.from_env()            # reads BLS_API_KEY etc.
with BLSClient.from_settings(settings) as client:
    resp = client.fetch(["LNS14000000", "CUUR0000SA0"], start_year=2015, end_year=2024)
records = to_records(resp.series)         # list[dict]: series_id, date, year, period, value, ...
```

Filters, calculations, the wide pivot and the survey and flat-file helpers:
[bls/python-api.md](bls/python-api.md).

## `dismal.bea`

```python
from dismal.bea import BEAClient, Settings
from dismal.bea.records import to_records

settings = Settings.from_env()            # reads BEA_API_KEY etc.
with BEAClient.from_settings(settings) as client:
    resp = client.fetch(
        "NIPA",
        {"Frequency": "Q", "Year": "2023,2024"},
        table_param="TableName",
        tables=["T10101"],
    )
records = to_records(resp.series, dataset="NIPA")   # dataset, series_id, series_title, period, value, ...
```

Datasets, parameters, parameter values, notes and dimensions:
[bea/python-api.md](bea/python-api.md).

## `dismal.fred`

```python
from datetime import date

from dismal.fred import FREDClient, Settings
from dismal.fred.records import to_records

settings = Settings.from_env()            # reads FRED_API_KEY etc.
with FREDClient.from_settings(settings) as client:
    resp = client.fetch(["UNRATE", "CPIAUCSL"], start=date(2015, 1, 1), units="pc1")
records = to_records(resp.series)         # list[dict]: series_id, date, value
```

Search, series metadata, vintages, releases and categories:
[fred/python-api.md](fred/python-api.md).

## Testing without the network

Every client accepts `transport=` (any `httpx.BaseTransport`, e.g.
`httpx.MockTransport`), so tests can serve canned responses; the repository's
own suites do this with fake APIs (see
[development.md](development.md#testing)).

## Stability

The public surface is what `dismal.bls.__all__`, `dismal.bea.__all__` and
`dismal.fred.__all__` export plus the modules listed on the per-source pages
and the `dismal.core` modules above; other names may change between minor
versions. The exception class names are unchanged from the stand-alone
packages (`BLSError`, `BEAAPIError`, `FREDNotFoundError`, ...).
