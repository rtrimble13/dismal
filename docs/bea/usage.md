# Command reference

All commands accept `-h/--help`. Global options go before the command, either
before or after `bea`:

```
dismal [-v|-vv] [-q] [--version] bea <command> [options]
dismal bea [-v|-vv] [-q] <command> [options]
```

| Global option | Effect |
| --- | --- |
| `-v, --verbose` | Log each HTTP request (parameters, attempt) to stderr; `-vv` adds httpx wire logs. The key is never logged. |
| `-q, --quiet` | Suppress warnings and notes on stderr. Errors are still printed. |
| `-V, --version` | Print version and exit (accepted at the root: `dismal --version`). |

Common output options (on every command that prints records):

| Option | Effect |
| --- | --- |
| `-f, --format {json,jsonl,csv,parquet,table}` | Output format. Default: `$BEA_FORMAT`, else `table` on a TTY and `json` otherwise. |
| `-o, --output PATH` | Write to a file instead of stdout (`-` = stdout). Parquet to stdout writes binary. |
| `--columns a,b,c` | Emit only these columns, in this order (applies to every format). |

Dataset names are case-insensitive (`nipa`, `NIPA`); the CLI uses the official
spelling in requests and output.

---

## `dismal bea data DATASET [NAME=VALUE...] [options]`

Fetch observations (the API's `GetData`). The positional `NAME=VALUE` pairs
(or `-p/--param NAME=VALUE`) are passed to the API unchanged, so every
parameter of every dataset is reachable. Shortcuts cover the common ones:

| Option | Parameter | Notes |
| --- | --- | --- |
| `-t, --table T` | `TableName` (NIPA, NIUnderlyingDetail, FixedAssets, Regional) or `TableID` (GDPbyIndustry, UnderlyingGDPbyIndustry, InputOutput) | Repeatable, or comma separated: one request per table, results merged. |
| `-F, --frequency F` | `Frequency` | `A`/`Q`/`M` or `annual`/`quarterly`/`monthly`; ITA/IIP codes (`QSA`, `QNSA`) pass through. Repeatable. Also filters rows client-side for datasets without a `Frequency` parameter. |
| `-g, --geo G` | `GeoFips` | `STATE`, `COUNTY`, `MSA`, ... or FIPS codes. Repeatable. |
| `-l, --line N` | `LineCode` | Regional line code. |
| `-i, --industry I` | `Industry` | GDPbyIndustry; defaults to `ALL`. Repeatable. |

Required parameters that are missing produce a usage error (exit 2) naming
them; `dismal bea datasets show DATASET` lists every parameter the API knows.

### Time range

| Option | Meaning |
| --- | --- |
| `-s, --start SPEC` | Inclusive start. `YYYY`, `YYYY-MM`, `YYYY-MM-DD`, `YYYY-Qn`, `YYYY-Hn`, `YYYYQn`, `YYYYMnn`. |
| `-e, --end SPEC` | Inclusive end. Same forms; a coarse spec resolves to its last month (`2024` -> Dec 2024, `2024-Q2` -> Jun 2024). |
| `-y, --years N` | The last N calendar years including the current one. Cannot be combined with `--start/--end`. |
| `--latest` | Request the last three years and keep only the newest observation of each series (no date flags allowed). |
| `Year=...` | Pass the API's `Year` parameter yourself: a comma list, `ALL`/`X` (mapped to the dataset's all-years value) or `LAST5`/`LAST10` where the dataset supports them. Cannot be combined with the flags above. |

With none of these the last three calendar years are requested. `--start`
alone runs to the current year; `--end` alone covers the three years ending
there.

A period is kept if any part of it overlaps the range. Example: `--start
2024-05 --end 2024-Q3` on a quarterly table keeps Q2 and Q3 2024.

### Content and shape

| Option | Meaning |
| --- | --- |
| `--notes` | Add a `notes` column with the text of the table notes each row references (`note_ref`). |
| `-L, --layout long\|wide` | `long` (default): one row per series and period. `wide`: one row per period, one value column per series id. |
| `--descending` | Newest first. Default is oldest first. |
| `--raw` | Print the API-shaped JSON (`BEAAPI.Results.Data[]`, `Notes`, `Dimensions`), merged across tables and after client-side filtering, with the `UserID` removed. JSON only. |
| `--strict` | Exit 6 when any requested table (or the request as a whole) has no observations after filtering. |

### Examples

