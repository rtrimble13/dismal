# Finding and reading BLS series ids

Every BLS time series has an id such as `LNS14000000` (unemployment rate) or
`CUUR0000SA0` (CPI-U, all items). The API has no search endpoint, so `dismal bls`
offers several routes to an id.

## 1. Offline fuzzy search: `dismal bls search`

```bash
dismal bls search "core cpi"
dismal bls search unemploymnt rate          # typos tolerated
dismal bls search "price of eggs"           # everyday phrases, any word order
dismal bls search "job openings" --kind all # series and surveys
dismal bls search california --survey LA    # only Local Area Unemployment series
```

Searches a curated catalog of about 130 widely used series (CPI, average
prices, CPS labour force, CES payrolls and earnings, state unemployment and
employment, PPI, import/export prices, ECI, JOLTS, productivity). It is
deliberately small and hand-checked; it is not the universe of BLS series.
Contributions to `src/dismal/bls/data/series_catalog.json` are welcome; see
[development.md](../development.md#adding-a-series-to-the-curated-catalog) for
tags and everyday-phrase aliases.

## 2. Exhaustive per-survey directories: `dismal bls series list`

```bash
dismal bls series list --survey AP --query "eggs"
dismal bls series list --survey CU --query "gasoline" --min-score 70
dismal bls series list --survey LN --limit 0 -f csv -o ln_series.csv
```

Downloads the survey's `*.series` flat file from `download.bls.gov` (cached 30
days) and fuzzy-filters it. These directories list *every* series with its
dimension codes and date coverage. BLS requires a descriptive `User-Agent`
for these downloads; set `BLS_USER_AGENT="my-project (me@example.com)"` if you
receive HTTP 403.

## 3. Popular series: `dismal bls popular`

```bash
dismal bls popular
dismal bls popular --survey CE --catalog
```

## 4. Describe an id: `dismal bls series info`

```bash
dismal bls series info CUUR0000SA0 LNS14000000
```

Returns the catalog metadata (needs a key) and the latest observation.

## 5. Survey listing: `dismal bls surveys`

```bash
dismal bls surveys
dismal bls surveys --query "producer price"
dismal bls surveys show WP
```

## Reading an id

The first two characters are the survey abbreviation; for most surveys the
third is the seasonal adjustment code (`S` adjusted, `U` not adjusted). The
rest encodes survey-specific dimensions. Examples:

| Id | Survey | Reading |
| --- | --- | --- |
| `CUUR0000SA0` | CU (CPI-U) | `U` not seasonally adjusted, `R` regular periodicity, area `0000` U.S. city average, item `SA0` all items |
| `CUSR0000SA0L1E` | CU | seasonally adjusted, item `SA0L1E` all items less food and energy |
| `LNS14000000` | LN (CPS) | `S` adjusted, `14` unemployment rate, demographic code `000000` total |
| `CES0000000001` | CE (payrolls) | `S` adjusted, industry `00000000` total nonfarm, data type `01` all employees |
| `CES0500000003` | CE | industry `05000000` total private, data type `03` average hourly earnings |
| `LASST060000000000003` | LA | `S` adjusted, `ST06` California (FIPS 06), measure `03` unemployment rate |
| `SMS06000000000000001` | SM | state `06`, area `00000`, supersector `00000000`, data type `01` employees |
| `WPSFD4` | WP (PPI) | `S` adjusted, commodity `FD4` final demand |
| `JTS000000000000000JOL` | JT (JOLTS) | `S` adjusted, industry `000000` total nonfarm, `JO` job openings, `L` level (`R` rate) |
| `PRS85006092` | PR | nonfarm business sector `8500`, measure `6092` output per hour, % change at annual rate |
| `APU0000708111` | AP | area `0000`, item `708111` eggs, grade A, large, per dozen |

Each survey documents its own format at
<https://www.bls.gov/help/hlpforma.htm>. The flat-file directories (`dismal bls
series list`) include the dimension code columns, and the companion files
`<xx>.area`, `<xx>.item`, etc. on `download.bls.gov/pub/time.series/<xx>/`
spell out each code.

## Frequencies

Most CPI, CPS, CES, PPI and JOLTS series are monthly; ECI and productivity
series are quarterly; some CPI area indexes are bimonthly or semiannual
(`S01`/`S02`). `--frequency` filters rows after download; `--annual-average`
adds `M13`/`Q05` annual-average rows for series that publish them.
