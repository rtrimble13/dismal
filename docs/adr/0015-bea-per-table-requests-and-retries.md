# 0015. BEA: one request per table, retries, rate-limit mapping

Date: 2026-10-25
Status: accepted

## Context

`GetData` accepts one table per request for the table-based datasets and has
no row or year cap, but BEA enforces per-minute limits (100 requests, 100 MB,
30 errors) and blocks a key for an hour when they are exceeded. Errors are
reported as HTTP 200 with an `Error` object (sometimes nested under
`Results`, sometimes inside a list), and single elements may be serialised as
objects instead of one-element lists. Transient 5xx and connection resets
happen.

## Decision

`BEAClient.fetch` (`dismal.bea.client`) issues one request per `--table`
value (merging series by id and notes by reference) and a single request
otherwise; the CLI warns when it issues more than one. Each HTTP request is
retried up to `BEA_MAX_RETRIES` (default 3) on timeouts, transport errors,
429 and 5xx with exponential back-off (0.5 s doubling, capped at 30 s,
`Retry-After` honoured). `Error` objects are normalised wherever they appear
and mapped by their text: rate limit wording or HTTP 429 to `BEAQuotaError`
(exit 4), key problems to `BEAConfigError` (exit 7), everything else to
`BEAAPIError` (exit 3) with the API's own code and description. Single-object
quirks are normalised to lists.

No client-side throttling is built in: one `dismal bea` invocation rarely
approaches 100 requests, and a limiter would hide the cost from scripts that
loop.

## Consequences

- Partial failures abort the whole call (no partial output), keeping results
  all-or-nothing for scripts.
- Retrying a failing request counts towards the 30-errors limit; retries are
  capped and `0` disables them.
- Error-code mapping relies on BEA's wording for rate limits and key problems;
  unknown wording degrades gracefully to exit 3.
