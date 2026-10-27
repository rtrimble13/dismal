# Development

## Setup

```bash
git clone https://github.com/rtrimble13/dismal && cd dismal
make install          # creates .venv with uv and installs -e ".[dev]"
source .venv/bin/activate
dismal --help
```

Without `make`: `uv venv && uv pip install -e ".[dev]"`.

## Everyday commands

| Command | What it does |
| --- | --- |
| `make check` | `make lint`, `make typecheck` and `make test`. Same as CI. |
| `make lint` | ruff lint + format check |
| `make format` | ruff format + autofix |
| `make typecheck` | mypy (strict) |
| `make test` | pytest with coverage (every source plus the root CLI) |
| `make build` | sdist and wheel into `dist/` |
| `make release-dry` | Show the next patch/minor/major tags without changing anything |
| `make release BUMP=minor` | Update the changelog, commit and tag locally (see [releasing.md](releasing.md)) |
| `pre-commit install` | optional git hooks (ruff, whitespace, yaml/json checks) |

## Layout

```
src/dismal/
  __init__.py       __version__ and SOURCES = ("bls", "bea", "fred")
  cli/__init__.py   Root Typer app: mounts the three sources, adds the aggregated
                    config / doctor / cache / version commands
  core/             Code shared by every source
    cache.py        FileCache for slowly-changing metadata
    cli.py          State, get_state, warn/info, resolve_format, emit_records,
                    error_handler, collect_series_ids, cache helpers
    config.py       BaseSettings, EnvNames, settings_kwargs_from_env,
                    default_cache_dir(source), default_user_agent
    errors.py       ExitCode, DismalError (base of every source's errors), PeriodError
    output.py       OutputFormat and the json / jsonl / csv / parquet / table writers
    records.py      Record, jsonable, stringify, first_seen_columns
  bls/              The BLS source
    cli/            Typer app: _common (plumbing), data, discover, meta
    client.py       HTTP client: chunking, retries, endpoints
    config.py       Settings (BLS_* variables) on top of core.config
    periods.py      Period codes, frequencies, date-spec parsing, range overlap
    models.py       Observation / Series / DataResponse / Survey
    filters.py      Client-side observation filters
    records.py      Flatten to records; wide pivot
    search.py       Fuzzy scoring and search
    catalog.py      Bundled data loaders (surveys snapshot, curated series)
    flatfiles.py    download.bls.gov series directories
    errors.py       BLSError and subclasses
    output.py, cache.py   Re-exports of dismal.core.output / dismal.core.cache
    data/           surveys.json, series_catalog.json
  bea/              The BEA source: same shape, plus datasets.py (static
                    per-dataset knowledge); data/ holds datasets.json, catalog.json
  fred/             The FRED source: same shape; data/ holds series_catalog.json
tests/
  bls/ bea/ fred/   One pytest suite per source, each with its own conftest.py
  test_root_cli.py  The root command: flag placement, aggregated maintenance commands
docs/               Umbrella pages, docs/<source>/ pages and docs/adr/
examples/           Per-source scripts and workflows, one merged agent skill
scripts/            Release helpers (next_version, changelog_release, changelog_section)
.github/workflows/  ci.yml, release.yml, bump-version.yml
```

## How the sources share `dismal.core`

The three sources were stand-alone packages with near-identical plumbing;
the consolidation ([ADR 0010](adr/0010-one-cli-per-source-subcommands.md))
moved that plumbing into `dismal.core` and left each source's API-specific
code untouched:

- **Errors.** Every source exception derives from
  `dismal.core.errors.DismalError` and carries an `exit_code` from the shared
  `ExitCode` enum, so `except DismalError` catches any source's failure and
  the exit-code table is one table.
- **Settings.** Each source's `Settings` extends `core.config.BaseSettings`
  and reads its own prefix through `EnvNames("BLS")` and
  `settings_kwargs_from_env`, which also provide the cache directory
  (`default_cache_dir("bls")` -> `~/.cache/dismal/bls`) and the User-Agent.
- **Output and records.** `core.output` and `core.records` hold the
  serialisers and record helpers; the per-source `output.py` and `cache.py`
  are thin re-exports kept so old import paths keep working.
