# `dismal` for agents and automations

This page is the contract an agent skill, cron job or CI step can rely on
across every source. It is intentionally terse; the per-source pages hold
the recipes, request budgets and record schemas:

- [bls/agents.md](bls/agents.md) - Bureau of Labor Statistics
- [bea/agents.md](bea/agents.md) - Bureau of Economic Analysis
- [fred/agents.md](fred/agents.md) - FRED / ALFRED

[`examples/skill/SKILL.md`](../examples/skill/SKILL.md) packages all of it as
one skill for Claude Code / Agent SDK style workflows.

## Invariants (every source)

- **One command, one source per call.** `dismal <source> <command>`; the
  commands of a source are exactly those the stand-alone tool had.
- **Data on stdout, diagnostics on stderr.** Never parse stderr. Stderr lines
  are prefixed `dismal <source>: warning:`, `dismal <source>: error:` or
  `dismal <source>: hint:` (`dismal:` for the top-level commands).
- **Pass `--format` explicitly** (`json`, `jsonl`, `csv`, `parquet`). Without
  it, output is JSON when stdout is not a terminal.
- **API keys come from the environment**: `BLS_API_KEY`, `BEA_API_KEY`,
  `FRED_API_KEY`. There are no flags. BLS works without a key at lower
  limits; BEA and FRED exit 7 without one.
- **Exit codes are stable and identical** across sources (below).
- **Rows are chronological** per series unless `--descending`; series appear
  in the order requested (BLS, FRED) or returned by the API (BEA).
- **Nothing is cached except metadata** (survey, dataset, parameter, release
  and category lists, BLS flat files), under `~/.cache/dismal/<source>`.
  Every `data`/`latest` call hits the API.
- **`search` is offline and free** in every source; it searches a curated
  catalog, not the whole universe. The live discovery commands (`dismal bls
  series list`, `dismal bea tables list`, `dismal fred series search`, ...)
  are exhaustive.
- **The record shape differs per source**; the common ground is `series_id`,
  `date` (ISO, first day of the period) and `value` (number or null). See
  [output-formats.md](output-formats.md).

## Exit codes

| Code | Meaning | Suggested handling |
| --- | --- | --- |
| 0 | success | parse stdout |
| 1 | unexpected error | report |
| 2 | usage error (flags, dates, columns; BEA: missing parameter) | fix the command; stderr says what was wrong |
| 3 | API failure or HTTP error | inspect stderr; usually a bad id, table or parameter |
| 4 | quota / rate limit | BLS: stop, retry after the daily reset (midnight US Eastern); BEA: stop, the key is blocked for an hour; FRED: pause for a minute |
| 5 | network / timeout | retry with back-off |
| 6 | `--strict` and a series or table returned no data | check ids / widen the range |
| 7 | configuration error (malformed variable; missing or rejected BEA/FRED key) | fix environment variables |

## Choosing a source

| Question is about | Source | Why |
| --- | --- | --- |
| Labor market: unemployment, payrolls, participation, JOLTS, state and metro employment | `bls` | The producing agency; `--catalog` metadata, `--calculations` for 1/3/6/12-period changes. |
| Prices: CPI, PPI, average prices, import/export prices; wages, earnings, employment cost, productivity | `bls` | Same; thousands of detail series reachable with `dismal bls series list`. |
| GDP and its components (NIPA), personal income and outlays, PCE prices, saving, corporate profits | `bea` | The producing agency; whole tables with every line and its title in one call. |
| GDP by industry, fixed assets, input-output | `bea` | Only BEA publishes these as tables. |
| State, county and metro income, GDP and employment compensation | `bea` (Regional) | `--geo` and `--line` select geographies and lines. |
| Trade balance, international transactions, investment position, multinationals | `bea` (ITA, IIP, MNE) | |
| Interest rates, yields, Fed policy, money and credit aggregates, bank data | `fred` | Federal Reserve data lives on FRED. |
| Exchange rates, equity and commodity prices, housing, consumer sentiment, international series | `fred` | FRED aggregates hundreds of sources. |
| A headline BLS or BEA series when one request per id and server-side transformations (`--units pc1`, `--frequency q`) are convenient | `fred` | FRED mirrors most headline BLS/BEA series under its own ids (`UNRATE`, `CPIAUCSL`, `GDPC1`, ...). Prefer the agency for detail series, revisions and official metadata. |
| How a value looked on a past date (vintages, revisions, "as first published") | `fred` (`--as-of`, `series vintages`) | ALFRED keeps every vintage. |
| What is being released this week | `dismal fred releases dates` | |
| Anything else | `dismal fred series search` first | The widest live search; fall back to `dismal bls series list` / `dismal bea tables list` for agency detail. |

Resolve ids with the source's offline `search` first; when the top score is
below 90, use the live discovery command or show the user the candidates.

## Health check

One command checks every key and endpoint (one request per source):

```bash
dismal doctor >/dev/null && echo ok
```

It prints `{"version", "python", "sources": {"bls": ..., "bea": ...,
"fred": ...}, "healthy": bool}` and exits 0 only when every source is
healthy; otherwise it exits with the first unhealthy source's code (7 for a
missing or rejected key, 5 for an unreachable API). Use `dismal <source>
doctor` when a job needs only one source, so an unset key for another
source does not fail it. `dismal config` prints the effective settings of
every source with keys masked.

## Cross-source recipes

Latest readings from each agency, one JSON line per series:

```bash
dismal bls latest LNS14000000 CES0000000001 --format jsonl --strict
dismal bea latest NIPA -t T10101 -F Q --columns series_id,series_title,period,value --format jsonl
dismal fred latest FEDFUNDS DGS10 --meta --format jsonl --strict
```

The same indicator from the agency and from FRED, to cross-check or to pick
the one whose transformation you need:

```bash
dismal bls latest CUUR0000SA0 --calculations --columns series_id,date,value,pct_change_12 --format json
dismal fred latest CPIAUCSL --units pc1 --format json
```

Parsing tips (every source):

- `jq`: `dismal fred latest UNRATE -f json | jq -r '.[0].value'`
- Python: `json.loads(subprocess.run([...,"-f","json"], capture_output=True, text=True, check=True).stdout)`
- pandas: `pd.read_csv(io.StringIO(csv_text), parse_dates=["date"])` or `pd.read_parquet(path)`
- Prefer `jsonl` when streaming or when a single malformed row must not spoil a batch.

## Judgment

The agent pages are the contract; the practitioners' guides are the judgment
layer on top of it (choosing series or tables, computing changes correctly,
revisions and release lags, reporting answers with sources):
[bls](bls/practitioners-guide.md), [bea](bea/practitioners-guide.md),
[fred](fred/practitioners-guide.md).
