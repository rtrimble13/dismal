# dismal

[![CI](https://github.com/rtrimble13/dismal/actions/workflows/ci.yml/badge.svg)](https://github.com/rtrimble13/dismal/actions/workflows/ci.yml)
[![License: MIT](https://img.shields.io/badge/license-MIT-blue.svg)](LICENSE)
[![Python 3.10+](https://img.shields.io/badge/python-3.10%2B-blue.svg)](pyproject.toml)

One command-line client (and small Python library) for the public APIs of the
three main sources of official U.S. economic data:

| Source | Subcommand | What it covers |
| --- | --- | --- |
| [U.S. Bureau of Labor Statistics](https://www.bls.gov/developers/) | `dismal bls` | CPI, PPI, unemployment, payrolls, JOLTS, wages, productivity |
| [U.S. Bureau of Economic Analysis](https://apps.bea.gov/API/signup/) | `dismal bea` | GDP and NIPA tables, personal income, PCE prices, industries, states and counties, international accounts |
| [FRED, Federal Reserve Bank of St. Louis](https://fred.stlouisfed.org/) | `dismal fred` | 800,000+ series on growth, jobs, prices, rates, money, markets, housing, trade; ALFRED vintages |

It is built for two audiences at once: people doing ad-hoc research in a
terminal, and automations or AI agents that need predictable, scriptable access
to official time series. Every source has the same hooks (`data`, `latest`,
`search`, discovery commands, `config`, `doctor`, `cache`, `version`), the same
output formats, the same exit codes and the same conventions, so what you learn
on one source carries over to the others.

```console
$ export BLS_API_KEY=... BEA_API_KEY=... FRED_API_KEY=...   # free keys; see Configuration
$ dismal bls data LNS14000000 --start 2024-01 --end 2024-03 --format csv
series_id,date,year,period,period_name,frequency,value,footnotes,latest
LNS14000000,2024-01-01,2024,M01,January,monthly,3.7,,false
LNS14000000,2024-02-01,2024,M02,February,monthly,3.9,,false
LNS14000000,2024-03-01,2024,M03,March,monthly,3.8,,false
$ dismal bea data NIPA --table T10101 --frequency Q --start 2024-Q1 --end 2024-Q3 --columns series_id,series_title,period,value -f csv
series_id,series_title,period,value
A191RL,Gross domestic product,2024Q1,1.6
A191RL,Gross domestic product,2024Q2,3.0
A191RL,Gross domestic product,2024Q3,3.1
...
$ dismal fred data UNRATE CPIAUCSL --start 2024-01 --end 2024-03 --units pc1 --format csv
series_id,date,value
UNRATE,2024-01-01,8.1
UNRATE,2024-02-01,8.3
UNRATE,2024-03-01,8.6
CPIAUCSL,2024-01-01,3.1
...
```

`dismal` consolidates the former stand-alone `bls`, `bea` and `fred` tools into
one package ([ADR 0010](docs/adr/0010-one-cli-per-source-subcommands.md)).
Every command, flag and output of those tools is available unchanged under its
source: `bls data ...` became `dismal bls data ...`.

## Features

- **Everything each API offers**: multi-series data requests, server-side
  transformations and vintages (FRED), every dataset with `NAME=VALUE`
  pass-through (BEA), catalog metadata and calculations (BLS), plus the
  metadata and discovery endpoints of each API.
- **Limits handled for you**: requests are chunked, paginated or split per
  table as each API requires, and merged; transient failures are retried
  with back-off.
- **Filters the APIs lack**: inclusive date ranges down to the month
  (`--start 2020-03 --end 2024-Q2`), `--years N`, frequency selection,
  latest-only, `--strict` for automations.
- **Output for humans and machines**: `table`, `json`, `jsonl`, `csv`,
  `parquet`; long (tidy) or wide layouts; `--columns` to pick columns;
  `--raw` for the untouched API shape. JSON by default when piped.
- **Discovery with fuzzy search**: `dismal <source> search "plain words"`
  works offline against a curated catalog per source, tolerates typos and
  understands everyday phrases ("grocery prices", "mortgage rates",
  "real gdp"); the live discovery commands cover the complete universe of
  each API.
- **Automation friendly**: API keys from the environment only, stable exit
  codes shared by every source, warnings on stderr and data on stdout,
  `--quiet`, `--series-file -` to read ids from stdin, `dismal doctor` to check
  all three sources at once.
- **One Python package**: `dismal.bls.BLSClient`, `dismal.bea.BEAClient` and
  `dismal.fred.FREDClient`, typed models, and one `DismalError` base class.
- **Linux CI, tag-driven releases**: one version for the whole package,
  derived from `vX.Y.Z` git tags; a one-click workflow bumps, tags and
  publishes.

## Installation

Requires Python 3.10+.

```bash
# with uv (recommended)
uv tool install git+https://github.com/rtrimble13/dismal
# or with pipx
pipx install git+https://github.com/rtrimble13/dismal
# or into the current environment
pip install git+https://github.com/rtrimble13/dismal
```

For development:

```bash
git clone https://github.com/rtrimble13/dismal && cd dismal
make install        # uv venv + editable install with dev extras
make check          # ruff, mypy, pytest
```

## Configuration

Each source reads its own `<SOURCE>_*` environment variables; nothing is shared
except `NO_COLOR`. Set the keys once; everything else has sensible defaults.

| Variable | Purpose |
| --- | --- |
| `BLS_API_KEY` | BLS registration key (free at <https://data.bls.gov/registrationEngine/>). Optional: without it BLS allows 25 requests/day, 25 series and 10 years per request. |
| `BEA_API_KEY` | BEA 36-character UserID (free at <https://apps.bea.gov/API/signup/>). **Required** for every live BEA request. |
| `FRED_API_KEY` | FRED 32-character key (free at <https://fred.stlouisfed.org/docs/api/api_key.html>). **Required** for every live FRED request. |
| `BLS_FORMAT`, `BEA_FORMAT`, `FRED_FORMAT` | Default `--format` per source. Default: `table` on a TTY, `json` otherwise. |
| `BLS_CACHE_DIR`, `BEA_CACHE_DIR`, `FRED_CACHE_DIR` | Where each source caches metadata. Default: `~/.cache/dismal/<source>`. |
| `BLS_TIMEOUT`, `BLS_MAX_RETRIES`, `BLS_USER_AGENT`, `BLS_API_BASE_URL` (and the `BEA_`/`FRED_` equivalents) | HTTP timeout, retries, User-Agent and endpoint override per source. |
| `NO_COLOR` | Disable colour in table output. |

The keys are deliberately **not** accepted as flags (see
[ADR 0003](docs/adr/0003-api-key-from-environment.md)). `dismal config` prints
the effective configuration of every source with the keys masked;
`dismal doctor` additionally checks connectivity to all three APIs. The
per-source pages list every variable: [bls](docs/bls/configuration.md),
[bea](docs/bea/configuration.md), [fred](docs/fred/configuration.md).

## Usage

```text
dismal [-v|-vv] [-q] [--version] <source> <command> [options]

dismal bls   data | latest | search | surveys | popular | series | config | doctor | cache | version
dismal bea   data | latest | search | datasets | tables | values | config | doctor | cache | version
dismal fred  data | latest | search | series | releases | categories | config | doctor | cache | version

dismal config    Effective configuration of every source (keys masked)
dismal doctor    Configuration + connectivity check of every source
dismal cache     info | clear, across every source
dismal version   Print the version
```

`-v` and `-q` are accepted before or after the source (`dismal -q bls data ...`
or `dismal bls -q data ...`). Run `dismal <source> --help` for a source's
commands and `dismal <source> <command> --help` for all options. Highlights:

```bash
# BLS: monthly CPI-U and core CPI, 2019 through June 2024, one column per series
dismal bls data CUUR0000SA0 CUUR0000SA0L1E --start 2019 --end 2024-06 --layout wide -f csv -o cpi.csv

# BLS: unemployment rate, last 5 years, with 1/3/6/12-month changes, as Parquet
dismal bls data LNS14000000 --years 5 --calculations -f parquet -o unrate.parquet

# BEA: real GDP growth, quarterly, one column per line of the table
dismal bea data NIPA --table T10101 --frequency Q --start 2019 --end 2024-Q2 --layout wide -f csv -o gdp.csv

# BEA: per-capita personal income for every state, last 5 years
dismal bea data Regional TableName=SAINC1 --line 3 --geo STATE --years 5

# FRED: 10-year and 2-year Treasury yields, monthly averages since 2019
dismal fred data DGS10 DGS2 --frequency m --start 2019 --layout wide -f csv -o yields.csv

# FRED: nonfarm payrolls as first published on 2 February 2024, from ALFRED
dismal fred data PAYEMS --as-of 2024-02-02 --years 1

# Latest readings, one line per series, fail if any is missing
dismal bls latest LNS14000000 CES0000000001 --format jsonl --strict
dismal fred latest UNRATE PAYEMS FEDFUNDS MORTGAGE30US --meta

# Find ids without knowing them (offline, typo-tolerant)
dismal bls search "unemploymnt rate"
dismal bea search "real gdp"
dismal fred search "mortgage rates"

# Exhaustive discovery through the live APIs
dismal bls series list --survey AP --query eggs
dismal bea tables list NIPA --query pce
dismal fred series search "median home price" --order-by popularity -n 10
dismal fred releases dates --days 7

# Health check of all three sources (one request each)
dismal doctor
```

The per-source references cover every command and flag:
[docs/bls/usage.md](docs/bls/usage.md), [docs/bea/usage.md](docs/bea/usage.md),
[docs/fred/usage.md](docs/fred/usage.md).

### Dates and frequencies

`--start`/`--end` accept `YYYY`, `YYYY-MM`, `YYYY-MM-DD`, `YYYY-Qn` and
`YYYY-Hn` for every source. Both bounds are inclusive. BLS and BEA only
understand whole years, so those sources fetch whole years and trim locally;
FRED receives the bounds directly. Frequency handling is source-specific
(`--frequency monthly|quarterly|...` for BLS, `--frequency Q` for BEA tables,
server-side aggregation with `--frequency m --aggregation eop` for FRED); see
each source's usage page.

### Output

Every source produces tidy *long* records with `series_id`, `date` and
`value` first, followed by the columns that source adds (period codes and
footnotes for BLS; dataset, table, line, units for BEA; vintage and metadata
columns for FRED). `date` is the first day of the period (ISO 8601 in text
formats, `date32` in Parquet); `value` is a float or `null`. `--layout wide`
gives one row per period and one column per series. See
[docs/output-formats.md](docs/output-formats.md) for the shared rules and the
schema of each source.

### Exit codes

The same for every source:

| Code | Meaning |
| --- | --- |
| 0 | success |
| 1 | unexpected error |
| 2 | usage error (bad flag, bad date, unknown column) |
| 3 | the API reported a failure or returned an HTTP error |
| 4 | daily request threshold / rate limit exceeded |
| 5 | network problem (DNS, timeout, connection reset) |
| 6 | `--strict` and at least one series or table returned no data |
| 7 | configuration error (e.g. a missing API key) |

Warnings go to **stderr**, prefixed with the source (`dismal fred: warning:`);
data goes to **stdout**. `--quiet` silences the warnings.

## Python API

```python
from dismal.bls import BLSClient
from dismal.bea import BEAClient
from dismal.fred import FREDClient
from dismal.bls.config import Settings as BLSSettings

with BLSClient.from_settings(BLSSettings.from_env()) as bls:  # or BLSClient(api_key="...")
    resp = bls.fetch(["LNS14000000", "CUUR0000SA0"], start_year=2015, end_year=2024)
    for series in resp.series:
        for obs in series.data:
            print(series.series_id, obs.date, obs.value)

with FREDClient(api_key="...") as fred:
    resp = fred.fetch(["UNRATE"], units="pc1")
```

Every source's errors derive from `dismal.core.errors.DismalError`, so one
`except` clause covers all three. See [docs/python-api.md](docs/python-api.md)
and the per-source pages.

## For agents and automations

`dismal` is designed to be called from scripts, cron jobs, GitHub Actions and
agent skills. [docs/agents.md](docs/agents.md) is the compact contract
(choosing a source, commands, flags, output schemas, exit codes, request
budgets) that a skill can reference, and
[examples/skill/SKILL.md](examples/skill/SKILL.md) is a ready-made skill
covering all three sources. The practitioner's guides
([bls](docs/bls/practitioners-guide.md), [bea](docs/bea/practitioners-guide.md),
[fred](docs/fred/practitioners-guide.md)) are the companion references for
turning questions into series, fetches and sourced answers.
[examples/](examples/) contains recipes, Python examples and scheduled
data-pull workflows per source.

## Documentation

- [docs/usage.md](docs/usage.md) - the command structure and the hooks every source shares
- [docs/configuration.md](docs/configuration.md) - environment variables, limits, caching
- [docs/output-formats.md](docs/output-formats.md) - formats, layouts and record schemas
- [docs/agents.md](docs/agents.md) - the contract for agentic workflows
- [docs/python-api.md](docs/python-api.md) - using the library
- [docs/development.md](docs/development.md) - repository layout, contributing, tests, tooling
- [docs/releasing.md](docs/releasing.md) - versioning and the release workflow
- [docs/adr/](docs/adr/) - architecture decision records
- Per source: [docs/bls/](docs/bls/), [docs/bea/](docs/bea/), [docs/fred/](docs/fred/)
  (usage, configuration, output formats, agents, Python API, practitioner's
  guide, how to read the ids)
- [CHANGELOG.md](CHANGELOG.md)

## Versioning

Versions are `vMAJOR.MINOR.PATCH` git tags; the package version is derived from
them at build time (hatch-vcs). Releases are produced by the **Bump version**
workflow in the Actions tab (choose patch/minor/major), which updates
`CHANGELOG.md`, tags, builds, verifies, and publishes a GitHub release
([docs/releasing.md](docs/releasing.md)).

## Data notes

- BLS, BEA and FRED data are provided under each publisher's terms:
  [BLS API terms of service](https://www.bls.gov/developers/termsOfService.htm),
  [BEA API terms](https://apps.bea.gov/API/_pdf/bea_web_service_api_user_guide.pdf),
  [FRED API terms of use](https://fred.stlouisfed.org/docs/api/terms_of_use.html).
- BLS flat-file downloads (`dismal bls series list`) come from
  `download.bls.gov`, which refuses requests without a descriptive
  `User-Agent`; set `BLS_USER_AGENT` with a contact address if you hit HTTP 403.
- The bundled survey list (BLS) and dataset list (BEA) are snapshots;
  `dismal bls surveys --refresh` and `dismal bea datasets --refresh` fetch the
  live lists and cache them.

## License

MIT - see [LICENSE](LICENSE).
