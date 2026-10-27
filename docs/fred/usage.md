# Command reference

All commands accept `-h/--help`. Global options go before the command
(`-v` and `-q` may be placed either before or after `fred`):

```
dismal [-v|-vv] [-q] [--version] fred <command> [options]
```

| Global option | Effect |
| --- | --- |
| `-v, --verbose` | Log each HTTP request (endpoint, parameters, attempt) to stderr; `-vv` adds httpx wire logs. The key is never logged. |
| `-q, --quiet` | Suppress warnings and notes on stderr. Errors are still printed. |
| `-V, --version` | Print version and exit. |

Common output options (on every command that prints records):

| Option | Effect |
| --- | --- |
| `-f, --format {json,jsonl,csv,parquet,table}` | Output format. Default: `$FRED_FORMAT`, else `table` on a TTY and `json` otherwise. |
| `-o, --output PATH` | Write to a file instead of stdout (`-` = stdout). Parquet to stdout writes binary. |
| `--columns a,b,c` | Emit only these columns, in this order (applies to every format). |

---

## `dismal fred data SERIES_ID... [options]`

Fetch observations. Series ids may be separated by spaces or commas and are
upper-cased and de-duplicated. Add `--series-file PATH` (or `-S -` for stdin)
to read more ids, one per line; `#` starts a comment. One API request is made
per series (plus one per series with `--meta`); responses longer than 100,000
observations are paginated automatically.

### Time range

| Option | Meaning |
| --- | --- |
| `-s, --start SPEC` | Inclusive start. `YYYY`, `YYYY-MM`, `YYYY-MM-DD`, `YYYY-Qn`, `YYYY-Hn`. Sent as `observation_start`. |
| `-e, --end SPEC` | Inclusive end. Same forms; a coarse spec resolves to its last day (`2024` -> 2024-12-31, `2024-Q2` -> 2024-06-30). Sent as `observation_end`. |
| `-y, --years N` | The last N calendar years including the current one. Cannot be combined with `--start/--end`. |
| `--latest` | Only the newest observation of each series (one request, `sort_order=desc&limit=1`). No date flags allowed. |

With neither flag the whole history of the series is returned.

### Transformations

| Option | Meaning |
| --- | --- |
| `-u, --units U` | `lin` levels (default), `chg` change, `ch1` change from a year ago, `pch` percent change, `pc1` percent change from a year ago, `pca` compounded annual rate of change, `cch` continuously compounded rate of change, `cca` continuously compounded annual rate, `log` natural log. Computed by the API. |
| `-F, --frequency F` | Aggregate to a lower frequency: `d`, `w`, `bw`, `m`, `q`, `sa`, `a` (or `daily` ... `annual`); week-ending codes (`wef`, `wem`, ...) pass through. Raising a series' frequency is an API error (exit 3). |
| `--aggregation M` | How `--frequency` aggregates: `avg` (default), `sum` or `eop` (end of period). Needs `--frequency`. |
| `--as-of DATE` | Values as they were known on `DATE` (`YYYY-MM-DD`), from ALFRED: `realtime_start=realtime_end=DATE`. Adds `realtime_start` and `realtime_end` columns. |
| `-m, --meta` | Add `title`, `units`, `frequency`, `seasonal_adjustment` and `last_updated` columns (one extra request per series). |

### Shape

| Option | Meaning |
| --- | --- |
| `-L, --layout long\|wide` | `long` (default): one row per series and date. `wide`: one row per date, one value column per series. |
| `--descending` | Newest first. Default is oldest first. |
| `--raw` | Print API-shaped JSON: the request parameters, messages and, per series, the observations with their original string values. JSON only; the key is never included. |
| `--strict` | Exit 6 when any requested series has no observations (unknown id, empty range). |

### Examples

```bash
dismal fred data UNRATE --start 2020-01 --end 2024-12
dismal fred data CPIAUCSL CPILFESL --units pc1 --years 5 --layout wide -f csv -o inflation.csv
dismal fred data DGS10 --frequency m --aggregation eop --start 2015
dismal fred data GDPC1 --units pca --years 10 --columns date,value
dismal fred data PAYEMS --as-of 2024-02-02 --start 2023-06
cat ids.txt | dismal fred data -S - --years 1 --strict -f jsonl > out.jsonl
```

