# Configuration

`dismal` is configured entirely through environment variables so it behaves
the same in a terminal, a cron job, a container and a CI runner. Each source
reads its own prefixed set (`BLS_*`, `BEA_*`, `FRED_*`); the names are the
same as the stand-alone tools used. `dismal <source> config` shows the
effective values of one source and `dismal config` those of all three.

## Shared rules

- **API keys come only from the environment** (`BLS_API_KEY`, `BEA_API_KEY`,
  `FRED_API_KEY`). There is no flag, so a key cannot leak into shell history
  or process listings ([ADR 0003](adr/0003-api-key-from-environment.md)).
  Leading and trailing whitespace is stripped. BLS works without a key at
  lower limits; BEA and FRED require one (exit 7 otherwise).
- **One `NO_COLOR`** for every source: any value disables colour in `table`
  output.
- **One cache tree**: `$XDG_CACHE_HOME/dismal/<source>`, or
  `~/.cache/dismal/<source>` when `XDG_CACHE_HOME` is unset, unless
  `<SOURCE>_CACHE_DIR` points elsewhere. Only metadata is cached (survey,
  dataset, parameter, release and category lists, BLS flat files); observations
  never are, so automations always see fresh data. `dismal cache info|clear`
  acts on every source at once.
- **One User-Agent default**: `dismal/<version> (+https://github.com/rtrimble13/dismal)`,
  overridable per source with `<SOURCE>_USER_AGENT`.
- **Invalid numeric values** (`BLS_TIMEOUT=fast`) are usage errors (exit 2),
  reported when the source runs and also by `dismal config`/`dismal doctor`.
- **Proxies and TLS**: the HTTP layer is `httpx`, which honours
  `HTTPS_PROXY`/`HTTP_PROXY`/`NO_PROXY` and `SSL_CERT_FILE` for every source.
- **Default output format** per source: `<SOURCE>_FORMAT`, else `table` when
  stdout is a terminal and `json` otherwise. Automations should pass
  `--format` explicitly.

## `bls`

Full details, request limits and caching:
[bls/configuration.md](bls/configuration.md).

| Variable | Default | Notes |
| --- | --- | --- |
| `BLS_API_KEY` | unset | Registration key from <https://data.bls.gov/registrationEngine/>. Without it: 25 requests/day, 25 series and 10 years per request, no catalog metadata or calculations. |
| `BLS_FORMAT` | unset | Default output format: `json`, `jsonl`, `csv`, `parquet` or `table`. |
| `BLS_CACHE_DIR` | `~/.cache/dismal/bls` | Survey list (7 days) and flat files (30 days). |
| `BLS_TIMEOUT` | `30` | Per-request timeout in seconds (flat-file downloads use at least 120 s). |
| `BLS_MAX_RETRIES` | `3` | Retries for HTTP 429/5xx and transport errors with exponential back-off; `0` disables. |
| `BLS_USER_AGENT` | `dismal/<version> (+https://github.com/rtrimble13/dismal)` | `download.bls.gov` returns 403 for anonymous agents; use something like `my-project (me@example.com)`. |
| `BLS_API_BASE_URL` | `https://api.bls.gov/publicAPI/v2` | Point at a proxy or a mock server. |
| `BLS_FLATFILE_BASE_URL` | `https://download.bls.gov/pub/time.series` | Same for flat files. |

## `bea`

Full details, request limits and caching:
[bea/configuration.md](bea/configuration.md).

| Variable | Default | Notes |
| --- | --- | --- |
| `BEA_API_KEY` | unset | The 36-character UserID from <https://apps.bea.gov/API/signup/>. Required for every live request. |
| `BEA_FORMAT` | unset | Default output format: `json`, `jsonl`, `csv`, `parquet` or `table`. |
| `BEA_CACHE_DIR` | `~/.cache/dismal/bea` | Dataset list, parameter lists and parameter values (7 days). |
| `BEA_TIMEOUT` | `60` | Per-request timeout in seconds. Large requests (all years of a county table) can take a while. |
| `BEA_MAX_RETRIES` | `3` | Retries for HTTP 429/5xx and transport errors with exponential back-off; `0` disables. |
| `BEA_USER_AGENT` | `dismal/<version> (+https://github.com/rtrimble13/dismal)` | Sent on every request. |
| `BEA_API_BASE_URL` | `https://apps.bea.gov/api/data` | Point at a proxy or a mock server. |

## `fred`

Full details, request limits and caching:
[fred/configuration.md](fred/configuration.md).

| Variable | Default | Notes |
| --- | --- | --- |
| `FRED_API_KEY` | unset | The 32-character key from <https://fred.stlouisfed.org/docs/api/api_key.html>. Required for every live request. |
| `FRED_FORMAT` | unset | Default output format: `json`, `jsonl`, `csv`, `parquet` or `table`. |
| `FRED_CACHE_DIR` | `~/.cache/dismal/fred` | Release list and category tree (7 days). |
| `FRED_TIMEOUT` | `30` | Per-request timeout in seconds. |
| `FRED_MAX_RETRIES` | `3` | Retries for HTTP 429/5xx and transport errors with exponential back-off; `0` disables. |
| `FRED_USER_AGENT` | `dismal/<version> (+https://github.com/rtrimble13/dismal)` | Sent on every request. |
| `FRED_API_BASE_URL` | `https://api.stlouisfed.org/fred` | Point at a proxy or a mock server. |

## Checking the configuration

```bash
dismal config                 # every source, keys masked
dismal bea config | jq .limits
dismal doctor                 # adds one live request per source; exit 0 = all healthy
```

`dismal doctor` reports `"healthy": false` and exits with the first unhealthy
source's code: 7 when the BEA or FRED key is missing or rejected, 5 when an
API cannot be reached. A missing BLS key is noted but not unhealthy.
