---
name: dismal-data
description: "Fetch official U.S. economic data with the `dismal` CLI: labor and price statistics (CPI, unemployment, payrolls, PPI, JOLTS, wages) from the Bureau of Labor Statistics (`dismal bls`), national, regional and international accounts (GDP, personal income, PCE prices, GDP by industry, state and county data, trade balances) from the Bureau of Economic Analysis (`dismal bea`), and economic time series (interest rates, money supply, exchange rates, housing, government debt, plus mirrors of BLS/BEA headline series and their past vintages) from FRED, the Federal Reserve Bank of St. Louis database (`dismal fred`). Use when a task needs an official economic indicator, its latest reading, its history or a past vintage, or a CSV/Parquet extract of BLS, BEA or FRED data."
---

# Economic data via the `dismal` CLI

`dismal` is one command-line client for three APIs, one subcommand each:
`dismal bls` (BLS Public Data API), `dismal bea` (BEA Data API) and
`dismal fred` (FRED API). It is installed (`dismal --version` works) and
reads the API keys from `BLS_API_KEY`, `BEA_API_KEY` and `FRED_API_KEY`. BLS
works without a key at lower limits; every live `bea` and `fred` request
needs its key (exit 7 without it). `dismal doctor` checks all three at once
(JSON on stdout, exit 0 = every source healthy); `dismal <source> doctor`
checks one.

## Rules shared by every source

1. Always pass `--format json` (or `jsonl`/`csv`/`parquet` for files). Parse
   **stdout** only; stderr holds warnings (`dismal <source>: warning: ...`).
2. Resolve ids before fetching: `dismal <source> search "<plain words>"
   --limit 5 --format json` is offline and free in every source. Use the top
   hit if its `score` >= 90, otherwise show the user the candidates or use
   the source's live discovery command.
3. Fetch with one call for everything you need from a source; never loop
   over ids, tables or years one at a time.
4. Exit codes are the same everywhere: `0` ok; `2` your flags were wrong
   (read stderr, fix); `3` bad id/table/parameter or API error; `4` quota or
   rate limit (what to do differs by source, below); `5` network (retry once
   after a pause); `6` a series or table had no data; `7` key missing or
   rejected.
5. Every long-layout row has `series_id`, `date` (`YYYY-MM-DD`, first day of
   the period) and `value` (number or null); the other columns differ by
   source (schemas below).

## Choosing the source

| The question is about | Use |
| --- | --- |
| Unemployment, payrolls, participation, JOLTS, state/metro employment; CPI, PPI, average prices; wages, earnings, employment cost, productivity | `dismal bls` (the producing agency; detail series, `--catalog` metadata, `--calculations`) |
| GDP and its components, personal income and outlays, PCE prices, saving, corporate profits; GDP by industry, fixed assets, input-output; state, county and metro income/GDP; trade balance, international transactions, investment position | `dismal bea` (whole tables with every line and title in one call) |
| Interest rates, yields, Fed policy, money and credit, bank data; exchange rates, equity and commodity prices, housing, sentiment, international series; anything else | `dismal fred` |
| A headline BLS/BEA series when server-side transformations (`--units pc1`, `--frequency q`) are convenient | `dismal fred` (mirrors most headline series: `UNRATE`, `CPIAUCSL`, `GDPC1`, `A191RL1Q225SBEA`, ...). Prefer the agency for detail series and official metadata. |
| How a value looked on a past date; revisions; "as first published" | `dismal fred` with `--as-of` / `series vintages` (ALFRED) |
| What is being released this week | `dismal fred releases dates --days 7 --format json` |

When unsure, run the offline `search` of the two likeliest sources; the
scores tell you which catalog knows the phrase.

---

## `dismal bls` (Bureau of Labor Statistics)

### Rules

1. Always pass `--format json` (or `jsonl`/`csv`/`parquet` for files). Parse
   **stdout** only; stderr holds warnings.
2. Resolve series ids before fetching data:
   - `dismal bls search "<plain words>" --limit 5 --format json` (offline,
     free). Use the top `id` if its `score` >= 90, otherwise show the user
     the candidates.
   - For something not in the curated catalog:
     `dismal bls series list --survey <XX> --query "<words>" --limit 10 --format json`
     (`XX` = `CU` consumer prices, `AP` average prices, `LN` labor force,
     `CE` national payrolls, `SM` state payrolls, `LA` state/local
     unemployment, `WP` producer prices, `JT` JOLTS, `CI` employment cost
     index, `PR` productivity). Run `dismal bls surveys --format json` for
     the full list.
