# 0011. BLS: fetch whole years, filter dates and frequencies client-side

Date: 2026-10-24
Status: accepted

## Context

The BLS API accepts only `startyear`/`endyear`. Users ask for month, quarter
or half-year bounds, specific frequencies, and sometimes only annual averages.

## Decision

`dismal bls data` translates `--start/--end` to the covering year range for
the API call, then filters observations locally:

- Bounds are inclusive `YearMonth` values. A period is kept when it
  **overlaps** the range (its last month >= start and first month <= end), so a
  quarterly or annual value is kept whenever any of its months is in range.
- `--frequency` filters on the decoded period code. Annual-average codes
  (`M13`, `Q05`, `S03`) have frequency `annual` and `annual_average=true`.
- `--latest` is passed to the API (it changes the response) and disables
  date flags.
- `--years N` is a convenience for `--start (this_year-N+1) --end this_year`.

## Consequences

- Slightly more data is transferred than strictly needed (whole years); the
  simplicity and predictability outweigh this.
- The overlap rule is documented and tested; `--start 2020-06` keeping the
  2020 annual value is intended, not a bug.
- `--raw` output is filtered too, so it is "API shape" but not "API bytes".