## `dismal fred latest SERIES_ID... [options]`

Alias for `dismal fred data --latest`; supports `--units`, `--frequency`,
`--aggregation`, `--as-of`, `--meta`, `--strict`, `--series-file` and the
output options.

## `dismal fred search QUERY... [options]`

Offline fuzzy search over the curated series catalog
(`src/dismal/fred/data/series_catalog.json`, ~150 series).

| Option | Meaning |
| --- | --- |
| `-n, --limit N` | Max results (default 20, `0` = all). |
| `--min-score S` | Minimum score 0-100 (default 55). |

Scores: 100 exact id, tag or title, or an everyday phrase the catalog knows
(`mortgage rates`, `jobs report`, `yield curve`, ignoring word order, plurals
and small words such as "of" and "in"); 92-100 every query word present;
lower scores are fuzzy (typos). Ties keep catalog order, so headline series
come first. Output columns: `kind, id, title, score, frequency, seasonal,
units, source`.

## `dismal fred series info SERIES_ID...`

Metadata for each series (live, one request per id): `id, title, frequency,
units, seasonal_adjustment, observation_start, observation_end,
last_updated, popularity`; `--notes` adds the notes. Unknown ids produce a
warning.

## `dismal fred series search QUERY... [options]`

The API's full-text search over every FRED series (live, one request).

| Option | Meaning |
| --- | --- |
| `-n, --limit N` | Max results, 1-1000 (default 20). |
| `--order-by X` | `search_rank` (relevance, default), `popularity`, `last_updated`, `title`, `series_id`, `units`, `frequency`, `seasonal_adjustment`, `observation_start`, `observation_end`, `realtime_start`, `realtime_end`, `group_popularity`. |
| `--sort asc\|desc` | Sort direction (the API's default depends on `--order-by`). |
| `-F, --frequency F` | Only series of this frequency (`d`, `w`, `bw`, `m`, `q`, `sa`, `a`). |
| `--seasonal sa\|nsa\|saar` | Only seasonally adjusted, not adjusted, or adjusted-annual-rate series. The API accepts one of `--frequency`/`--seasonal` per search. |
| `-t, --tag T` | Require this FRED tag (repeatable), e.g. `usa`, `monthly`, `bls`, `nsa`. |
| `--exclude-tag T` | Exclude this tag (repeatable), e.g. `discontinued`. |
| `--id` | Search ids instead of titles (prefix match), e.g. `dismal fred series search DGS --id`. |

Columns as for `series info`. When more series match than are shown, a note
on stderr gives the total.

## `dismal fred series vintages SERIES_ID`

Every date on which the series was released or revised (ALFRED). Columns:
`series_id, vintage_date`.

## `dismal fred series updates [-n N]`

Series most recently updated on FRED, newest first (live).

## `dismal fred releases [options]` / `releases show ID` / `releases series ID` / `releases dates`

`dismal fred releases` lists every release (cached 7 days; `--refresh` re-fetches,
`-q/--query` fuzzy-filters by name): `id, name, press_release, link`.
`releases show 53` prints one release's metadata as JSON. `releases series
53 [-n N]` lists the series published in a release. `releases dates [--days
N]` lists the release calendar for the next N days (default 14; negative for
the past): `date, release_id, release_name`.

## `dismal fred categories` / `categories children ID` / `categories series ID`

`dismal fred categories` lists the top-level categories (cached 7 days;
`-q/--query` filters); `categories children 10` the children of a category;
`categories series 32992 [-n N]` the series in a category.

## `dismal fred config`, `dismal fred doctor`

`config` prints the effective settings as JSON (key masked) including the
API's limits. `doctor` adds live checks (one `/sources` request) and exits
non-zero when unhealthy: 7 without a key (or with a rejected one), otherwise
the exit code of the failure (3 API, 4 rate limit, 5 network).

## `dismal fred cache info|clear`

Shows or deletes cached files under `FRED_CACHE_DIR`.

## `dismal fred version [--short]`

Prints `dismal X.Y.Z (python ...)`, or only `X.Y.Z` with `--short`.

## Shell completion

`dismal --install-completion` installs completion for the current shell;
`dismal --show-completion` prints it.