- **CLI plumbing.** `core.cli` holds `State` (the Typer context object:
  settings, verbosity, an optional mock transport), `get_state`, stderr
  helpers, format resolution, `emit_records`, `error_handler` and series-id
  collection. Each source's `cli/_common.py` subclasses `State` with its own
  `Settings` and `source` name (which sets the `dismal bls:` stderr prefix),
  binds `handle_errors = error_handler("dismal bls")` and adds `build_client`.
- **The root app** (`src/dismal/cli/__init__.py`) mounts the three source
  apps with `add_typer`. The root callback stores `-v/-q` on a bare
  `core.State`; the source callback promotes it to its own `State` subclass,
  which is how the flags work on either side of the source. The aggregated
  `config`, `doctor` and `cache` commands build one per-source state each and
  call the source's `meta.settings_record` / `meta.doctor_report`.

Source packages never import each other, and `dismal.core` never imports a
source.

## Adding a command to a source

1. Pick the module in `src/dismal/<source>/cli/`: `data.py` for commands that
   fetch observations, `discover.py` for catalog and metadata lookups,
   `meta.py` for maintenance. Each module exposes `register(app)`, which the
   source's `cli/__init__.py` calls.
2. Write the command with `@app.command(...)` and `@handle_errors` from
   `_common`, take `ctx: typer.Context`, and get the state with
   `get_state(ctx)`. Build the client with `build_client(state)` so tests can
   inject a transport.
3. Produce `list[Record]` and hand it to `emit_records(state, records,
   resolve_format(state, fmt), output, columns=...)`; this gives the command
   `--format`, `--output` and `--columns` for free. Raise the source's error
   classes (never `typer.Exit` with a hand-picked code); `handle_errors` maps
   them to exit codes and the stderr prefix.
4. Add a fake endpoint to `tests/<source>/conftest.py` if the command needs
   one, then CLI tests in `tests/<source>/test_cli.py`.
5. Document the command in `docs/<source>/usage.md` (and the columns in
   `docs/<source>/output-formats.md`), and add it to the command table in
   [usage.md](usage.md). Flags shared by every source (`--format`, `-s/-e/-y`,
   `--layout`, `--strict`, ...) keep the same spelling in all three.

## Testing

No API is ever called in tests. Each suite's `conftest.py` contains a small
in-memory fake of its API, served through `httpx.MockTransport`:

| Fixture class | Serves |
| --- | --- |
| `tests/bls/conftest.py: FakeBLS` | The four BLS endpoints plus the flat-file host, with deterministic observations. |
| `tests/bea/conftest.py: FakeBEA` | The five BEA API methods for a few NIPA, Regional, GDPbyIndustry and ITA tables, including the API's quirks (single objects instead of one-element lists, thousands separators, `(NA)` values, `Error` objects with HTTP 200). |
| `tests/fred/conftest.py: FakeFRED` | The FRED endpoints the client uses (series, observations with pagination, units, frequency aggregation and vintages, search with filters and tags, vintage dates, updates, releases and release dates, categories, sources), including `.` for holidays in daily series. |

CLI tests inject the fake via `State(transport=fake.transport)` passed as the
Typer context object (`runner.invoke(app, args, obj=state)`); client tests
pass it to `BLSClient(transport=...)` and friends. Each suite also has a
`cache_dir` fixture pointing `<SOURCE>_CACHE_DIR` at a temporary directory
and an autouse fixture that clears the `<SOURCE>_*` environment.

`tests/test_root_cli.py` covers the root command: `--version`, flag placement
before and after the source, and the aggregated `config`, `doctor`, `cache
info|clear` and `version` commands, with every source's fake mounted on one
transport.

Run one suite with `uv run pytest tests/fred`, everything with `make test`.

To exercise the real APIs locally:

```bash
export BLS_API_KEY=... BEA_API_KEY=... FRED_API_KEY=...
dismal doctor
dismal bls latest LNS14000000 -v
dismal bea latest NIPA -t T10101 -F Q -v
dismal fred latest UNRATE -v
```

## Adding a series to the curated catalog

The BLS and FRED sources each bundle a curated series catalog that
`dismal <source> search` searches offline. Everyday wording goes in one of
two places in either catalog ([ADR 0009](adr/0009-catalog-aliases.md)):

- **`tags`** for single words and established terms (`jobs`, `pay`, `core`,
  `u-6`, `cpi`, `vix`, `yield curve`). Each word of a tag earns credit on its
  own, so avoid multi-word tags whose words could pair with unrelated titles,
  and give a tag to one series only when a query should have one clear winner.
