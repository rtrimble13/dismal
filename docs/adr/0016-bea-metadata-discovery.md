# 0016. BEA: discovery through the API's metadata methods, cached

Date: 2026-10-25
Status: accepted

## Context

Where BLS publishes flat-file series directories, BEA exposes metadata through
the API itself: `GetDataSetList`, `GetParameterList`, `GetParameterValues` and
`GetParameterValuesFiltered`. The values of some parameters depend on others
(Regional `LineCode` on `TableName`). Metadata changes rarely but every call
counts against the per-minute limits.

## Decision

- `dismal bea datasets` lists datasets from a bundled snapshot, or from a
  cached live copy after `--refresh`.
- `dismal bea datasets show DATASET` wraps `GetParameterList`; `dismal bea
  values DATASET PARAMETER [--filter K=V]` wraps `GetParameterValues[Filtered]`;
  `dismal bea tables list DATASET` is `values` for the dataset's table
  parameter with friendlier column names. All are cached for 7 days under
  `BEA_CACHE_DIR` and accept `--refresh`.
- `dismal bea tables show DATASET TABLE` fetches the table for the last two
  years at every frequency (one request) and summarises one row per series;
  for Regional, whose rows carry no line description, it lists the table's
  `LineCode` values instead.
- Parameter-value rows keep the API's columns but are normalised to `key` and
  `description` because the API names them differently per parameter
  (`Key/Desc`, `TableName/Description`, `FrequencyID/Description`).

## Consequences

- Complete discovery without flat files, at the cost of one request per
  dataset/parameter per week.
- The cache is metadata only; observations are never cached.
- `tables show` costs one data request and may return nothing for a table
  that has no data in the last two years.