3. Fetch with one call for all ids you need:
   - latest: `dismal bls latest ID1 ID2 --format json --strict`
   - range: `dismal bls data ID1 ID2 --start YYYY-MM --end YYYY-MM --format json`
   - changes: add `--calculations` (adds `pct_change_12`, `net_change_1`, ...)
   - metadata: add `--catalog` (adds `series_title`, `seasonality`, ...)
4. Interpret exit codes: `0` ok; `2` your flags were wrong (read stderr,
   fix); `3` bad id or API error; `4` daily quota exhausted (stop, tell the
   user); `5` network (retry once after a pause); `6` a series had no data.
5. Budget: each `dismal bls data` call costs `ceil(ids/50) * ceil(years/20)`
   requests of a 500/day quota. Do not loop over ids one at a time.

### Output schema

Each JSON row: `series_id, date (YYYY-MM-DD, first day of period), year,
period (M01-M12, Q01-Q04, A01; M13 = annual average), period_name, frequency,
value (number or null), footnotes, latest (bool)`, plus optional
`series_title`, `pct_change_12`, etc.

### Worked example

User: "What's the latest core CPI and how much is it up year over year?"

```bash
dismal bls search "core cpi" --limit 3 --format json          # -> CUSR0000SA0L1E (SA), CUUR0000SA0L1E (NSA)
dismal bls latest CUUR0000SA0L1E --calculations --format json  # value, pct_change_12
```

Report the `period_name`/`year`, `value` and `pct_change_12` from the result.
Prefer not-seasonally-adjusted (`NSA`) series for year-over-year changes and
seasonally adjusted (`SA`) for month-over-month.

---

## `dismal bea` (Bureau of Economic Analysis)

### Rules

1. Always pass `--format json` (or `jsonl`/`csv`/`parquet` for files). Parse
   **stdout** only; stderr holds warnings.
2. Resolve the table and parameters before fetching data:
   - `dismal bea search "<plain words>" --limit 5 --format json` (offline,
     free). Each hit has a `command` field; use the top hit if its `score`
     >= 90, otherwise show the user the candidates.
   - For something not in the curated catalog:
     `dismal bea tables list <DATASET> --query "<words>" --limit 10 --format json`
     (`NIPA` national accounts, `NIUnderlyingDetail` detailed NIPA,
     `Regional` states/counties/metros, `GDPbyIndustry`, `ITA` international
     transactions, `IIP` investment position, `FixedAssets`). Run
     `dismal bea datasets --format json` for the full list and
     `dismal bea datasets show <DATASET> --format json` for its parameters.
   - To learn a table's lines (series ids and titles):
     `dismal bea tables show <DATASET> <TABLE> --format json`. For Regional
     line codes and geographies:
     `dismal bea values Regional LineCode --filter TableName=<T>` and
     `dismal bea values Regional GeoFips --query "<state>"`.
3. Fetch with one call per table set:
   - latest: `dismal bea latest NIPA -t T10101 -F Q --format json --strict`
   - range: `dismal bea data NIPA -t T10101 -F Q --start YYYY-Qn --end YYYY-Qn --format json`
   - regional: `dismal bea data Regional -t SAINC1 --line 1 --geo STATE --years 5 --format json`
   - other datasets: pass parameters as `NAME=VALUE`, e.g.
     `dismal bea data ITA Indicator=BalGds AreaOrCountry=AllCountries -F QSA --years 3`
   - notes/footnotes: add `--notes`
4. Interpret exit codes: `0` ok; `2` your flags or parameters were wrong
   (read stderr, it names the missing parameter); `3` bad table/parameter or
   API error; `4` rate limit (stop for an hour, tell the user); `5` network
   (retry once after a pause); `6` no data; `7` key missing or rejected.
5. Budget: 100 requests, 100 MB and 30 errors per minute per key; exceeding
   any blocks the key for an hour. Do not loop over tables or years one at a
   time, and do not guess parameters repeatedly - use the discovery commands.

### Output schema

