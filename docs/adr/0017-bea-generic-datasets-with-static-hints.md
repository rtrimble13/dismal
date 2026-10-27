# 0017. BEA: generic `GetData` pass-through plus static per-dataset hints

Date: 2026-10-25
Status: accepted

## Context

The BEA API is generic - `GetData` takes `datasetname` and whatever
parameters that dataset defines - but the datasets are heterogeneous:
different required parameters (`TableName`+`Frequency`+`Year` for NIPA,
`TableName`+`LineCode`+`GeoFips`+`Year` for Regional,
`Indicator`+`AreaOrCountry` for ITA), different "all years" tokens (`X` vs
`ALL`), and different row shapes from which a series id and title must be
derived. New datasets appear occasionally.

## Decision

- `dismal bea data DATASET NAME=VALUE...` passes any parameter through
  unchanged, so every dataset works on day one.
- A small static table (`dismal.bea.datasets.DatasetInfo`) records, per known
  dataset: the table parameter name (for `--table`), whether `Frequency` is
  accepted, the valid frequency codes, the all-years token, the required
  parameters (for early, precise usage errors), defaults (`Industry=ALL`), the
  columns that identify a series and the columns that describe it.
- Unknown datasets fall back to a generic rule: every non-time, non-value,
  non-description column identifies the series, the first description-like
  column titles it, and a warning says parameters are passed through.
- `series_id` is BEA's own code when the dataset has one (`SeriesCode`,
  `TimeSeriesId`); composite keys are joined with `:` so they stay readable
  and unique within a response.

## Consequences

- Shortcuts, validation and wide pivots are precise for the datasets people
  use most, without blocking the rest.
- The static table is a maintenance point; `dismal bea datasets show` (live)
  remains the source of truth when they disagree, and the docs say so.
- Composite ids such as `SAINC1-1:06000` are stable but not BEA vocabulary;
  the long layout always carries the underlying columns.
