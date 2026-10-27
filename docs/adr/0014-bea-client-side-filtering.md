# 0014. BEA: request whole years, filter sub-annual bounds and `--latest` client-side

Date: 2026-10-25
Status: accepted

## Context

The BEA API's only time filter is `Year` (a comma list, the dataset's "all
years" value - `X` for NIPA-style datasets, `ALL` elsewhere - and
`LAST5`/`LAST10` for some datasets). Users ask for month or quarter bounds,
specific frequencies, and "the latest value". The API has no "latest" flag at
all.

## Decision

`dismal bea data` translates `--start/--end` to the covering list of years
for the API call, then filters observations locally, exactly as the BLS
source does (ADR 0011):

- Bounds are inclusive `YearMonth` values; a period is kept when it
  **overlaps** the range.
- `--frequency` is sent as the `Frequency` parameter for datasets that accept
  one (so the server does the work) and additionally applied locally; for
  datasets without the parameter it is a local filter only.
- `--latest` requests the last three calendar years and keeps the newest
  observation of each series. Three years covers the publication lag of every
  dataset at small cost; it is documented as a heuristic.
- With no date flag the last three calendar years are requested (the same
  default the BLS source inherits from the BLS API). `Year=ALL`/`Year=X` and
  `Year=LAST5` pass through for users who want the API's semantics.

## Consequences

- Slightly more data is transferred than strictly needed; simplicity and
  predictability outweigh this.
- `--latest` is not "the newest value BEA has ever published" but "the newest
  in the last three years", which is the same thing for every regularly
  updated table.
- `--raw` output is filtered too, so it is "API shape" but not "API bytes".
