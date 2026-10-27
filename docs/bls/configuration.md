# Configuration

`dismal bls` is configured entirely through environment variables so it behaves
the same in a terminal, a cron job, a container and a CI runner.
`dismal bls config` shows the effective values.

## Variables

| Variable | Default | Notes |
| --- | --- | --- |
| `BLS_API_KEY` | unset | Registration key from <https://data.bls.gov/registrationEngine/>. Never passed as a flag ([ADR 0003](../adr/0003-api-key-from-environment.md)). Leading/trailing whitespace is stripped. |
| `BLS_FORMAT` | unset | Default output format: `json`, `jsonl`, `csv`, `parquet` or `table`. When unset: `table` if stdout is a terminal, else `json`. |
| `BLS_CACHE_DIR` | `$XDG_CACHE_HOME/dismal/bls` or `~/.cache/dismal/bls` | Cache for the survey list (7 days) and flat files (30 days). Never caches observations. |
| `BLS_TIMEOUT` | `30` | Per-request timeout in seconds (flat-file downloads use at least 120 s). |
| `BLS_MAX_RETRIES` | `3` | Retries for HTTP 429/5xx and transport errors, with exponential back-off (0.5 s, 1 s, 2 s, ... capped at 30 s; `Retry-After` honoured). `0` disables retries. |
| `BLS_USER_AGENT` | `dismal/<version> (+https://github.com/rtrimble13/dismal)` | Sent on every request. `download.bls.gov` returns 403 for anonymous agents; use something like `my-project (me@example.com)`. |
| `BLS_API_BASE_URL` | `https://api.bls.gov/publicAPI/v2` | Point at a proxy or a mock server. |
| `BLS_FLATFILE_BASE_URL` | `https://download.bls.gov/pub/time.series` | Same for flat files. |
| `NO_COLOR` | unset | Any value disables colour in `table` output. |

Invalid numeric values (`BLS_TIMEOUT=fast`) are reported as usage errors (exit 2).

## Request limits

BLS publishes these limits for API v2; the CLI applies them when splitting work:

| | With `BLS_API_KEY` | Without |
| --- | --- | --- |
| Requests per day | 500 | 25 |
| Series per request | 50 | 25 |
| Years per request | 20 | 10 |
| Catalog metadata, calculations, annual averages | yes | no (`catalog` is ignored by the API) |

A `dismal bls data` call with 120 series over 1990-2024 and a key issues
`ceil(120/50) * ceil(35/20) = 3 * 2 = 6` requests. The CLI warns on stderr when
it splits by series. The quota is per key, per day; a `REQUEST_NOT_PROCESSED`
answer mentioning the threshold exits with code 4.

Budget tips for automations:

- Prefer one `dismal bls data` call with many ids over many calls with one id.
- Use `--latest` for monitoring; it is one request regardless of history.
- Keep `--start/--end` to what you need; year windows multiply requests.
- Discovery via `dismal bls search` is offline and free; `dismal bls surveys` without
  `--refresh` and `dismal bls series list` (after the first download) are too.

## Caching

| What | Where | TTL | Refresh |
| --- | --- | --- | --- |
| Survey list | `$BLS_CACHE_DIR/surveys.json` | 7 days (stale copies are still used offline) | `dismal bls surveys --refresh` |
| Flat-file directories | `$BLS_CACHE_DIR/flatfiles/<xx>.series` | 30 days | `dismal bls series list --survey XX --refresh` |

`dismal bls cache info` lists cached files; `dismal bls cache clear` removes them.
Observations are never cached so automations always see fresh data.

## Proxies and TLS

The HTTP layer is `httpx`, which honours `HTTPS_PROXY`/`HTTP_PROXY`/`NO_PROXY`
and `SSL_CERT_FILE`.
