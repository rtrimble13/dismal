# Practitioner's guide

How to use `dismal bls` to answer real questions with official U.S. labor and
price statistics.

This guide answers two questions: *what can I use `dismal bls` for?* and *how
would I use `dismal bls` to do X?* It is written for people doing research in a
terminal or a notebook, and it doubles as a reference for agents (skills,
coding assistants, scheduled jobs) that answer questions with BLS data.

It is about using the tool well, not about every flag. For those, see
[usage.md](usage.md) (command reference), [agents.md](agents.md) (the
machine contract: exit codes, schemas, budget) and
[series-ids.md](series-ids.md) (how ids are built).

**Agents:** read [section 7](#7-using-dismal-bls-from-an-agent) first, then use
[section 8](#8-question-playbook) as a lookup table and the recipes in
[section 5](#5-recipes-from-data-to-answers) as templates.

## Contents

1. [What you can answer with `dismal bls`](#1-what-you-can-answer-with-dismal-bls)
2. [The research workflow](#2-the-research-workflow)
3. [Finding the right series](#3-finding-the-right-series)
4. [Fetching exactly what you need](#4-fetching-exactly-what-you-need)
5. [Recipes: from data to answers](#5-recipes-from-data-to-answers)
6. [Reading BLS data correctly](#6-reading-bls-data-correctly)
7. [Using `dismal bls` from an agent](#7-using-dismal-bls-from-an-agent)
8. [Question playbook](#8-question-playbook)
9. [Troubleshooting](#9-troubleshooting)
10. [Further reading](#10-further-reading)

---

## 1. What you can answer with `dismal bls`

`dismal bls` reaches every time series BLS publishes through its Public Data API,
across the 30-plus surveys that `dismal bls surveys` lists. In practice that covers
prices, jobs, unemployment, wages, labor costs and productivity, nationally and
for states, metro areas and counties.

| Domain | Typical questions | Surveys | Good starting series |
| --- | --- | --- | --- |
| Consumer prices | What is inflation? How much have rents risen? What is $100 from 2000 worth today? What will the Social Security COLA be? | `CU` CPI-U, `CW` CPI-W, `SU` chained CPI, `AP` average prices | `CUUR0000SA0`, `CUSR0000SA0L1E`, `CUUR0000SAH1`, `CWUR0000SA0`, `APU0000708111` |
| Producer and trade prices | Are business input costs rising? What is happening to import prices? | `WP` PPI commodities, `PC` PPI industries, `EI` import/export | `WPSFD4`, `WPSFD49104`, `EIUIR` |
| People and unemployment (household survey) | What is the unemployment rate? How does it differ by race, sex, age or education? Is participation recovering? | `LN` Current Population Survey | `LNS14000000`, `LNS11300060`, `LNS13327709` |
| Jobs (establishment survey) | How many jobs were added? Which industries are growing? How long is the workweek? | `CE` Current Employment Statistics | `CES0000000001`, `CES0500000003` |
| Turnover | Are employers still hiring? Are workers quitting? Are layoffs rising? | `JT` JOLTS | `JTS000000000000000JOL`, `JTS000000000000000QUR` |
| Wages and compensation | Are wages keeping up with prices? How fast are labor costs rising? What does an occupation pay? | `CE`, `CI` ECI, `CM` employer costs, `LE` CPS earnings, `OE` occupational wages | `CES0500000003`, `CIU2020000000000A` |
| Geography | Which states have the highest unemployment? How is my county doing? What is inflation in my metro area? | `LA` local unemployment, `SM` state and metro jobs, `CU` (metro CPI), `EN` QCEW | `LASST480000000000003`, `SMS48000000000000001`, `CUURS49ASA0` |
| Productivity and costs | Is productivity accelerating? Are unit labor costs inflationary? | `PR`, `IP`, `MP` | `PRS85006092`, `PRS85006112` |
| Other programs | How do households spend? How do people use their time? How many workplace injuries or strikes? How many jobs are projected? | `CX`, `TU`, `IS`, `WS`, `EP`, `LU`, `BD` | find ids with `dismal bls series list` |

### What `dismal bls` is not for

Knowing the boundary saves time and prevents wrong answers.

- **Statistics from other agencies.** GDP and PCE inflation (BEA), interest
  rates (Federal Reserve), housing starts and retail sales (Census), and weekly
  jobless claims (Department of Labor's ETA, not BLS) are not here. Say so
  rather than substituting a BLS series.
- **Data as first published.** The API returns today's values for every
  period, after all revisions. For "what did the January report say at the
  time", use a real-time archive such as ALFRED (St. Louis Fed).
- **Microdata.** `dismal bls` returns published aggregates, not survey responses.
- **Release dates and narrative.** The release calendar, news-release text and
  some tables (for example CPI relative-importance weights) live on bls.gov,
  not in the API.
- **Forecasts.** Apart from the employment projections program (`EP`), BLS
  publishes measurements, not predictions.

---

## 2. The research workflow

Every question, simple or complex, goes through the same steps. Skipping the
first one is the most common source of wrong answers.

1. **Frame the question precisely.** Decide the items in the table below.
2. **Find candidate series** ([section 3](#3-finding-the-right-series)).
3. **Verify the series** is the measure you mean: title, seasonal adjustment,
   units, geography and date coverage.
4. **Fetch once**, with a range that covers any comparison you need
   ([section 4](#4-fetching-exactly-what-you-need)).
5. **Transform in code** (changes, ratios, real values, rankings). Do not do
   arithmetic by eye.
6. **Sanity-check** the result: period, units, magnitude, preliminary flags
   and gaps ([section 6](#6-reading-bls-data-correctly)).
7. **Report with provenance:** value, units, period, series id, seasonal
   adjustment, retrieval date and caveats
   ([section 7.4](#74-answer-template)).

| Decide | Options | Sensible default |
| --- | --- | --- |
| Measure | level (people, jobs), rate (%), index, average price ($) | what the question names; "inflation" means a CPI index change |
| Geography | U.S., region, state, metro, county | U.S. unless stated |
| Seasonal adjustment | seasonally adjusted (SA), not adjusted (NSA) | SA for month-to-month and recent trends; NSA for year-over-year CPI and contracts ([section 6.1](#61-seasonally-adjusted-or-not)) |
| Frequency | monthly, quarterly, semiannual, annual average | the series' native frequency |
| Time | latest, a range, full history | latest plus 12 months of context |
| Transformation | level, change, percent change, annualized rate, inflation-adjusted, ratio, rank | depends on the question; percent changes for indexes, point changes for rates |

---

## 3. Finding the right series

The API has no search endpoint, so `dismal bls` gives you a ladder of discovery
tools.
Start at the top; each step down covers more series and costs a little more.

| Step | Command | Cost | Covers |
| --- | --- | --- | --- |
| 1 | `dismal bls search "words"` | free, offline | ~130 curated headline series |
| 2 | `dismal bls search "words" --kind all`, `dismal bls surveys --query "words"` | free, offline | which survey a topic belongs to |
| 3 | `dismal bls series list --survey XX --query "words"` | one download per survey, cached 30 days; no API quota | every series in that survey |
| 4 | `dismal bls popular --survey XX` | 1 request | what BLS flags as popular |
| 5 | `dismal bls series info ID...` | 1 request | verify title, seasonality and latest value (metadata needs a key) |

### 3.1 Write queries in BLS vocabulary

The offline search matches words in series titles and curated tags, tolerates
typos and word order, and skips small words such as "of", "in" and "the". The
curated catalog also recognizes many everyday phrases as a whole, ignoring word
order and plurals. These score 100:

- **Prices:** `inflation rate`, `cost of living`, `grocery prices`,
  `food prices`, `gas prices`, `egg prices` (or `price of eggs`),
  `rent inflation`, `housing costs`, `health care costs`, `car prices`,
  `used car prices`, `electricity prices`, `regional inflation`,
  `chicago inflation` (or `inflation in chicago`).
- **Jobs:** `job growth`, `jobs added`, an industry plus `jobs`
  (`manufacturing jobs`, `construction jobs`), `hiring`, `quitting`,
  `open jobs`, `hours worked`.
- **Unemployment and pay:** `unemployment rate`, `real unemployment rate`
  (U-6), `wage growth`, `pay`, `salary`, `paycheck`, `worker productivity`.
- **Places in the catalog:** `texas jobs` or `jobs in texas`,
  `unemployment in ohio`. Other states are easiest to build from a pattern
  ([section 3.4](#34-build-ids-from-patterns)).

Beyond these, name the concept rather than asking a question. A word that
appears in no title or tag still counts against the match.

| You might type | What happens | Type instead |
| --- | --- | --- |
| `what is inflation`, `how much are eggs` | nothing: the question words count as misses | `inflation`, `egg prices` |
| `employment rate` | the unemployment rate, at 85, from word overlap | `employment population ratio` or `epop` |
| `airfare`, `teen jobs`, `wage growth texas` | nothing: not in the curated catalog | find the survey, then `dismal bls series list` or an id pattern ([sections 3.3-3.4](#33-go-beyond-the-curated-catalog-with-dismal-bls-series-list)) |
| `home prices`, `jobless claims` | nothing, correctly: BLS does not publish these | say so ([section 1](#what-dismal-bls-is-not-for)) |

Useful exact terms (all score 100): `core cpi`, `core ppi`, `u-6`, `epop`,
`jolts`, `quits`, `layoffs`, `vacancies`, `eci`, `cola`, `chained cpi`,
`average price`, `jobs report`, `nonfarm payrolls`, `prime age`, and state
names (`texas`, `ohio`, ...).

### 3.2 Read the score

| Score | Meaning | What to do |
| --- | --- | --- |
| 100 | exact id, tag, title or known everyday phrase | use it, after choosing among ties |
| ~92-99 | every query word found | almost always right; read the title |
| below ~90 | partial or fuzzy match | read titles; reformulate; or go to step 3 |
| nothing | no result above `--min-score` (55) | reformulate, then `dismal bls search ... --kind all` to find the survey |

Ties at 100 are normal and usually differ in one dimension, most often seasonal
adjustment (`CUUR0000SA0L1E` NSA vs `CUSR0000SA0L1E` SA) or demographic group.
Choose deliberately using the `seasonal` and `title` columns; do not just take
the first row.

```bash
dismal bls search "core cpi" --limit 4 --format csv --columns id,score,seasonal,title
```

### 3.3 Go beyond the curated catalog with `dismal bls series list`

When the catalog has nothing, find the survey, then search its complete
directory. The directory comes from `download.bls.gov`, which requires a
descriptive User-Agent:

```bash
export BLS_USER_AGENT="my-research (me@example.com)"

dismal bls search "occupational wages" --kind surveys          # -> OE
dismal bls series list --survey CU --query "all items denver" --limit 5
dismal bls series list --survey LA --query "travis county unemployment rate" --limit 5
dismal bls series list --survey AP --query "coffee" --limit 10
dismal bls series list --survey PC --query "hospitals" --limit 10
dismal bls series list --survey OE --query "registered nurses" --limit 10   # large download
```

Tips:

- Directories include each survey's dimension codes and date coverage. Look at
  one row first (`--limit 1 --format json`) to learn the column names, then
  select them with `--columns`. Columns vary by survey.
- Check `end_year` (where present) to avoid discontinued series, and
  `begin_year` to know how far back a series goes.
- Some directories are big (`OE`, `EN`). The first download is slow; later
  calls read the 30-day cache. Narrow with `--query`.
- To grep or join a directory yourself, export it once:
  `dismal bls series list --survey LN --limit 0 --format csv -o ln_series.csv`.

### 3.4 Build ids from patterns

Several surveys have regular ids, which is handy for "all states" or "every
industry" questions. [series-ids.md](series-ids.md) explains how to read ids;
these are the patterns you will use most.

| Survey | Pattern | Example |
| --- | --- | --- |
| `LA` state | `LASST` + 2-digit state FIPS + `00000000000` + measure (`03` unemployment rate, `04` unemployed, `05` employed, `06` labor force) | `LASST480000000000003` Texas unemployment rate, SA |
| `SM` state | `SMS` + FIPS + `00000` (statewide) + `00000000` (total nonfarm) + `01` (employees) | `SMS48000000000000001` Texas payroll jobs, SA |
| `CE` national | `CES` (or `CEU` for NSA) + 8-digit industry + 2-digit data type (`01` employees, `02` weekly hours, `03` hourly earnings, `08` hourly earnings of production and nonsupervisory employees, `11` weekly earnings) | `CES3000000003` manufacturing average hourly earnings |
| `CU` | `CU` + `S`/`U` (SA/NSA) + `R` (regular: monthly or bimonthly) or `S` (semiannual) + 4-character area + item code | `CUUR0400SA0` West region, all items |

CES supersector codes: `10` mining and logging, `20` construction, `30`
manufacturing, `40` trade, transportation and utilities, `50` information,
`55` financial activities, `60` professional and business services, `65`
education and health, `70` leisure and hospitality, `80` other services, `90`
government; `05` total private, `00` total nonfarm.

**Verify every constructed id** before relying on it. A wrong id does not fail
loudly; it simply returns no rows:

```bash
dismal bls series info CES3000000003 --format json        # title, seasonality, latest value
dismal bls latest CES3000000003 --strict --format json    # exit 6 if the id returns nothing
```

---

## 4. Fetching exactly what you need

### 4.1 Pick the time window

| Need | Flags | Notes |
| --- | --- | --- |
| The newest value | `dismal bls latest ID...` | one request per 50 ids, no matter how long the history |
| Recent context | `--years N` | the last N calendar years including this one |
| A specific span | `--start 2021-01 --end 2024-06` | inclusive; also `YYYY`, `YYYY-Qn`, `YYYY-Hn` |
| Everything since a date | `--start 2019-01` | runs to the current year |
| Full history | `--start 1948` (or the series' `begin_year`) | split into 20-year requests automatically |

With no date flags the API returns the three most recent years. A period is
kept when any part of it overlaps the range, so `--start 2020-06` keeps the
2020 annual value and Q2 2020.

**Fetch a cushion for comparisons.** If you will compute 12-month changes
yourself, start 12 months before the first row you need (13 months for a
change in a 12-month change). The same applies to rolling averages.

### 4.2 Let the API compute changes, when you have a key

`--calculations` adds `net_change_{1,3,6,12}` and `pct_change_{1,3,6,12}` to
each row, as BLS computes them. For monthly series the spans are months, so `pct_change_12` is the year-over-year percent
change and `net_change_1` the one-month change.

- Use `net_change_*` for rates (the unemployment rate rising from 4.0 to 4.2
  is +0.2 points; its `pct_change_1` of 5% is meaningless).
- For quarterly or other non-monthly series, compute changes from `value`
  yourself rather than assuming what the spans mean.
- `--calculations`, `--annual-average` and `--catalog` need `BLS_API_KEY`.
  Without a key, compute changes and averages yourself; every recipe below
  shows how.

### 4.3 Frequencies and annual averages

- `--frequency monthly|quarterly|semiannual|annual` keeps only rows of that
  kind (repeatable).
- `--annual-average` (`-A`) asks for BLS's own annual averages (`M13`, `Q05`,
  `S03`), flagged with `annual_average=true`. Combine with `--frequency annual`
  to get one row per year. The current year has no annual average until its
  last period is published.
- Series that are annual by nature return `A01` rows (frequency `annual`).
  These are not averages of sub-annual data, so they are never flagged as
  annual averages.

### 4.4 Shape and format

| Use | Flags |
| --- | --- |
| Analysis in pandas, R or SQL; several measures per series | default long layout, `--format json`, `csv` or `parquet` |
| A spreadsheet, a chart, or arithmetic across series | `--layout wide --format csv` (one column per series id) |
| Streaming, line-by-line processing, appending to logs | `--format jsonl` |
| A local data store | `--format parquet -o file.parquet` |
| Reading at a terminal | `--format table` (the default on a TTY) |
| Only some columns | `--columns series_id,date,value,pct_change_12` |

The wide layout carries only values: `--catalog` and `--calculations` columns
are dropped. Use long layout when you need them.

`dismal bls data` never caches observations, so every call costs quota. For
iterative analysis, pull once to Parquet or CSV and work from the file.

### 4.5 Budget your requests

Each `dismal bls data` call costs `ceil(series / 50) * ceil(years / 20)` requests with
a key (`/25` and `/10` without). The daily cap is 500 requests with a key and
25 without; it resets at midnight U.S. Eastern.

| Call | With key | Without key |
| --- | --- | --- |
| `dismal bls latest` with 10 ids | 1 | 1 |
| `dismal bls latest` with all 51 state unemployment rates | 2 | 3 |
| `dismal bls data` 1 id `--years 5` | 1 | 1 |
| `dismal bls data` 1 id `--start 1948` (79 years) | 4 | 8 |
| `dismal bls data` 120 ids, 1990-2024 | 6 | 20 |
| `dismal bls search`, `dismal bls surveys`, cached `dismal bls series list` | 0 | 0 |

Batch ids into one call, keep ranges to what you need, and prefer `latest`
for monitoring.

---

## 5. Recipes: from data to answers

Each recipe states the question, the series, the command and the arithmetic.
Series ids come from the curated catalog unless noted. Results change with
every release, so no outputs are shown.

### 5.1 Setup

```bash
export BLS_API_KEY=...        # free: https://data.bls.gov/registrationEngine/
export BLS_USER_AGENT="my-research (me@example.com)"   # for dismal bls series list
```

Simple answers need only `dismal bls` and `jq`. For arithmetic across rows or series,
a small pandas helper keeps the recipes short:

```python
import json
import subprocess

import pandas as pd


def bls(*args: str) -> pd.DataFrame:
    """Run a `dismal bls` command and return its JSON output as a DataFrame."""
    proc = subprocess.run(
        ["dismal", "bls", *args, "--format", "json"],
        capture_output=True,
        text=True,
        check=True,
    )
    df = pd.DataFrame(json.loads(proc.stdout))
    if "date" in df.columns:
        df["date"] = pd.to_datetime(df["date"])
    return df


def values(*args: str) -> pd.Series:
    """One series' values indexed by date (long layout, single id)."""
    return bls(*args).set_index("date")["value"]
```

Changes below are computed by shifting the *dates*
(`s.shift(12, freq="MS")`), not the rows, so a missing month produces a gap
instead of silently comparing the wrong months.

You can also skip the subprocess and use the library directly; see
[python-api.md](python-api.md).

### 5.2 Prices and inflation

#### What is the latest inflation rate?

BLS reports the 12-month change from not seasonally adjusted CPI and the
one-month change from seasonally adjusted CPI. Fetch both, headline and core:

```bash
dismal bls latest CUUR0000SA0 CUUR0000SA0L1E CUSR0000SA0 CUSR0000SA0L1E --calculations \
  --columns series_id,year,period_name,value,pct_change_1,pct_change_12 --format csv
```

Read `pct_change_12` from the `CUUR...` rows (year over year) and
`pct_change_1` from the `CUSR...` rows (month over month). Without a key:

```python
cpi = values("data", "CUUR0000SA0", "--years", "2")
yoy = (cpi / cpi.shift(12, freq="MS") - 1) * 100
print(yoy.dropna().tail(1).round(1))
```

#### Is inflation speeding up or slowing down?

Annualize short-run changes of the seasonally adjusted index and compare them
with the 12-month rate:

```python
core = values("data", "CUSR0000SA0L1E", "--years", "3")
ann_3m = ((core / core.shift(3, freq="MS")) ** 4 - 1) * 100
ann_6m = ((core / core.shift(6, freq="MS")) ** 2 - 1) * 100
yoy = (core / core.shift(12, freq="MS") - 1) * 100
print(pd.DataFrame({"3m_ann": ann_3m, "6m_ann": ann_6m, "12m": yoy}).dropna().tail(6).round(1))
```

Short-run rates above the 12-month rate mean inflation is accelerating.

#### How much have prices risen since a given date?

Divide index levels; do not add up monthly changes.

```bash
dismal bls data CUUR0000SAF11 --start 2021-01 --format json --columns date,value \
  | jq -r '"\(.[0].date) -> \(.[-1].date): \(((.[-1].value / .[0].value - 1) * 1000 | round) / 10)%"'
```

(`CUUR0000SAF11` is food at home, "groceries".) The answer is "from January
2021 to the latest month", so state the end month too.

#### What is $X from year Y worth today?

Scale by the ratio of CPI-U annual averages (or of two specific months):

```bash
dismal bls data CUUR0000SA0 --start 2000 --end 2025 --annual-average --frequency annual \
  --format json --columns year,value \
  | jq '(map(select(.year == 2025))[0].value / map(select(.year == 2000))[0].value) * 100'
```

That is what $100 of 2000 money is in 2025 dollars. Without a key, average
the twelve monthly values of each year yourself
(`cpi.groupby(cpi.index.year).mean()`, complete years only). Use the NSA
series: it is never revised, which is why contracts and escalation clauses
use it.

#### What is driving inflation?

Compare 12-month changes of the major components:

```bash
dismal bls latest CUUR0000SA0L1E CUUR0000SAF11 CUUR0000SEFV CUUR0000SA0E CUUR0000SAH1 \
  CUUR0000SACL1E CUUR0000SASLE CUUR0000SETA02 CUUR0000SAM --calculations \
  --columns series_id,year,period_name,pct_change_12 --format csv
```

A component's contribution to the headline rate also depends on its weight
(relative importance), which BLS publishes as separate tables, not through the
API. Without weights, say "rising fastest", not "contributing most".

#### How has the price of eggs (gasoline, milk, electricity) changed?

Average prices (`AP`) are in dollars, which is what people usually mean:

```bash
dismal bls data APU0000708111 APU000074714 --start 2019-01 --layout wide --format csv
```

`APU0000708111` is a dozen grade A large eggs, `APU000074714` a gallon of
regular gasoline; `dismal bls search "average price"` lists the rest. Average prices
are national, not seasonally adjusted, and not the same thing as the CPI index
for the item ([section 6.8](#68-average-prices-are-not-price-indexes)).

#### What will the Social Security COLA be?

The cost-of-living adjustment is the percent change in the average CPI-W (NSA)
for July-September over the same quarter of the previous year (when the
previous year also had a COLA), to one decimal place:

```python
w = values("data", "CWUR0000SA0", "--start", "2024-07", "--end", "2025-09")
q3_prev = round(w.loc["2024-07":"2024-09"].mean(), 3)
q3_now = round(w.loc["2025-07":"2025-09"].mean(), 3)
print(round((q3_now / q3_prev - 1) * 100, 1))
```

Before September data are out, the same arithmetic with the months available
gives a running estimate; say so when you report it.

#### Are producer and import prices rising?

```bash
dismal bls latest WPSFD4 WPSFD49104 EIUIR --calculations \
  --columns series_id,year,period_name,pct_change_1,pct_change_12 --format csv
```

`WPSFD4` is PPI final demand, `WPSFD49104` core PPI (less foods, energy and
trade services), `EIUIR` all import prices (NSA). Industry-level producer
prices are in `PC`: `dismal bls series list --survey PC --query "..."`.

### 5.3 Jobs and the labor market

#### How many jobs were added last month?

```bash
dismal bls latest CES0000000001 CES0500000001 --calculations \
  --columns series_id,year,period_name,value,net_change_1 --format csv
```

Values are thousands of jobs, so `net_change_1` of `150` means 150,000. The
latest two months are preliminary (footnote `P`) and will be revised; monthly
changes also carry sampling error, so compare with the 3-month average:

```python
jobs = values("data", "CES0000000001", "--years", "2")
monthly = jobs - jobs.shift(1, freq="MS")
print(pd.DataFrame({"change": monthly, "3m_avg": monthly.rolling(3).mean()}).dropna().tail(6))
```

#### Which industries are adding or losing jobs?

```bash
dismal bls latest CES1000000001 CES2000000001 CES3000000001 CES4000000001 CES5000000001 \
  CES5500000001 CES6000000001 CES6500000001 CES7000000001 CES8000000001 CES9000000001 \
  --calculations --columns series_id,year,period_name,value,net_change_1,net_change_12 \
  --format csv
```

The ids follow the supersector pattern in [section 3.4](#34-build-ids-from-patterns).
For detailed industries, search `dismal bls series list --survey CE --query "..."`.

#### Is the labor market cooling?

No single number answers this. Pull a small dashboard in one request:

```bash
dismal bls latest LNS14000000 LNS12300060 CES0000000001 JTS000000000000000JOR \
  JTS000000000000000QUR JTS000000000000000LDL LNS13008636 --calculations \
  --columns series_id,year,period_name,value,net_change_12 --format csv
```

Unemployment rate, prime-age employment-population ratio, payrolls, openings
rate, quits rate, layoffs and long-term unemployed. JOLTS (`JTS...`) is a month
behind the others, so the periods differ; report each with its own month.

A common recession signal is the Sahm rule: the 3-month average unemployment
rate rising 0.5 points or more above its low of the previous 12 months.

```python
u = values("data", "LNS14000000", "--years", "4")
ma3 = u.rolling(3).mean()
sahm = ma3 - ma3.shift(1).rolling(12).min()
print(sahm.dropna().tail(6).round(2))   # >= 0.50 triggers
```

The rolling windows count rows: if a month is missing (a null value or a gap),
check the affected windows before trusting the result.

#### How tight is the labor market?

Job openings per unemployed person; both series are SA and in thousands:

```python
w = bls("data", "JTS000000000000000JOL", "LNS13000000", "--years", "5",
        "--layout", "wide").set_index("date").dropna()
print((w["JTS000000000000000JOL"] / w["LNS13000000"]).tail(6).round(2))
```

`dropna()` removes the latest month(s) where unemployment is out but JOLTS is
not yet. Above 1 means more openings than unemployed people. For a Beveridge
curve, plot `JTS000000000000000JOR` (openings rate) against `LNS14000000`.

#### How do unemployment rates differ across groups?

```bash
dismal bls data LNS14000003 LNS14000006 LNS14000009 LNS14032183 --years 3 \
  --layout wide --format csv
```

White, Black, Hispanic and Asian unemployment rates; subtract columns for the
gap in percentage points. Other groups: `LNS14000001`/`LNS14000002` (men,
women), `LNS14000012` (16-19), `LNS14027660`/`LNS14027662` (less than high
school, bachelor's and higher). Smaller groups have larger sampling error;
compare 3-month averages rather than single months.

#### When was unemployment last this low (or high)?

Fetch the full history (4 requests with a key) and search it:

```python
u = values("data", "LNS14000000", "--start", "1948")
now, prior = u.iloc[-1], u.iloc[:-1]
print(u.index[-1].date(), now, "last at or below this:", prior[prior <= now].index.max().date())
```

### 5.4 Wages and compensation

#### Are real wages rising?

Deflate average hourly earnings by CPI. BLS's own real-earnings figures use
CPI-U for all employees and CPI-W for production and nonsupervisory employees;
both SA here:

```python
w = bls("data", "CES0500000003", "CUSR0000SA0", "--start", "2019-01",
        "--layout", "wide").set_index("date").dropna()
real = w["CES0500000003"] / w["CUSR0000SA0"] * w["CUSR0000SA0"].iloc[-1]  # latest-month dollars
real_yoy = (real / real.shift(12, freq="MS") - 1) * 100
print(real_yoy.dropna().tail(6).round(1))
```

`dropna()` matters: earnings for a month come out about a week before that
month's CPI. Positive `real_yoy` means pay is outpacing prices.

#### How fast are wages and labor costs growing?

Two measures, for two purposes:

- **Average hourly earnings** (`CES0500000003`): monthly and timely, but
  shifts with the mix of jobs (it jumped in 2020 because low-paid jobs
  disappeared). Use `--calculations` and `pct_change_12`.
- **Employment Cost Index** (`CIU2020000000000A` private wages and salaries,
  `CIU1010000000000A` total compensation, all civilian): quarterly and holds
  the job mix fixed, so it is the better gauge of underlying wage pressure.
  These ECI series are *already* 12-month percent changes: report `value`
  directly and do not compute a percent change of them.

```bash
dismal bls data CIU2020000000000A CIU1010000000000A --years 3 --format csv \
  --columns series_id,year,period_name,value
```

#### What does an occupation pay?

Occupational wages (`OE`) are a large directory; search it:

```bash
dismal bls series list --survey OE --query "registered nurses annual mean wage" --limit 10
```

Pick the row for the geography and industry you need, then `dismal bls latest ID`.
OEWS is an annual cross-section (May reference period); the API typically
holds only the most recent estimates, so it suits "what does X earn" better
than "how has X's pay changed".

### 5.5 States, metros and counties

#### Rank states by unemployment rate

Build the 51 ids (50 states and DC) from FIPS codes and fetch them in one call:

```bash
printf 'LASST%s0000000000003\n' 01 02 04 05 06 08 09 10 11 12 13 15 16 17 18 19 20 \
  21 22 23 24 25 26 27 28 29 30 31 32 33 34 35 36 37 38 39 40 41 42 44 45 46 47 48 \
  49 50 51 53 54 55 56 > state_unrate.txt

dismal bls latest -S state_unrate.txt --catalog --strict --format json \
  | jq -r 'sort_by(.value) | reverse | .[:10][] | "\(.value)\t\(.series_title // .series_id)"'
```

Two requests with a key. Without a key, drop `--catalog` and read the state
FIPS code from characters 6-7 of the id (`.series_id[5:7]` in jq). For payroll
jobs swap in `SMS%s000000000000001`. State data come out a couple of weeks
after the national figures, so the latest month may lag `LNS14000000`.

#### Compare a state with the nation over time

```bash
dismal bls data LASST060000000000003 LNS14000000 --start 2019-01 --layout wide --format csv
```

#### Metro-area inflation

```bash
dismal bls series list --survey CU --query "all items denver" --limit 5
```

Only about two dozen metro areas have a CPI. Many are published every other
month, or only twice a year (`periodicity_code` `S`, periods `S01`/`S02`), so
compare like periods: the same month a year earlier, or `S01` with `S01`. Metro CPIs
are NSA and noisier than the national index.

#### County or metro unemployment

```bash
dismal bls series list --survey LA --query "travis county unemployment rate" --limit 5
```

Most sub-state series are not seasonally adjusted (`LAU...`), so compare with
the same month a year earlier, not the previous month.

#### County jobs and wages by industry

The Quarterly Census of Employment and Wages (`EN`) is a near-complete count
of jobs and pay by county and industry, published about five to six months
after the quarter ends. It is a large directory:

```bash
dismal bls series list --survey EN --query "..." --limit 20
```

### 5.6 Productivity and long history

#### How fast is productivity growing?

`PRS85006092` is already the quarterly change at an annual rate. For annual
growth, average the index (`PRS85006093`, 2017=100) by year and compare years:

```python
idx = values("data", "PRS85006093", "--start", "2015")
annual = idx.groupby(idx.index.year).agg(["mean", "count"])
annual = annual[annual["count"] == 4]["mean"]          # complete years only
print((annual.pct_change() * 100).round(1))
```

Pair with unit labor costs (`PRS85006112`, `PRS85006113`): labor costs rising
faster than productivity put upward pressure on prices.

#### Working with decades of history

Ranges longer than 20 years are split into several requests and merged for
you; budget roughly one request per 20 years per 50 series. Pull long history
once, store it, and refresh only recent years afterwards
([section 5.7](#57-monitoring-and-pipelines)). Watch for breaks in long series
([section 6.7](#67-gaps-breaks-and-missing-values)).

### 5.7 Monitoring and pipelines

#### Has anything new been released?

Keep a watchlist and compare the latest periods with the last run:

```bash
touch latest.jsonl
dismal bls latest -S watchlist.txt --strict --format jsonl \
  --columns series_id,year,period,value > latest.new.jsonl || exit
if ! cmp -s latest.new.jsonl latest.jsonl; then
  diff latest.jsonl latest.new.jsonl || true   # new periods or revised values
  mv latest.new.jsonl latest.jsonl
fi
```

`|| exit` keeps a failed call (quota, network) from replacing the last good
snapshot. One request per 50 ids, so it is cheap to run daily. Most BLS releases come
out at 8:30 a.m. Eastern.

#### Keep a local data set current

Revisions mean appending only the newest row leaves stale history behind.
Each run, re-pull a recent window that covers the revision period (two years
is safe for most programs) and replace those rows; pull deep history only
once.

```bash
dismal bls data -S ids.txt --years 2 --strict --format parquet -o recent.parquet
```

[`examples/bls/github-actions/weekly-pull.yml`](../../examples/bls/github-actions/weekly-pull.yml)
is a scheduled workflow that does this and commits the files.

---

## 6. Reading BLS data correctly

### 6.1 Seasonally adjusted or not?

Seasonal adjustment removes predictable calendar patterns (holiday hiring,
summer jobs, heating fuel prices). The third character of most ids is `S` for
adjusted and `U` for not adjusted.

| Question | Use | Why |
| --- | --- | --- |
| Change from last month, 3- or 6-month trends | SA | NSA month-to-month moves are mostly seasonal |
| Change from a year ago | NSA for CPI (BLS's headline 12-month rate); either for most others | seasons cancel over 12 months |
| A level for a contract, escalation clause or COLA | NSA | never revised |
| States, metros, counties | whatever exists; often only NSA | compare with the same month a year earlier |
| Annual averages | NSA | annual averages are computed from unadjusted data |

When search returns both and the question does not say, pick by this table and
state your choice in the answer.

### 6.2 Levels, rates, indexes and changes

- **Percent vs percentage points.** Rates (unemployment, participation,
  openings rate) change by *points*. Use `net_change_*` for rates and
  `pct_change_*` for levels, indexes and prices.
- **Some series are already changes.** ECI series ending in `A` are 12-month
  percent changes; `PRS85006092` is a percent change at an annual rate. Report
  the value; do not take a change of a change unless you mean to.
- **Index levels are not comparable across series.** CPI components have
  different base periods (`1982-84=100`, `Dec 1997=100`, ...). Compare percent
  changes, or rebase each to a common period (for a date-indexed series `s`:
  `s / s.loc["2020-01-01"] * 100`).
- **Units.** CES and CPS levels and JOLTS levels are in thousands. Average
  prices are dollars per unit (dozen, gallon, pound, kWh). `dismal bls search` shows a
  `units` column for catalog series; `--catalog` adds metadata for any series.

### 6.3 Revisions and preliminary values

The API always returns the current vintage. A value you pulled last month may
have changed since.

- **Payroll jobs (`CE`, `SM`)**: each month's estimate is revised in each of
  the next two monthly releases; all series are benchmarked once a year (the
  national benchmark appears with January data in early February). Preliminary
  values carry footnote `P`.
- **CPI (`CU`, `CW`)**: NSA indexes are not revised. Seasonal factors are
  recalculated each February, revising five years of SA data.
- **Chained CPI (`SU`)**: published as preliminary and revised for about a
  year before becoming final.
- **JOLTS, state and local data (`JT`, `LA`, `SM`)**: revised the following
  month and in annual updates.

Practice: check `footnotes` for `P`; record the retrieval date with every
result; for historical "as reported" questions use a real-time archive (ALFRED).

### 6.4 Release timing

"Latest" is the latest *published* period, and it differs by program.
Approximate lags (see the BLS release calendar for exact dates):

| Program | Surveys | Published |
| --- | --- | --- |
| Employment Situation (jobs, unemployment) | `CE`, `LN` | usually the first Friday after the reference month |
| CPI and average prices | `CU`, `CW`, `SU`, `AP` | about two weeks after the month ends |
| PPI, import/export prices | `WP`, `PC`, `EI` | about two weeks after the month ends |
| JOLTS | `JT` | about five weeks after the month ends (one month behind payrolls) |
| State and metro jobs and unemployment | `LA`, `SM` | about three weeks after the month (states); metros and counties later |
| Employment Cost Index | `CI` | about a month after the quarter |
| Productivity and costs | `PR` | about five weeks after the quarter, revised a month later |
| QCEW | `EN` | about five to six months after the quarter |
| Occupational wages | `OE` | annually, for May of the previous year |

Consequences: always report the period with the value; when combining series
(ratios, real values), align on dates and drop months where one side is
missing.

### 6.5 Two surveys, two job counts

The household survey (`LN`, the Current Population Survey) counts *people*,
including the self-employed, and gives the unemployment rate and demographic
detail. The establishment survey (`CE`) counts *jobs* on payrolls (a person
with two jobs counts twice) and gives industry detail, hours and earnings. They
can disagree for months. Use `CE` for "how many jobs", `LN` for "how many
people are working or looking".

### 6.6 Noise and sampling error

Most BLS series are survey estimates. A 0.1-point move in the unemployment rate
or a small change in monthly payrolls is often within sampling error, and
smaller groups and areas are noisier still. Prefer 3-month averages, year-over-
year changes and trends over single-month moves, and see each program's
technical note on bls.gov for its confidence intervals.

### 6.7 Gaps, breaks and missing values

- **Nulls.** `value` is `null` when BLS reports `-` or no estimate. Some
  periods were never collected (for example during the October-November 2025
  federal shutdown) and appear as nulls or missing rows. Date-aligned
  arithmetic (`shift(..., freq="MS")`) keeps a gap from shifting comparisons.
- **Level breaks.** CPS population controls are updated each January, which
  can shift household-survey levels (not usually rates) between December and
  January. BLS notes these in the release; compare rates rather than levels
  across a January when it matters.
- **Discontinued and redefined series.** Check `end_year` in
  `dismal bls series list`; discontinued PPI commodity series live in survey `WD`.
- **Irregular periodicity.** Some metro CPIs are bimonthly or semiannual;
  their missing months are by design, not gaps.

### 6.8 Average prices are not price indexes

`AP` average prices are dollars per unit for a narrowly defined item (a dozen
grade A large eggs). CPI item indexes (`CU`) measure the price change of a
broader category with quality adjustment. They usually move together but can
diverge; use `AP` for "how much does X cost" and `CU` for "how fast are X
prices rising".

### 6.9 Composition effects

Averages move when the mix changes. Average hourly earnings rose sharply in
spring 2020 because low-wage jobs disappeared, not because anyone got a raise.
The ECI holds the job mix fixed; prefer it for wage-pressure questions.

---

## 7. Using `dismal bls` from an agent

[agents.md](agents.md) is the contract (invariants, exit codes, schema);
[`examples/skill/SKILL.md`](../../examples/skill/SKILL.md) is a ready-made skill.
This section is the judgment layer on top: how to turn a user's question into
a correct, sourced answer with the fewest requests.

### 7.1 Protocol

1. **Classify the request.** Latest value, change, history, comparison,
   derived metric (real wages, ratios, rankings), or not BLS data (GDP,
   interest rates, jobless claims). For the last, say so and stop.
2. **Frame it** with the table in [section 2](#2-the-research-workflow): measure,
   geography, seasonal adjustment, frequency, time span, transformation.
3. **Resolve ids, cheapest first.**
   - Check the [question playbook](#8-question-playbook).
   - `dismal bls search "<concept>" --limit 5 --format json`. Accept the top hit if
     its score is at least 90 and it matches the framed geography and
     adjustment; choose among ties by the `seasonal` field.
   - Otherwise reformulate in BLS vocabulary
     ([section 3.1](#31-write-queries-in-bls-vocabulary)) and retry once, then
     use `dismal bls series list --survey XX --query ...`.
   - If several candidates remain plausible, show them to the user and ask.
   - Never invent an id. Ids built from a pattern must be verified
     (`dismal bls series info` or `dismal bls latest ID --strict`).
4. **Plan one fetch.** All ids in one call; the narrowest window that covers
   the comparison (plus a 12-month cushion when computing changes yourself);
   `latest` when only the current value matters. Estimate the request cost.
5. **Run it** with `--format json` (or `jsonl`) and `--strict`. Parse stdout
   only. Handle the exit code ([section 7.3](#73-exit-codes)).
6. **Compute in code**, never by eye. Align series on `date`.
7. **Sanity-check.** Is the period what you expected? Units right (thousands,
   index, percent)? Magnitude plausible? Any `null` values or `P` footnotes?
   Do the series' latest periods differ?
8. **Answer** with the template in [section 7.4](#74-answer-template).

### 7.2 Decision rules

| Situation | Rule |
| --- | --- |
| "Inflation" with no qualifier | CPI-U all items, 12-month change from NSA (`CUUR0000SA0`); mention core (`CUUR0000SA0L1E`) |
| Month-over-month anything | SA series |
| Year-over-year CPI | NSA series |
| "Jobs added" | `CES0000000001` `net_change_1`, in thousands |
| "Unemployment" with no qualifier | `LNS14000000` (U-3, SA) |
| "Wages" with no qualifier | `CES0500000003` for the latest month; ECI for underlying wage growth |
| A rate changed | report percentage points (`net_change_*`) |
| An index or level changed | report percent (`pct_change_*` or computed) |
| Series with different latest periods | report each with its own period; align before combining |
| A value footnoted `P` | say "preliminary" |
| No key (`dismal bls config` shows `api_key: "(not set)"`) | skip `--calculations`, `--annual-average` and `--catalog`; compute instead; budget 25 requests/day |
| User asks for a forecast | BLS data describe the past; say so, and offer the relevant history |

### 7.3 Exit codes

| Code | Do |
| --- | --- |
| 0 | parse stdout |
| 2 | your command is wrong: read stderr, fix flags, dates or `--columns` |
| 3 | an API or HTTP failure: read stderr; usually a bad parameter; an HTML "busy" page means BLS is refusing or overloaded: retry later |
| 4 | daily quota exhausted: stop and tell the user (resets at midnight Eastern) |
| 5 | network: retry once after a pause |
| 6 | (`--strict`) a series returned no data: re-check the id, the range and `--frequency` |
| 7 | configuration: fix the environment variables |

### 7.4 Answer template

```
<Measure> was <value> <units> in <period> (<seasonally adjusted | not seasonally adjusted>)<, preliminary>.
<Change, in points for rates or percent for levels and indexes, with the comparison period>.
<One caveat if it matters: revisions, sampling error, a different latest month, a gap>.
Source: U.S. Bureau of Labor Statistics, <program>, series <ID>; retrieved <YYYY-MM-DD>.
```

Always include the period and the series id; a number without them cannot be
checked. If you publish an application or analysis built on the API, BLS's
[terms of service](https://www.bls.gov/developers/termsOfService.htm) ask for
the statement "BLS.gov cannot vouch for the data or analyses derived from
these data after the data have been retrieved from BLS.gov."

### 7.5 Worked examples

**"What's the unemployment rate, and is it higher than a year ago?"**

```bash
dismal bls search "unemployment rate" --limit 3 --format json   # LNS14000000, 100, SA
dismal bls latest LNS14000000 --calculations --strict --format json \
  --columns series_id,year,period_name,value,net_change_12,footnotes
```

Answer: "The unemployment rate was {value}% in {period_name} {year}
(seasonally adjusted), {net_change_12:+} points from a year earlier. Source:
BLS Current Population Survey, series LNS14000000; retrieved {today}."

**"How much have grocery prices gone up since January 2021?"**

```bash
dismal bls search "food at home" --limit 3 --format json        # CUUR0000SAF11, 96.7, NSA
dismal bls data CUUR0000SAF11 --start 2021-01 --strict --format json --columns date,value \
  | jq '{from: .[0].date, to: .[-1].date, pct: ((.[-1].value / .[0].value - 1) * 100)}'
```

Answer with the percent to one decimal and the end month ("from January 2021
to {to}"), naming the series as CPI-U food at home, U.S. city average, NSA.

**"Which states have the highest unemployment right now?"**

Build the state ids ([section 5.5](#55-states-metros-and-counties)), run one
`dismal bls latest -S state_unrate.txt --catalog --strict --format json`, sort by
value, and report the top states with the month, noting that state figures are
seasonally adjusted and published later than the national rate.

**"What were initial jobless claims last week?"**

Not BLS data: weekly claims come from the Department of Labor's Employment and
Training Administration. Say so and offer the closest BLS measures (the
unemployment rate, JOLTS layoffs) instead of substituting one silently.

### 7.6 Anti-patterns

- Calling `dismal bls data` once per id in a loop (wastes quota; one call takes many
  ids).
- Fetching full history when the question needs the latest value.
- Re-fetching the same data within a task instead of keeping the parsed result.
- Taking the top search hit without checking seasonal adjustment and geography.
- Reporting `pct_change_*` of a rate, or a percent change of a series that is
  already a percent change.
- Comparing index levels across series with different bases.
- Combining series without aligning dates (JOLTS and CPI lag payrolls).
- Parsing stderr, or relying on the default output format.
- Naming catalog columns (`series_title`, ...) in `--columns` without a key:
  they do not exist and the command exits 2.
- Presenting preliminary or revised numbers without saying so.

---

## 8. Question playbook

Starting points for common questions. Ids are national, monthly and from the
curated catalog unless noted; patterns are explained in
[section 3.4](#34-build-ids-from-patterns).

| Question | Series | Notes |
| --- | --- | --- |
| Headline inflation, year over year | `CUUR0000SA0` | `pct_change_12` |
| Headline inflation, month over month | `CUSR0000SA0` | `pct_change_1` |
| Core inflation | `CUUR0000SA0L1E` (NSA), `CUSR0000SA0L1E` (SA) | all items less food and energy |
| Core goods / core services | `CUUR0000SACL1E`, `CUUR0000SASLE` | |
| Shelter, rent, owners' equivalent rent | `CUUR0000SAH1`, `CUUR0000SEHA`, `CUUR0000SEHC` | |
| Groceries, restaurants | `CUUR0000SAF11`, `CUUR0000SEFV` | |
| Energy, gasoline (index) | `CUUR0000SA0E`, `CUUR0000SETB01` | |
| New and used vehicles | `CUUR0000SETA01`, `CUUR0000SETA02` | |
| Medical care | `CUUR0000SAM` | |
| Price of eggs, gasoline, milk, bread, electricity ($) | `APU0000708111`, `APU000074714`, `APU0000709112`, `APU0000702111`, `APU000072610` | average prices, NSA |
| Inflation by region | `CUUR0100SA0`, `CUUR0200SA0`, `CUUR0300SA0`, `CUUR0400SA0` | Northeast, Midwest, South, West |
| Inflation in a metro | `CUURS12ASA0` (New York), `CUURS49ASA0` (Los Angeles), `CUURS23ASA0` (Chicago) | others: `dismal bls series list --survey CU` |
| Social Security COLA | `CWUR0000SA0` | Q3 average vs prior Q3 |
| Chained CPI | `SUUR0000SA0` | preliminary for about a year |
| Producer prices | `WPSFD4`, `WPSFD49104` (core) | |
| Import / export prices | `EIUIR`, `EIUIQ` | |
| Unemployment rate | `LNS14000000` | `net_change_*` in points |
| Broad underemployment (U-6) | `LNS13327709` | |
| Participation, prime-age participation | `LNS11300000`, `LNS11300060` | |
| Employment-population ratio, prime age | `LNS12300060` | a cleaner read than participation |
| Unemployment by race and ethnicity | `LNS14000003`, `LNS14000006`, `LNS14000009`, `LNS14032183` | White, Black, Hispanic, Asian |
| Unemployment by sex, age, education | `LNS14000001`, `LNS14000002`, `LNS14000012`, `LNS14027660`, `LNS14027662` | |
| Long-term unemployment, duration | `LNS13008636`, `LNS13008276` | thousands; median weeks |
| Involuntary part-time | `LNS12032194` | |
| Payroll jobs added | `CES0000000001` | `net_change_1`, thousands |
| Private payrolls | `CES0500000001` | |
| Jobs by industry | `CES{10,20,30,40,50,55,60,65,70,80,90}00000001` | pattern; `CES8000000001` is not in the catalog |
| Average hourly earnings | `CES0500000003`, `CES0500000008` | all employees; production and nonsupervisory |
| Average weekly hours | `CES0500000002` | |
| Job openings (level, rate) | `JTS000000000000000JOL`, `JTS000000000000000JOR` | one month behind payrolls |
| Hires, quits, layoffs | `JTS000000000000000HIR`, `JTS000000000000000QUR`, `JTS000000000000000LDL` | |
| Employment Cost Index | `CIU2020000000000A`, `CIU1010000000000A` | already 12-month % changes; quarterly |
| Productivity, unit labor costs | `PRS85006092`, `PRS85006112` | already % changes at annual rates; quarterly |
| State unemployment rate | `LASST{FIPS}0000000000003` | pattern; SA |
| State payroll jobs | `SMS{FIPS}000000000000001` | pattern; SA |
| County or metro unemployment | `dismal bls series list --survey LA --query "..."` | mostly NSA |
| County jobs and wages by industry | `dismal bls series list --survey EN --query "..."` | QCEW, quarterly, long lag |
| Wages by occupation | `dismal bls series list --survey OE --query "..."` | annual cross-section |

---

## 9. Troubleshooting

| Symptom | Likely cause | Fix |
| --- | --- | --- |
| `dismal bls search` finds nothing | question words, or the series is not in the curated catalog | reformulate ([section 3.1](#31-write-queries-in-bls-vocabulary)); then `--kind all` and `dismal bls series list` |
| Warning `no observations returned for X`, or exit 6 with `--strict` | wrong or discontinued id; range before the series begins; `--frequency` the series does not have | `dismal bls series info X`; check `begin_year`/`end_year` in `dismal bls series list`; widen the range |
| Exit 2 `unknown column(s)` | `--columns` names a column that was not produced (catalog fields without a key, calculation columns without `--calculations`) | the error lists the available columns |
| `--catalog` columns missing, with a warning | no `BLS_API_KEY` | set the key, or drop `--catalog` |
| Calculation columns are null | no key, or a gap in the data | set the key, or compute changes yourself with a 12-month cushion |
| Rows outside `--start/--end` | overlap rule: a quarter or year that overlaps the range is kept | add `--frequency monthly`, or filter by `date` |
| Exit 3 with an HTML "The BLS website is busy" page (HTTP 503) | BLS is overloaded or is refusing traffic from your network (seen from some cloud hosts) | retry later or from another network; `dismal bls -v ...` shows each attempt |
| HTTP 403 from `download.bls.gov` | missing descriptive User-Agent | `export BLS_USER_AGENT="my-project (me@example.com)"` |
| Exit 4 | daily request quota used up | wait for midnight Eastern; set a key for 500/day |
| `dismal bls series list` is slow | first download of a large directory | later calls use the 30-day cache |
| Output is a table in a script | the default format follows the terminal | always pass `--format` |
| `dismal bls surveys -q price` filters instead of going quiet | `-q` means `--query` on `surveys` and `series list` | put the global flag first: `dismal bls -q data ...` |
| Latest periods differ across series | different release schedules | expected; report each period |

`dismal bls doctor` checks the configuration and makes one live request; run it first
when something unexpected happens.

---

## 10. Further reading

In this repository:

- [usage.md](usage.md): every command and flag
- [agents.md](agents.md): the contract for automations and agents
- [series-ids.md](series-ids.md): how to read and find series ids
- [output-formats.md](output-formats.md): record schemas per format
- [configuration.md](configuration.md): environment variables, limits, caching
- [python-api.md](python-api.md): using `dismal.bls.BLSClient` directly

From BLS:

- [BLS Public Data API](https://www.bls.gov/developers/) and its
  [terms of service](https://www.bls.gov/developers/termsOfService.htm)
- [Release calendar](https://www.bls.gov/schedule/)
- [Series id formats by survey](https://www.bls.gov/help/hlpforma.htm)
- [Handbook of Methods](https://www.bls.gov/opub/hom/): how each program
  measures what it measures
- Program pages with technical notes: [CPI](https://www.bls.gov/cpi/),
  [CES](https://www.bls.gov/ces/), [CPS](https://www.bls.gov/cps/),
  [JOLTS](https://www.bls.gov/jlt/), [LAUS](https://www.bls.gov/lau/),
  [State and metro employment](https://www.bls.gov/sae/),
  [PPI](https://www.bls.gov/ppi/), [ECI](https://www.bls.gov/eci/),
  [Productivity](https://www.bls.gov/lpc/), [OEWS](https://www.bls.gov/oes/),
  [QCEW](https://www.bls.gov/cew/)

For data as originally published (vintages), see
[ALFRED](https://alfred.stlouisfed.org/) at the Federal Reserve Bank of St.
Louis.
