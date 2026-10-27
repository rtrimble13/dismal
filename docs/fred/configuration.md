# Configuration

`dismal fred` is configured entirely through environment variables so it behaves the
same in a terminal, a cron job, a container and a CI runner. `dismal fred config`
shows the effective values.

## Variables

| Variable | Default | Notes |
| --- | --- | --- |
| `FRED_API_KEY` | unset | The 32-character key from <https://fred.stlouisfed.org/docs/api/api_key.html>. Required for every live request; never passed as a flag ([ADR 0003](../adr/0003-api-key-from-environment.md)). Leading/trailing whitespace is stripped. |
| `FRED_FORMAT` | unset | Default output format: `json`, `jsonl`, `csv`, `parquet` or `table`. When unset: `table` if stdout is a terminal, else `json`. |
| `FRED_CACHE_DIR` | `$XDG_CACHE_HOME/dismal/fred` or `~/.cache/dismal/fred` | Cache for the release list and the category tree (7 days). Never caches observations. |
| `FRED_TIMEOUT` | `30` | Per-request timeout in seconds. |
| `FRED_MAX_RETRIES` | `3` | Retries for HTTP 429/5xx and transport errors, with exponential back-off (0.5 s, 1 s, 2 s, ... capped at 30 s; `Retry-After` honoured). `0` disables retries. |
| `FRED_USER_AGENT` | `dismal/<version> (+https://github.com/rtrimble13/dismal)` | Sent on every request. |
| `FRED_API_BASE_URL` | `https://api.stlouisfed.org/fred` | Point at a proxy or a mock server. |
| `NO_COLOR` | unset | Any value disables colour in `table` output. |

Invalid numeric values (`FRED_TIMEOUT=fast`) are reported as usage errors (exit 2).

## Request limits

| Limit | Value |
| --- | --- |
| Requests per minute, per key | 120 |
| Observations per request | 100,000 (the CLI paginates) |
| Search results per request | 1,000 |

There is no daily quota. Exceeding the per-minute limit returns HTTP 429,
which the CLI retries with back-off and then reports as exit code 4. One
`dismal fred data` call issues one request per series (two with `--meta`); the CLI
warns on stderr when a call will make 50 or more. `dismal fred config` prints the
limits.

Budget tips for automations:

- Prefer `--latest` for monitoring: one small request per series regardless
  of history.
- Use `--start/--end`: the API filters server-side, so you transfer only what
  you need. A daily series back to 1962 is about 16,000 rows.
- Discovery via `dismal fred search` is offline and free; `dismal fred releases` and `dismal fred
  categories` are cached for a week after the first call; `dismal fred series search`
  is one request per query.
- Spread large batches over time: 120 series per minute is the ceiling.

## Caching

| What | Where | TTL | Refresh |
| --- | --- | --- | --- |
| Release list | `$FRED_CACHE_DIR/releases.json` | 7 days | `dismal fred releases --refresh` |
| Category children | `$FRED_CACHE_DIR/categories/<id>.json` | 7 days | `dismal fred categories [children ID] --refresh` |

`dismal fred cache info` lists cached files; `dismal fred cache clear` removes them.
Observations and series metadata are never cached so automations always see
fresh data.

## Proxies and TLS

The HTTP layer is `httpx`, which honours `HTTPS_PROXY`/`HTTP_PROXY`/`NO_PROXY`
and `SSL_CERT_FILE`.