```bash
dismal bea data NIPA --table T10101 --frequency Q --start 2020 --end 2024-Q2
dismal bea data NIPA -t T10105 -t T10106 -F A --years 10 --layout wide -f csv -o gdp.csv
dismal bea data NIPA -t T20804 -F M --latest --columns series_id,series_title,period,value
dismal bea data Regional -t SAINC1 --line 3 --geo STATE --years 5 -f parquet -o pcpi.parquet
dismal bea data Regional TableName=CAINC1 LineCode=1 GeoFips=06037,06059 Year=LAST10
dismal bea data GDPbyIndustry -t 1 -F Q --industry 31G --start 2023
dismal bea data ITA Indicator=BalCurrAcct AreaOrCountry=AllCountries -F QSA --years 5
dismal bea data IIP TypeOfInvestment=Net Component=Pos -F A Year=ALL
dismal bea data FixedAssets -t FAAt101 --years 3
dismal bea data InputOutput -t 56 Year=2022 -f jsonl
```

## `dismal bea latest DATASET [NAME=VALUE...] [options]`

Alias for `dismal bea data --latest`; supports the parameter shortcuts, `--notes`,
`--strict` and the output options.

## `dismal bea search QUERY... [options]`

Offline fuzzy search over the curated table catalog
(`src/dismal/bea/data/catalog.json`, ~75 tables and indicators) and the dataset list.

| Option | Meaning |
| --- | --- |
| `-d, --dataset NAME` | Only tables of this dataset. |
| `-k, --kind tables\|datasets\|all` | What to search (default `tables`). |
| `-n, --limit N` | Max results (default 20, `0` = all). |
| `--min-score S` | Minimum score 0-100 (default 55). |

Scores: 100 exact id/tag/title; 92-100 every query word present; lower scores
are fuzzy (typos). Ties keep catalog order, so headline tables come first.
Output columns: `kind, id, title, dataset, score, frequency, units, command`;
`command` is a ready-to-run `dismal bea data` invocation.

## `dismal bea datasets [options]` / `dismal bea datasets show DATASET`

Lists datasets from the cached live list when one exists (`--refresh` fetches
and caches it), otherwise from the bundled snapshot. `-q/--query`
fuzzy-filters by name or description. `datasets show NIPA` lists the
dataset's parameters (`GetParameterList`, cached 7 days; `--refresh` to
re-fetch) with columns `parameter, required, multiple, all_value, default,
type, description`.

## `dismal bea tables list DATASET [options]`

Every table of a dataset, from `GetParameterValues` for `TableName`/`TableID`
(cached 7 days).

| Option | Meaning |
| --- | --- |
| `-q, --query TEXT` | Fuzzy-filter by title/id; adds a `score` column. |
| `-n, --limit N` | Max rows (default 50, `0` = all). |
| `--min-score S` | Default 60. |
| `--refresh` | Re-fetch the list. |

Columns: `table`, `title`, then any extra columns the API returns. Datasets
without tables (ITA, IIP, MNE, ...) are rejected with a pointer to `dismal bea
values`.

## `dismal bea tables show DATASET TABLE`

Describes the lines (series) of one table. For NIPA, NIUnderlyingDetail,
FixedAssets, GDPbyIndustry and UnderlyingGDPbyIndustry the table is fetched
for the last two years at every frequency (one request) and summarised as one
row per series: `series_id, series_title, <dimensions>, unit, unit_mult,
frequencies, latest_period, latest_value`. For Regional the valid `LineCode`
values of the table are listed (`line_code, description`).

## `dismal bea values DATASET PARAMETER [options]`

The valid values of any parameter (`GetParameterValues`, or
`GetParameterValuesFiltered` with `--filter`), cached 7 days.

| Option | Meaning |
| --- | --- |
| `-F, --filter NAME=VALUE` | Narrow by another parameter, e.g. `--filter TableName=SAINC1` for `LineCode`. Repeatable. |
| `-q, --query TEXT` | Fuzzy-filter by description/key; adds a `score` column. |
| `-n, --limit N` | Max rows (default 50, `0` = all). |
| `--refresh` | Re-fetch. |

Columns: `key`, `description`, then any extra columns (`Year` for NIPA tables
returns `FirstAnnualYear`, `LastQuarterlyYear`, ...).

## `dismal bea config`, `dismal bea doctor`

`config` prints the effective settings as JSON (key masked) including the
API's rate limits. `doctor` adds live checks (one `GetDataSetList` request)
and exits non-zero when unhealthy: 7 without a key (or with a rejected one),
otherwise the exit code of the failure (3 API, 4 rate limit, 5 network).
`dismal config` and `dismal doctor` run the same checks for every source
(`bls`, `bea`, `fred`) at once.

## `dismal bea cache info|clear`

Shows or deletes cached files under `BEA_CACHE_DIR`. `dismal cache info|clear`
does the same for every source.

## `dismal bea version [--short]`

Prints `dismal X.Y.Z (python ...)`, or only `X.Y.Z` with `--short`. The
version is the same for every source (`dismal version`, `dismal --version`).

## Shell completion

`dismal --install-completion` installs completion for the current shell;
`dismal --show-completion` prints it.
