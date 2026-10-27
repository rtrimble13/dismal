# 0012. BLS: transparent chunking and retries in the client

Date: 2026-10-24
Status: accepted

## Context

BLS API limits: 50 series and 20 years per request with a key (25/10
without), 500 requests per day. Transient 5xx and connection resets happen.
Automations should not have to implement batching or back-off themselves.

## Decision

`BLSClient.fetch` (`dismal.bls.client`) splits ids into chunks and year
ranges into windows according to the limits implied by the presence of a key,
issues `chunks x windows` POST requests, merges series by id (de-duplicating
observations by year+period), preserves the caller's id order and sorts
observations chronologically. Each HTTP request is retried up to
`BLS_MAX_RETRIES` (default 3) on timeouts, transport errors, 429 and 5xx with
exponential back-off (0.5 s doubling, capped at 30 s, `Retry-After`
honoured). API-level failures are mapped to `BLSAPIError`, quota problems
(`REQUEST_NOT_PROCESSED`, "threshold", HTTP 429) to `BLSQuotaError`.

The CLI warns when a call is split by series so users notice the quota cost.

## Consequences

- One `dismal bls` call can consume several daily requests;
  `docs/bls/configuration.md` documents the formula.
- Partial failures abort the whole call (no partial output), keeping results
  all-or-nothing for scripts.
- Retries are a client concern; tests stub `sleep` to keep the suite fast.
