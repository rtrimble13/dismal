# Command reference

`dismal` is one command with one subcommand per data source. Each source keeps
its own `data`, `latest`, `search` and discovery commands, and the maintenance
commands (`config`, `doctor`, `cache`, `version`) exist both per source and,
aggregated over every source, at the top level.

```
dismal [-v|-vv] [-q] [--version] <source> <command> [options]
dismal <source> [-v|-vv] [-q] <command> [options]
dismal config | doctor | cache info|clear | version
```

All commands accept `-h/--help`. `-v` and `-q` may be given before or after
the source (`dismal -v bls data ...` and `dismal bls -v data ...` are the
same). `dismal` with no arguments prints the help.

## Sources

| Source | Data | Reference |
| --- | --- | --- |
| `bls` | U.S. Bureau of Labor Statistics Public Data API: CPI, PPI, employment, unemployment, wages, JOLTS, productivity. | [bls/usage.md](bls/usage.md) |
| `bea` | U.S. Bureau of Economic Analysis Data API: NIPA (GDP, income, PCE), GDP by industry, fixed assets, regional, international accounts. | [bea/usage.md](bea/usage.md) |
| `fred` | FRED, the Federal Reserve Bank of St. Louis database: interest rates, money, markets, and mirrors of most BLS/BEA headline series, with ALFRED vintages. | [fred/usage.md](fred/usage.md) |

Each source needs its own API key in the environment (`BLS_API_KEY`,
`BEA_API_KEY`, `FRED_API_KEY`); see [configuration.md](configuration.md).
BLS works without a key at lower limits; BEA and FRED exit 7 without one.

## Commands per source

Every source answers the same hooks: `data` fetches observations, `latest`
is `data --latest`, `search` is an offline fuzzy search over a curated
catalog, the discovery commands query the API's own lists, and the
maintenance commands are the same four everywhere. The per-source pages
document every option.

### `dismal bls`

| Command | Purpose |
| --- | --- |
| `data SERIES_ID...` | Observations for one or more series, with date range, frequency filter, catalog metadata and calculations. |
| `latest SERIES_ID...` | The newest observation of each series. |
| `search QUERY...` | Offline fuzzy search over the curated series catalog and the survey list. |
| `surveys [show ABBR]` | The survey list; `show` prints one survey's metadata. |
| `popular [--survey XX]` | Series BLS lists as popular. |
| `series list --survey XX` | Every series of a survey, from the BLS flat files. |
| `series info SERIES_ID...` | Catalog metadata plus the latest value. |
| `config`, `doctor`, `cache info\|clear`, `version` | Maintenance. |

### `dismal bea`

| Command | Purpose |
| --- | --- |
| `data DATASET [NAME=VALUE...]` | Observations from any dataset (`GetData`), with table, frequency, geography, line and industry shortcuts. |
| `latest DATASET ...` | The newest observation of each series of a table. |
| `search QUERY...` | Offline fuzzy search over the curated table catalog and the dataset list; each hit carries a ready-to-run command. |
| `datasets [show DATASET]` | The dataset list; `show` lists a dataset's parameters. |
| `tables list DATASET` | Every table of a dataset. |
| `tables show DATASET TABLE` | The lines (series) of one table. |
| `values DATASET PARAMETER` | The valid values of any parameter. |
| `config`, `doctor`, `cache info\|clear`, `version` | Maintenance. |

### `dismal fred`

| Command | Purpose |
| --- | --- |
| `data SERIES_ID...` | Observations for one or more series, with server-side units, frequency aggregation and `--as-of` vintages. |
| `latest SERIES_ID...` | The newest observation of each series. |
| `search QUERY...` | Offline fuzzy search over the curated series catalog. |
| `series info SERIES_ID...` | Metadata for each series. |
| `series search QUERY...` | The API's full-text search over every FRED series. |
| `series vintages SERIES_ID` | Every release or revision date of a series (ALFRED). |
| `series updates` | Series most recently updated on FRED. |
| `releases [show ID \| series ID \| dates]` | The release list, one release, its series, or the release calendar. |
| `categories [children ID \| series ID]` | The category tree and the series in a category. |
| `config`, `doctor`, `cache info\|clear`, `version` | Maintenance. |

## Top-level maintenance commands

The top-level commands run the per-source command for `bls`, `bea` and
`fred` in that order and combine the results.