- **`aliases`** (optional) for everyday phrases people type whole
  (`grocery prices`, `wage growth`, `cost of living`, `mortgage rates`, `jobs
  report`, `fed balance sheet`). An alias matches only the entire query,
  ignoring case, word order, plurals and small words such as "of" and "in",
  and lends no credit to its individual words. An alias must contain at
  least two significant words (a test enforces it).

Check a new phrase with `dismal <source> search "<phrase>"`, and check that
it does not create matches for unrelated queries
(`tests/<source>/test_search_catalog.py` pins both kinds).

### BLS: `src/dismal/bls/data/series_catalog.json`

Each entry needs `id`, `title`, `survey` (must equal the first two characters
of the id), `frequency`, `seasonal` (`SA`/`NSA`), `units`, and `tags` (search
keywords); `aliases` is optional. Keep national headline series before
regional ones within a survey: ties in search score keep file order. Verify
the id with `dismal bls series info ID` before committing.

```json
{
  "id": "CUUR0000SA0",
  "title": "CPI-U: All items, U.S. city average, not seasonally adjusted",
  "survey": "CU",
  "frequency": "monthly",
  "seasonal": "NSA",
  "units": "index 1982-84=100",
  "tags": ["cpi", "inflation", "consumer prices", "headline"],
  "aliases": ["inflation rate", "consumer price index", "cost of living"]
}
```

### FRED: `src/dismal/fred/data/series_catalog.json`

Each entry needs `id`, `title`, `frequency` (`daily`, `weekly`, `biweekly`,
`monthly`, `quarterly`, `annual`), `seasonal` (`SA`/`NSA`), `units`, `source`
(the publishing agency) and `tags`; `aliases` is optional. Keep headline
series before variants: ties in search score keep file order. Verify the id
with `dismal fred series info ID` before committing.

```json
{
  "id": "GDP",
  "title": "Gross Domestic Product",
  "frequency": "quarterly",
  "seasonal": "SA",
  "units": "billions of dollars, annual rate",
  "source": "BEA",
  "tags": ["gdp", "nominal gdp", "output", "headline"],
  "aliases": ["gross domestic product", "size of the economy", "nominal gdp level"]
}
```

## Adding a table to the curated catalog

Edit `src/dismal/bea/data/catalog.json`. Each entry needs `id` (the table or
indicator code), `dataset`, `title`, `params` (what `dismal bea data` must
send to fetch it, e.g. `{"TableName": "T10101"}` or `{"TableName": "SAINC1",
"LineCode": "1", "GeoFips": "STATE"}`), `frequency` (available codes,
preferred first), `units` and `tags` (search keywords). Keep headline tables
before detail tables within a dataset: ties in search score keep file order.
Verify the entry with `dismal bea tables show DATASET TABLE` before
committing.

```json
{
  "id": "T10101",
  "dataset": "NIPA",
  "title": "Table 1.1.1. Percent Change From Preceding Period in Real Gross Domestic Product",
  "params": {"TableName": "T10101"},
  "frequency": "Q,A",
  "units": "percent change, annual rate",
  "tags": ["gdp", "real gdp", "gdp growth", "growth rate", "headline"]
}
```

## Supporting a new BEA dataset

Datasets unknown to `src/dismal/bea/datasets.py` already work: parameters
pass through, and the series id is derived from every non-time dimension
column. To add shortcuts, defaults and a precise series id, add a
`DatasetInfo` entry (table parameter, frequency support, required
parameters, `series_key`, `title_columns`) and a fake table in
`tests/bea/conftest.py`.

## Style

- Python 3.10+, `from __future__ import annotations`, type hints everywhere
  (mypy strict).
- Ruff for lint and formatting, line length 100.
- CLI commands live in `src/dismal/<source>/cli/*.py` and register themselves
  via `register(app)`; behaviour shared by one source's commands goes in its
  `_common.py`, behaviour shared by every source in `dismal.core.cli`.
- Errors raised from library code are subclasses of the source's base error
  (`BLSError`, `BEAError`, `FREDError`), which derive from `DismalError`; the
  CLI maps them to exit codes in `dismal.core.cli.error_handler`.
- A change that touches `dismal.core` is a change to every source: run
  `make check`, not one suite.
- Decisions with lasting consequences get an ADR in `docs/adr/`.

## Releasing

One version covers the whole package and is derived from `vX.Y.Z` git tags;
see [releasing.md](releasing.md).
