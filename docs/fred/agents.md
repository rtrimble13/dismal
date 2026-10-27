# `dismal fred` for agents and automations

This page is the contract an agent skill, cron job or CI step can rely on. It
is intentionally terse; link to it from your skill instead of copying it.

## Invariants

- **Data on stdout, diagnostics on stderr.** Never parse stderr.
- **Pass `--format` explicitly** (`json`, `jsonl`, `csv`, `parquet`). Without
  it, output is JSON when stdout is not a terminal.
- **The API key comes from `FRED_API_KEY`.** There is no flag and no anonymous
  mode: every live command exits 7 without a key.
- **Exit codes are stable** (below). Treat 4 (rate limit) as "wait a minute",
  5 (network) as "retry with back-off", 2 as "my command was wrong".
- **Series ids are upper-cased and de-duplicated**; order of output follows the
  order given. Unknown ids are warnings, not errors, unless `--strict`.
- **Rows are chronological** per series unless `--descending`.
- **Values are the current vintage** unless `--as-of` is given.
- **Nothing is cached except metadata** (releases, categories). Every
  `dismal fred data` call hits the API.

## Exit codes

| Code | Meaning | Suggested handling |
| --- | --- | --- |
| 0 | success | parse stdout |
| 1 | unexpected error | report |
| 2 | usage error (flags, dates, columns) | fix the command |
| 3 | API error or HTTP error | inspect stderr; usually a bad id, units or frequency |
| 4 | rate limit (120 requests per minute) | pause for a minute, then retry |
| 5 | network / timeout | retry with back-off |
| 6 | `--strict` and a series returned no data | check ids / widen the range |
| 7 | configuration error (missing or rejected key) | fix `FRED_API_KEY` |

## Recipes

Latest value of several series, one line per series, with titles and units:

```bash
dismal fred latest UNRATE CPIAUCSL FEDFUNDS DGS10 --meta --format jsonl --strict
```

Year-over-year inflation, computed by the API:

```bash
dismal fred data CPIAUCSL PCEPILFE --units pc1 --start 2023-01 --format json
```

Monthly averages of daily yields, as a wide CSV:

```bash
dismal fred data DGS2 DGS10 --frequency m --years 10 --layout wide --format csv -o yields.csv
```

Real GDP growth, annualized, from the series BEA publishes:

```bash
dismal fred data A191RL1Q225SBEA --years 3 --format json
```

What a series looked like on a past date (vintage):

```bash
dismal fred data PAYEMS --as-of 2024-02-02 --start 2023-10 --format json
```

Parquet for a data lake:

```bash
dismal fred data --series-file ids.txt --start 2000 --format parquet -o fred.parquet
```

Resolve a plain-language request to ids:

```bash
dismal fred search "mortgage rates" --limit 5 --format json                     # offline, free
dismal fred series search "median household income" --order-by popularity -n 5 --format json   # live, 1 request
```

Describe ids before using them (1 request each):

```bash
dismal fred series info UNRATE DGS10 --format json
```

What is being released soon (1 request):

```bash
dismal fred releases dates --days 7 --format json
```

Health check before a batch (1 request):

```bash
dismal fred doctor >/dev/null && echo ok
```

## Request budget

A `dismal fred data` call issues one request per series (two with `--meta`), each
returning at most 100,000 observations per page. The key allows 120 requests
per minute. Batch ids into one call, prefer `--latest` for monitoring, and
narrow with `--start/--end` so only the needed rows are transferred.

## Output schema (long layout)

```
series_id       string
date            ISO date (first day of the period for m/q/a series)
value           float | null   (null where FRED reports ".")
realtime_start  ISO date       (only with --as-of)
realtime_end    ISO date       (only with --as-of; 9999-12-31 = still current)
title, units, frequency, seasonal_adjustment, last_updated   strings (only with --meta)
```

See [output-formats.md](output-formats.md) for the wide layout and Parquet types.

## Parsing tips

- `jq`: `dismal fred latest UNRATE -f json | jq -r '.[0].value'`
- Python: `json.loads(subprocess.run([...,"-f","json"], capture_output=True, text=True, check=True).stdout)`
- pandas: `pd.read_csv(io.StringIO(csv_text), parse_dates=["date"])` or `pd.read_parquet(path)`
- Prefer `jsonl` when streaming or when a single malformed row must not spoil a batch.

## A ready-made skill

[`examples/skill/SKILL.md`](../../examples/skill/SKILL.md) packages these rules as
a skill for Claude Code / Agent SDK style workflows.
[practitioners-guide.md](practitioners-guide.md) is the judgment layer on top
of this contract: choosing series, computing changes correctly, reading
vintages and revisions, and reporting answers with sources.
