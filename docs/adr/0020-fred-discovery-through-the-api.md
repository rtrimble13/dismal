# 0020. FRED: discovery through search, releases and categories, with cached metadata

Date: 2026-10-25
Status: accepted

## Context

Where BLS publishes flat-file directories and BEA exposes parameter lists,
FRED organises its series by release (the publication they come from) and by
a category tree, and exposes full-text search, per-series metadata, vintage
dates, recent updates and a release calendar. Metadata changes slowly but
every call counts against the per-minute limit.

## Decision

- `dismal fred series search` wraps `/series/search` with the API's own
  ordering, filters (`filter_variable`/`filter_value` for frequency or
  seasonal adjustment) and tag filters; `dismal fred series info` wraps
  `/series`; `dismal fred series vintages` and `dismal fred series updates`
  wrap their endpoints.
- `dismal fred releases` lists `/releases` (cached 7 days under
  `FRED_CACHE_DIR`, `--refresh` to re-fetch, `--query` to fuzzy-filter);
  `releases show`, `releases series` and `releases dates` (the calendar,
  `/releases/dates` over a window of days) are live.
- `dismal fred categories` lists the children of the root (cached 7 days per
  category id); `categories children` and `categories series` descend.
- Series metadata and observations are never cached.

## Consequences

- Complete discovery at one request per query, with the slow-changing lists
  cached for a week.
- The release calendar makes monitoring workflows possible without scraping
  the website.
- Output columns for metadata commands are the same everywhere (`id, title,
  frequency, units, seasonal_adjustment, observation_start, observation_end,
  last_updated, popularity`), so agents learn one schema.
