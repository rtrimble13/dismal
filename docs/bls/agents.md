# `dismal bls` for agents and automations

This page is the contract an agent skill, cron job or CI step can rely on. It
is intentionally terse; link to it from your skill instead of copying it.

## Invariants

- **Data on stdout, diagnostics on stderr.** Never parse stderr.
- **Pass `--format` explicitly** (`json`, `jsonl`, `csv`, `parquet`). Without
  it, output is JSON when stdout is not a terminal.
- **The API key comes from `BLS_API_KEY`.** There is no flag. Without a key the
  tool still works with lower limits (25 requests/day).
- **Exit codes are stable** (below). Treat 4 (quota) as "retry tomorrow", 5
  (network) as "retry with back-off", 2 as "my command was wrong".
- **Series ids are upper-cased and de-duplicated**; order of output follows the
  order given.
- **Rows are chronological** per series unless `--descending`.
- **Nothing is cached except metadata** (survey list, flat files). Every
  `dismal bls data` call hits the API.

## Exit codes

| Code | Meaning | Suggested handling |
| --- | --- | --- |
| 0 | success | parse stdout |
| 1 | unexpected error | report |
| 2 | usage error (flags, dates, columns) | fix the command |
| 3 | API failure or HTTP error | inspect stderr; usually a bad id or parameter |
| 4 | daily threshold / rate limit | stop; retry after the daily reset (midnight US Eastern) |
| 5 | network / timeout | retry with back-off |
| 6 | `--strict` and a series returned no data | check ids / widen the range |
| 7 | configuration error | fix environment variables |

## Recipes

Latest value of several series, one line per series:

```bash
dismal bls latest LNS14000000 CUUR0000SA0 CES0000000001 --format jsonl --strict
```

A date range as tidy JSON with 12-month percent changes:

```bash
dismal bls data CUUR0000SA0 --start 2023-01 --end 2024-12 --calculations \
  --columns series_id,date,value,pct_change_12 --format json
```

A wide CSV for a spreadsheet or dataframe:

```bash
dismal bls data CUUR0000SA0 CUUR0000SA0L1E LNS14000000 --years 10 --layout wide --format csv -o macro.csv
```

Parquet for a data lake:

```bash
dismal bls data --series-file ids.txt --start 2000 --end 2024 --format parquet -o bls.parquet
```

Resolve a plain-language request to ids (offline, no quota used):

```bash
dismal bls search "core inflation" --limit 5 --format json
dismal bls search "texas unemployment" --survey LA --format json
dismal bls series list --survey AP --query "eggs" --limit 5 --format json   # exhaustive, needs network once
```

Describe ids before using them (1 request):

```bash
dismal bls series info CUUR0000SA0 LNS14000000 --format json
```

Health check before a batch (1 request):

```bash
dismal bls doctor >/dev/null && echo ok
```

## Request budget

A single `dismal bls data` call issues `ceil(n_series / 50) * ceil(n_years / 20)`
requests with a key (`/25` and `/10` without). The daily cap is 500 with a key.
Batch ids into one call; prefer `--latest` for monitoring; avoid re-fetching
history every run.

## Output schema (long layout)

```
series_id      string
date           ISO date (first day of the period)
year           int
period         string   M01-M12, M13 (annual avg), Q01-Q05, S01-S03, A01
period_name    string
frequency      monthly | quarterly | semiannual | annual
value          float | null
footnotes      string   "CODE: text; ..."
latest         bool
annual_average bool     (only with --annual-average)
series_title…  strings  (only with --catalog; needs a key)
net_change_N, pct_change_N  float | null  (N in 1,3,6,12; only with --calculations)
```

See [output-formats.md](output-formats.md) for the wide layout and Parquet types.

## Parsing tips

- `jq`: `dismal bls latest LNS14000000 -f json | jq -r '.[0].value'`
- Python: `json.loads(subprocess.run([...,"-f","json"], capture_output=True, text=True, check=True).stdout)`
- pandas: `pd.read_csv(io.StringIO(csv_text), parse_dates=["date"])` or `pd.read_parquet(path)`
- Prefer `jsonl` when streaming or when a single malformed row must not spoil a batch.

## A ready-made skill

[`examples/skill/SKILL.md`](../../examples/skill/SKILL.md) packages these rules as
a skill for Claude Code / Agent SDK style workflows.
[practitioners-guide.md](practitioners-guide.md) is the judgment layer on top
of this contract: choosing series, computing changes correctly, interpreting
revisions and seasonal adjustment, and reporting answers with sources.