Each JSON row: `dataset, series_id, series_title, date (YYYY-MM-DD, first day
of period), year, period (2024 | 2024Q1 | 2024M01), frequency (annual |
quarterly | monthly), value (number or null), unit, unit_mult (power of ten:
6 = millions), note_ref`, plus the dataset's dimension columns
(`table_name`, `line_number`, `geo_fips`, `industry`, ...). Report values with
their `unit`; multiply by `10 ** unit_mult` only when the user wants raw
units.

### Worked example

User: "How fast did the U.S. economy grow last quarter, and what did consumer
spending do?"

```bash
dismal bea search "real gdp growth" --limit 3 --format json     # -> T10101 (NIPA), command included
dismal bea latest NIPA -t T10101 -F Q --format json             # rows for every line of the table
```

Report `period`, `value` and `unit` for `series_id` `A191RL` (Gross domestic
product) and `DPCERL` (Personal consumption expenditures). Quarterly NIPA
growth rates are seasonally adjusted annual rates.

---

## `dismal fred` (FRED, Federal Reserve Bank of St. Louis)

### Rules

1. Always pass `--format json` (or `jsonl`/`csv`/`parquet` for files). Parse
   **stdout** only; stderr holds warnings.
2. Resolve series ids before fetching data:
   - `dismal fred search "<plain words>" --limit 5 --format json` (offline,
     free). Use the top `id` if its `score` >= 90, otherwise show the user
     the candidates.
   - For something not in the curated catalog:
     `dismal fred series search "<words>" --order-by popularity -n 10 --format json`
     (live, one request); add `--frequency m`, `--seasonal sa` or
     `--tag usa` to narrow, `--exclude-tag discontinued` to drop dead series.
   - Confirm what an id measures: `dismal fred series info ID --format json`
     (title, frequency, units, seasonal adjustment, last update).
3. Fetch with one call for all ids you need:
   - latest: `dismal fred latest ID1 ID2 --meta --format json --strict`
   - range: `dismal fred data ID1 ID2 --start YYYY-MM --end YYYY-MM --format json`
   - changes: add `--units pc1` (percent change from a year ago), `pch`
     (from the previous observation), `chg` (difference), `pca` (annualized)
   - lower frequency: add `--frequency m|q|a` (`--aggregation eop` for rates
     and stocks, the default `avg` for flows and indexes)
   - as first published: add `--as-of YYYY-MM-DD`
4. Interpret exit codes: `0` ok; `2` your flags were wrong (read stderr,
   fix); `3` bad id, units or frequency; `4` rate limit (wait a minute); `5`
   network (retry once after a pause); `6` a series had no data; `7` key
   missing or rejected.
5. Budget: 120 requests per minute; each `dismal fred data` call costs one
   request per series (two with `--meta`). Batch ids into one call; do not
   loop over ids one at a time.

### Output schema

Each JSON row: `series_id, date (YYYY-MM-DD; first day of the period for
monthly/quarterly/annual series), value (number or null)`, plus
`realtime_start`/`realtime_end` with `--as-of` and `title, units, frequency,
seasonal_adjustment, last_updated` with `--meta`. With `--units pc1`/`pch`
the value is a percent change; with `chg`/`ch1` a difference in the series'
units.

### Worked example

User: "What's the unemployment rate, and how does it compare to a year ago?"

```bash
dismal fred search "unemployment rate" --limit 3 --format json      # -> UNRATE, score 100
dismal fred data UNRATE --years 2 --meta --format json              # levels; the last row is the latest
dismal fred latest UNRATE --units ch1 --format json                 # change from a year ago, in points
```

Report the latest `date`, `value` and `units`, and the year-ago change in
percentage points (rates change by points, not percent). Say that the value
is the current vintage.

---

## Reference

The cross-source contract (invariants, exit codes, choosing a source, the
health check) is [`docs/agents.md`](../../docs/agents.md); each source's
recipes and request budget are in `docs/<source>/agents.md`.

For anything beyond a single lookup (derived measures such as real wages or
real values, growth versus levels, contributions, PCE inflation arithmetic,
yield-curve questions, state rankings, choosing between candidate series or
tables, vintages, revisions and release lags, the answer template), follow
the source's practitioner's guide, especially section 7 (agent protocol) and
section 8 (question playbook):

- [`docs/bls/practitioners-guide.md`](../../docs/bls/practitioners-guide.md)
- [`docs/bea/practitioners-guide.md`](../../docs/bea/practitioners-guide.md)
- [`docs/fred/practitioners-guide.md`](../../docs/fred/practitioners-guide.md)