| Command | Output |
| --- | --- |
| `dismal config [-o PATH]` | JSON `{"version": ..., "sources": {"bls": {...}, "bea": {...}, "fred": {...}}}`. Each source object is exactly what `dismal <source> config` prints (effective settings, masked key, limits, the environment variables read), including a `"source"` key. |
| `dismal doctor [-o PATH]` | JSON `{"version", "python", "sources": {<source>: <that source's doctor report>}, "healthy": bool}`. One live request per source. Exit 0 when every source is healthy, otherwise the exit code of the first unhealthy source (7 for a missing or rejected BEA/FRED key, 5 when an API is unreachable, ...). |
| `dismal cache info [-f FORMAT] [-o PATH]` | Cached metadata files of every source, columns `source, file, bytes`. |
| `dismal cache clear` | Deletes every source's cache (`~/.cache/dismal/<source>` by default) and prints one line per source on stderr. |
| `dismal version [--short]` | `dismal X.Y.Z (python 3.x.y)`, or only `X.Y.Z` with `--short`. `dismal <source> version` prints the same. |

`dismal --version` (or `-V`) prints `dismal X.Y.Z`. There is one version for
the whole package, from the `vX.Y.Z` git tags of the repository.

## Global options

| Option | Effect |
| --- | --- |
| `-v, --verbose` | Log each HTTP request to stderr; `-vv` adds httpx wire logs. Keys are never logged. |
| `-q, --quiet` | Suppress warnings and notes on stderr. Errors are still printed. |
| `-V, --version` | Print `dismal X.Y.Z` and exit. |
| `-h, --help` | Help for any command. |

Common output options, on every command that prints records:

| Option | Effect |
| --- | --- |
| `-f, --format {json,jsonl,csv,parquet,table}` | Output format. Default: `$<SOURCE>_FORMAT` (`BLS_FORMAT`, ...), else `table` on a TTY and `json` otherwise. |
| `-o, --output PATH` | Write to a file instead of stdout (`-` = stdout). Parquet to stdout writes binary. |
| `--columns a,b,c` | Emit only these columns, in this order (applies to every format). |

See [output-formats.md](output-formats.md) for the formats and the record
schema of each source.

## stdout and stderr

Data goes to stdout and nothing else does. Diagnostics go to stderr, one
line each, prefixed with the program and source:

```
dismal bls: warning: splitting 120 series into 3 requests
dismal bea: error: BEA API error 40: the parameter Year is required
dismal bea: hint: run `dismal bea datasets show NIPA` to list the parameters
dismal: bls: removed 2 cached file(s) from /home/me/.cache/dismal/bls
```

The top-level commands use the bare `dismal:` prefix.

## Shell completion

`dismal --install-completion` installs completion for the current shell;
`dismal --show-completion` prints it. Completion covers the sources, their
commands and options.

## Exit codes

The codes are the same for every source and are stable across releases
([ADR 0008](adr/0008-stable-exit-codes-and-streams.md)).

| Code | Meaning | Notes |
| --- | --- | --- |
| 0 | success | |
| 1 | unexpected error | |
| 2 | usage error | bad flags, dates, columns or (BEA) a missing required parameter |
| 3 | API failure or HTTP error | usually a bad id, table or parameter value |
| 4 | quota or rate limit | BLS: daily threshold (resets at midnight US Eastern); BEA: 100 requests / 100 MB / 30 errors per minute, key blocked for an hour; FRED: 120 requests per minute |
| 5 | network / timeout | after the configured retries |
| 6 | `--strict` and a series or table returned no data | |
| 7 | configuration error | malformed `<SOURCE>_*` variable; missing or rejected BEA/FRED key |

The per-source agent pages ([bls](bls/agents.md), [bea](bea/agents.md),
[fred](fred/agents.md)) suggest how to handle each code.

## Cross-source examples

The same indicator from two agencies, side by side:

```bash
dismal bls latest LNS14000000 --format json          # unemployment rate, from BLS
dismal fred latest UNRATE --meta --format json      # the same series as FRED carries it
```

Real GDP growth from BEA's table and from FRED's mirror of it:

```bash
dismal bea latest NIPA -t T10101 -F Q --columns series_id,period,value --format json
dismal fred data A191RL1Q225SBEA --years 2 --format json
```

Headline inflation three ways: BLS computes the 12-month change, FRED
transforms server-side, BEA gives the PCE price index:

```bash
dismal bls latest CUUR0000SA0 --calculations --columns series_id,date,value,pct_change_12 -f json
dismal fred latest CPIAUCSL --units pc1 -f json
dismal bea latest NIPA -t T20804 -F M --columns series_id,series_title,period,value -f json
```

Check every key and endpoint before a batch job, then pull from each source
into one directory:

```bash
dismal doctor >/dev/null || exit 1
dismal bls data --series-file bls-ids.txt --years 5 --format parquet -o data/bls.parquet
dismal bea data NIPA -t T10101 -F Q --years 5 --format parquet -o data/bea.parquet
dismal fred data --series-file fred-ids.txt --years 5 --format parquet -o data/fred.parquet
```

Inspect the configuration of one source or all of them:

```bash
dismal fred config | jq '.api_key, .limits'
dismal config | jq '.sources | map_values(.cache_dir)'
dismal cache info --format table
```
