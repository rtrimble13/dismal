# 0013. BLS: exhaustive series discovery via BLS flat files

Date: 2026-10-24
Status: accepted

## Context

A curated catalog (ADR 0005) cannot cover the hundreds of thousands of BLS
series. BLS publishes, per survey, a tab-delimited `<xx>.series` file at
`https://download.bls.gov/pub/time.series/<xx>/` listing every series id with
its dimension codes, title (for most surveys) and date coverage. The host
rejects requests without a descriptive `User-Agent`.

## Decision

`dismal bls series list --survey XX` downloads the survey's `.series` file
(with a configurable `User-Agent`, `BLS_USER_AGENT`), caches it for 30 days
under `BLS_CACHE_DIR/flatfiles/`, parses it generically (header row defines
columns; `series_title` used when present, otherwise descriptive columns are
joined), and optionally fuzzy-filters with the same scorer as `dismal bls
search`. HTTP 403 yields a hint about the User-Agent requirement; 404 a hint
to check the abbreviation.

## Consequences

- Complete discovery without quota use, at the cost of one potentially large
  download per survey per month.
- The flat-file host is a separate dependency with its own availability and
  etiquette; the tool identifies itself and caches aggressively.
- Flat files are not the API; schema differences between surveys are exposed
  as-is in the extra columns rather than normalised.
