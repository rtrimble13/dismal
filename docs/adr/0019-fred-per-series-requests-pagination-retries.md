# 0019. FRED: one request per series, pagination, retries, rate-limit mapping

Date: 2026-10-25
Status: accepted

## Context

The observations endpoint takes one series per request and returns at most
100,000 observations per page (`limit`/`offset`). FRED allows 120 requests
per minute per key and answers excess with HTTP 429. Errors are JSON bodies
with `error_code` and `error_message` on HTTP 400 (unknown series, bad
parameters, bad key). Transient 5xx and connection resets happen.

## Decision

`FREDClient.fetch` (`dismal.fred.client`) issues one request per series (two
with `meta`), paginates transparently when a response is longer than one
page, and preserves the caller's order. Unknown series are reported as
messages and omitted rather than failing the whole call, matching how the BLS
source treats missing ids; `--strict` turns them into exit 6. Each HTTP
request is retried up to `FRED_MAX_RETRIES` (default 3) on timeouts,
transport errors, 429 and 5xx with exponential back-off (0.5 s doubling,
capped at 30 s, `Retry-After` honoured). HTTP 429 after retries becomes
`FREDQuotaError` (exit 4); HTTP 400/404 bodies become `FREDNotFoundError`
when the message says something does not exist, `FREDConfigError` when it
names the key, and `FREDAPIError` otherwise; other statuses become
`FREDHTTPError`. The CLI warns when a call will make 50 or more requests.

No client-side throttling is built in: a limiter would hide the cost from
scripts that loop, and the warning plus retry-with-back-off handle the
common case.

## Consequences

- Fetching many series costs many requests; the docs give the budget formula
  and recommend `--latest` and `--series-file` batches.
- Partial results are possible by design (one bad id does not spoil the
  batch); automations use `--strict` when they need all-or-nothing.
- Error mapping relies on FRED's message wording for "does not exist" and
  "api_key"; unknown wording degrades gracefully to exit 3.
