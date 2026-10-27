# Configuration

`dismal bea` is configured entirely through environment variables so it behaves
the same in a terminal, a cron job, a container and a CI runner. `dismal bea config`
shows the effective values (`dismal config` shows every source).

## Variables

| Variable | Default | Notes |
| --- | --- | --- |
| `BEA_API_KEY` | unset | The 36-character UserID from <https://apps.bea.gov/API/signup/>. Required for every live request; never passed as a flag ([ADR 0003](../adr/0003-api-key-from-environment.md)). Leading/trailing whitespace is stripped. |
| `BEA_FORMAT` | unset | Default output format: `json`, `jsonl`, `csv`, `parquet` or `table`. When unset: `table` if stdout is a terminal, else `json`. |
| `BEA_CACHE_DIR` | `$XDG_CACHE_HOME/dismal/bea` or `~/.cache/dismal/bea` | Cache for the dataset list, parameter lists and parameter values (7 days). Never caches observations. |
| `BEA_TIMEOUT` | `60` | Per-request timeout in seconds. Large requests (all years of a county table) can take a while. |
| `BEA_MAX_RETRIES` | `3` | Retries for HTTP 429/5xx and transport errors, with exponential back-off (0.5 s, 1 s, 2 s, ... capped at 30 s; `Retry-After` honoured). `0` disables retries. |
| `BEA_USER_AGENT` | `dismal/<version> (+https://github.com/rtrimble13/dismal)` | Sent on every request. |
| `BEA_API_BASE_URL` | `https://apps.bea.gov/api/data` | Point at a proxy or a mock server. |
| `NO_COLOR` | unset | Any value disables colour in `table` output. |

Invalid numeric values (`BEA_TIMEOUT=fast`) are reported as usage errors (exit 2).

## Request limits

BEA publishes these limits per key; exceeding any of them blocks the key for
one hour:

| Limit | Value |
| --- | --- |
| Requests per minute | 100 |
| Data volume per minute | 100 MB |
| Errors per minute | 30 |

There is no per-request cap on rows or years, and no daily quota. A blocked
key answers with an error the CLI maps to exit code 4; wait an hour before
retrying. `dismal bea config` prints the limits.

One `dismal bea data` call issues one request per table (`--table` is repeatable);
everything else is a single request. The CLI warns on stderr when it issues
more than one.

Budget tips for automations:

- Ask for the years you need (`--years`, `--start/--end`); `Year=ALL` on a
  county-level Regional table is tens of MB.
- Use `--latest` for monitoring; it requests three years and keeps one row per
  series.
- Discovery via `dismal bea search` is offline and free; `dismal bea datasets`, `dismal bea tables
  list` and `dismal bea values` are cached for a week after the first call.
- Keep requests that are likely to fail (guessing parameters) to a minimum:
  30 errors in a minute also trigger the block.

## Caching

| What | Where | TTL | Refresh |
| --- | --- | --- | --- |
| Dataset list | `$BEA_CACHE_DIR/datasets.json` | used whenever present | `dismal bea datasets --refresh` |
| Parameter lists | `$BEA_CACHE_DIR/params/<DATASET>.json` | 7 days | `dismal bea datasets show X --refresh` |
| Parameter values | `$BEA_CACHE_DIR/values/<DATASET>.<PARAMETER>[__filters].json` | 7 days | `dismal bea tables list X --refresh`, `dismal bea values X P --refresh` |

`dismal bea cache info` lists cached files; `dismal bea cache clear` removes them.
Observations are never cached so automations always see fresh data.

## Proxies and TLS

The HTTP layer is `httpx`, which honours `HTTPS_PROXY`/`HTTP_PROXY`/`NO_PROXY`
and `SSL_CERT_FILE`.
