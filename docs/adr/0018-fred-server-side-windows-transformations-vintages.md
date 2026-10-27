# 0018. FRED: date windows, transformations, aggregation and vintages are the API's job

Date: 2026-10-25
Status: accepted

## Context

The BLS and BEA sources fetch whole years and filter client-side because
their APIs only understand years (ADR 0011, ADR 0014). The FRED observations
endpoint accepts exact `observation_start`/`observation_end` dates, computes
transformations (`units`: changes, percent changes, logs), aggregates to lower
frequencies (`frequency`, `aggregation_method`) and serves any past vintage
(`realtime_start`/`realtime_end`). Re-implementing those locally would
transfer more data and risk disagreeing with what FRED's own site shows.

## Decision

Delegate to the API and keep the client thin:

- `--start/--end` accept the same friendly specs as the other sources
  (`2020-03`, `2024-Q2`, `2024-H1`) and are translated to the first/last day
  they cover, then sent as `observation_start`/`observation_end`. No
  client-side date filtering.
- `--units`, `--frequency` and `--aggregation` map one-to-one to the API's
  `units`, `frequency` and `aggregation_method`, after validation against the
  documented vocabularies (`dismal.fred.periods`).
- `--as-of DATE` sets `realtime_start=realtime_end=DATE` so the values are the
  ones published on that day (ALFRED); the response's `realtime_*` columns
  are included so the vintage is visible in the output.
- `--latest` is `sort_order=desc&limit=1`, one small request per series.
- Without a date flag the full history is returned, because the API
  transfers only what is asked for and the default is cheap.

## Consequences

- Results match fred.stlouisfed.org exactly for the same parameters.
- Anything FRED cannot do (year-over-year changes of weekly series, custom
  windows) is documented as "compute it yourself" in the practitioner's
  guide, with pandas recipes.
- `--raw` is close to the API's bytes, not merely its shape.
