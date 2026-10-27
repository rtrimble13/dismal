# `dismal bea` for agents and automations

This page is the contract an agent skill, cron job or CI step can rely on. It
is intentionally terse; link to it from your skill instead of copying it.

## Invariants

- **Data on stdout, diagnostics on stderr.** Never parse stderr.
- **Pass `--format` explicitly** (`json`, `jsonl`, `csv`, `parquet`). Without
  it, output is JSON when stdout is not a terminal.
- **The API key comes from `BEA_API_KEY`.** There is no flag and no anonymous
  mode: every live command exits 7 without a key.
- **Exit codes are stable** (below). Treat 4 (rate limit) as "wait an hour",
  5 (network) as "retry with back-off", 2 as "my command was wrong".
- **Every dataset yields the same core columns**; dataset-specific dimensions
  follow them.
- **Rows are chronological** per series unless `--descending`.
- **Nothing is cached except metadata** (datasets, parameters, parameter
  values). Every `dismal bea data` call hits the API.

## Exit codes

| Code | Meaning | Suggested handling |
| --- | --- | --- |
| 0 | success | parse stdout |
| 1 | unexpected error | report |
| 2 | usage error (flags, dates, missing parameter, columns) | fix the command; stderr names the missing parameter |
| 3 | API error or HTTP error | inspect stderr; usually a bad table/parameter value |
| 4 | rate limit (100 requests / 100 MB / 30 errors per minute) | stop; the key is blocked for one hour |
| 5 | network / timeout | retry with back-off |
| 6 | `--strict` and a request returned no data | check parameters / widen the range |
| 7 | configuration error (missing or rejected key) | fix `BEA_API_KEY` |

## Recipes

Latest value of every line of a table, one line per series:

```bash
dismal bea latest NIPA --table T10101 --frequency Q --format jsonl --strict
```

A date range as tidy JSON, selected columns:

```bash
dismal bea data NIPA -t T20804 -F M --start 2023-01 --end 2024-12 \
  --columns series_id,series_title,date,value --format json
```

A wide CSV for a spreadsheet or dataframe (one column per series id):

```bash
dismal bea data NIPA -t T10105 -t T10106 -F A --years 10 --layout wide --format csv -o gdp.csv
```

State-level data, Parquet for a data lake:

```bash
dismal bea data Regional -t SAINC1 --line 1 --geo STATE --start 2000 --format parquet -o income.parquet
```

Resolve a plain-language request to a table (offline, no requests used):

```bash
dismal bea search "real gdp growth" --limit 5 --format json     # each hit has a "command" field
dismal bea search "county personal income" --dataset Regional --format json
dismal bea tables list NIPA --query "price index" --limit 10 --format json   # exhaustive, 1 request then cached
```

Learn a table's lines / a parameter's values before fetching (1 request, cached):

```bash
dismal bea tables show NIPA T20100 --format json          # series_id, series_title, latest value
dismal bea values Regional LineCode --filter TableName=SAINC1 --format json
dismal bea values Regional GeoFips --query texas --format json
dismal bea datasets show GDPbyIndustry --format json      # the dataset's parameters
```

Health check before a batch (1 request):

```bash
dismal bea doctor >/dev/null && echo ok
```

## Request budget

A `dismal bea data` call issues one request per `--table` value (one otherwise).
There is no daily quota, but more than 100 requests, 100 MB or 30 errors in a
minute blocks the key for an hour. Batch years into one call (`--years`,
`--start/--end`), avoid guessing parameters in a loop, and reuse the cached
metadata commands.

## Output schema (long layout)

```
dataset        string
series_id      string   BEA series code, or dimension values joined with ":"
series_title   string
date           ISO date (first day of the period)
year           int
period         string   2024 | 2024Q1 | 2024M01
frequency      annual | quarterly | monthly
value          float | null
unit           string | null   e.g. "Level", "Percent change, annual rate"
unit_mult      int | null      power of ten: 6 = millions, 9 = billions
note_ref       string
notes          string          (only with --notes)
<dimensions>   strings/ints    table_name, line_number, geo_fips, industry, ... by dataset
```

See [output-formats.md](output-formats.md) for the wide layout and Parquet types.

## Parsing tips

- `jq`: `dismal bea latest NIPA -t T10101 -F Q -f json | jq -r '.[] | select(.series_id=="A191RL") | .value'`
- Python: `json.loads(subprocess.run([...,"-f","json"], capture_output=True, text=True, check=True).stdout)`
- pandas: `pd.read_csv(io.StringIO(csv_text), parse_dates=["date"])` or `pd.read_parquet(path)`
- Scale with `unit_mult`: `value * 10 ** unit_mult` gives the value in units.
- Prefer `jsonl` when streaming or when a single malformed row must not spoil a batch.

## A ready-made skill

[`examples/skill/SKILL.md`](../../examples/skill/SKILL.md) packages these rules
(and those of the `bls` and `fred` sources) as a skill for Claude Code / Agent
SDK style workflows.
[practitioners-guide.md](practitioners-guide.md) is the judgment layer on top
of this contract: choosing tables and lines, annual rates and chained dollars,
revisions and release lags, and reporting answers with sources.
