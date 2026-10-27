# Command reference

All commands accept `-h/--help`. Global options go before the command, either
before or after the `bls` source:

```
dismal [-v|-vv] [-q] [--version] bls <command> [options]
dismal bls [-v|-vv] [-q] <command> [options]
```

| Global option | Effect |
| --- | --- |
| `-v, --verbose` | Log each HTTP request (method, path, attempt) to stderr; `-vv` adds httpx wire logs. |
| `-q, --quiet` | Suppress warnings and notes on stderr. Errors are still printed. |
| `-V, --version` | Print version and exit (at the root: `dismal --version`). |

Common output options (on every command that prints records):

| Option | Effect |
| --- | --- |
| `-f, --format {json,jsonl,csv,parquet,table}` | Output format. Default: `$BLS_FORMAT`, else `table` on a TTY and `json` otherwise. |
| `-o, --output PATH` | Write to a file instead of stdout (`-` = stdout). Parquet to stdout writes binary. |
| `--columns a,b,c` | Emit only these columns, in this order (applies to every format). |

---

## `dismal bls data SERIES_ID... [options]`

Fetch observations. Series ids may be separated by spaces or commas and are
upper-cased and de-duplicated. Add `--series-file PATH` (or `-S -` for stdin)
to read more ids, one per line; `#` starts a comment.

### Time range

| Option | Meaning |
| --- | --- |
| `-s, --start SPEC` | Inclusive start. `YYYY`, `YYYY-MM`, `YYYY-MM-DD`, `YYYY-Qn`, `YYYY-Hn`. |
| `-e, --end SPEC` | Inclusive end. Same forms; a coarse spec resolves to its last month (`2024` -> Dec 2024, `2024-Q2` -> Jun 2024). |
| `-y, --years N` | The last N calendar years including the current one. Cannot be combined with `--start/--end`. |
| `--latest` | Only the newest observation of each series (no date flags allowed). |

With neither flag the API's default applies: the three most recent years.
`--start` alone runs to the current year; `--end` alone covers the three years
ending there. Ranges longer than the per-request limit (20 years with a key,
10 without) are split into several requests and merged.

A period is kept if any part of it overlaps the range. Example: `--start
2020-05 --end 2020-Q3` on a quarterly series keeps Q2 and Q3 2020.

### Content

| Option | Meaning |
| --- | --- |
| `-F, --frequency F` | Keep only `monthly`, `quarterly`, `semiannual` or `annual` rows. Repeatable. |
| `-A, --annual-average` | Ask the API for annual averages (`M13`, `Q05`, `S03`). Adds an `annual_average` column. |
| `-c, --catalog` | Add catalog metadata columns (`series_title`, `survey_name`, `seasonality`, ...). Requires `BLS_API_KEY`; the API ignores it otherwise. |
| `--calculations` | Add `net_change_{1,3,6,12}` and `pct_change_{1,3,6,12}` columns. |
| `--aspects` | Include the API's `aspects` list (JSON string in CSV). |

### Shape

| Option | Meaning |
| --- | --- |
| `-L, --layout long\|wide` | `long` (default): one row per series and period. `wide`: one row per period, one value column per series. |
| `--descending` | Newest first. Default is oldest first (the API returns newest first; the CLI sorts chronologically). |
| `--raw` | Print the API-shaped JSON (`status`, `Results.series[].data[]`), merged across split requests and after client-side filtering. JSON only. |
| `--strict` | Exit 6 when any requested series has no observations after filtering. |

### Examples

```bash
dismal bls data LNS14000000 --start 2020-01 --end 2024-12
dismal bls data CUUR0000SA0 CUSR0000SA0 --years 5 --layout wide -f csv -o cpi.csv
dismal bls data CES0000000001 --calculations --latest --columns series_id,date,value,net_change_1
dismal bls data PRS85006092 -s 2010 -e 2024 -F quarterly -A -F annual
cat ids.txt | dismal bls data -S - --years 1 --strict -f jsonl > out.jsonl
```

## `dismal bls latest SERIES_ID... [options]`

Alias for `dismal bls data --latest`; supports `--catalog`, `--calculations`,
`--strict`, `--series-file` and the output options.

## `dismal bls search QUERY... [options]`

Offline fuzzy search over the curated series catalog
(`src/dismal/bls/data/series_catalog.json`, ~130 series) and the survey list.

| Option | Meaning |
| --- | --- |
| `-u, --survey XX` | Only series of this survey. |
| `-k, --kind series\|surveys\|all` | What to search (default `series`). |
| `-n, --limit N` | Max results (default 20, `0` = all). |
| `--min-score S` | Minimum score 0-100 (default 55). |

Scores: 100 exact id/tag/title or an everyday phrase the catalog knows
(`grocery prices`, `wage growth`, ignoring word order, plurals and small words
such as "of" and "in"); 92-100 every query word present; lower scores are fuzzy
(typos). Ties keep catalog order, so headline national series come
first. Output columns: `kind, id, title, survey, score, frequency, seasonal, units`.

## `dismal bls surveys [options]` / `dismal bls surveys show ABBR`

Lists surveys from the cached live list when one exists (`--refresh` fetches
and caches it), otherwise from the bundled snapshot. `-q/--query` fuzzy-filters
by name or abbreviation. `surveys show CU` prints the API's metadata object for
a survey (live request).

## `dismal bls popular [--survey XX] [--catalog]`

Series BLS lists as popular (live). `--catalog` fetches titles with one extra
data request (needs a key).

## `dismal bls series list --survey XX [options]`

Every series of a survey, parsed from the BLS flat-file directory
`https://download.bls.gov/pub/time.series/<xx>/<xx>.series` (cached 30 days).

| Option | Meaning |
| --- | --- |
| `-q, --query TEXT` | Fuzzy-filter by title/id; adds a `score` column. |
| `-n, --limit N` | Max rows (default 50, `0` = all). |
| `--min-score S` | Default 60. |
| `--refresh` | Re-download the directory. |

Columns: `series_id`, `title`, then every column of the flat file (for CU:
`area_code`, `item_code`, `seasonal`, `periodicity_code`, `base_period`,
`begin_year`, `end_period`, ...). Some directories are large (OE is >100 MB);
narrow with `--query`.

## `dismal bls series info SERIES_ID...`

Catalog metadata (title, survey, seasonality and survey-specific dimensions)
plus the latest year/period/value for each series. Needs a key for the
metadata.

## `dismal bls config`, `dismal bls doctor`

`config` prints the effective settings as JSON (key masked) including the
request limits in force. `doctor` adds live checks (one `/surveys` request) and
exits 5 if the API is unreachable.

## `dismal bls cache info|clear`

Shows or deletes cached files under `BLS_CACHE_DIR`.

## `dismal bls version [--short]`

Prints `dismal X.Y.Z (python ...)`, or only `X.Y.Z` with `--short`.

## Shell completion

`dismal --install-completion` installs completion for the current shell;
`dismal --show-completion` prints it.
