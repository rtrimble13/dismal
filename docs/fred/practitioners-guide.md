# Practitioner's guide

How to use `dismal fred` to answer real questions with the time series in FRED, the
Federal Reserve Bank of St. Louis database: growth, jobs, prices, interest
rates, money, markets, housing, trade and government, in the United States
and abroad, including what any series looked like on a past date.

This guide answers two questions: *what can I use `dismal fred` for?* and *how would
I use `dismal fred` to do X?* It is written for people doing research in a terminal
or a notebook, and it doubles as a reference for agents (skills, coding
assistants, scheduled jobs) that answer questions with FRED data. It is the
sibling of the
[`dismal bls`](../bls/practitioners-guide.md)
and [`dismal bea`](../bea/practitioners-guide.md)
practitioner's guides and follows the same layout.

It is about using the tool well, not about every flag. For those, see
[usage.md](usage.md) (command reference), [agents.md](agents.md) (the
machine contract: exit codes, schemas, budget) and
[series-ids.md](series-ids.md) (how ids are found and read).

**Agents:** read [section 7](#7-using-dismal-fred-from-an-agent) first, then use
[section 8](#8-question-playbook) as a lookup table and the recipes in
[section 5](#5-recipes-from-data-to-answers) as templates.

## Contents

1. [What you can answer with `dismal fred`](#1-what-you-can-answer-with-dismal-fred)
2. [The research workflow](#2-the-research-workflow)
3. [Finding the right series](#3-finding-the-right-series)
4. [Fetching exactly what you need](#4-fetching-exactly-what-you-need)
5. [Recipes: from data to answers](#5-recipes-from-data-to-answers)
6. [Reading FRED data correctly](#6-reading-fred-data-correctly)
7. [Using `dismal fred` from an agent](#7-using-dismal-fred-from-an-agent)
8. [Question playbook](#8-question-playbook)
9. [Troubleshooting](#9-troubleshooting)
10. [Further reading](#10-further-reading)

---

## 1. What you can answer with `dismal fred`

FRED collects more than 800,000 series from about a hundred sources: the
statistical agencies (BLS, BEA, Census), the Federal Reserve Board and the
reserve banks, Treasury, the OECD and IMF, market data vendors and
researchers. `dismal fred` reaches every one of them by id, with the API's own
transformations and the ALFRED archive of past vintages.

| Domain | Typical questions | Good starting series |
| --- | --- | --- |
| Growth and output | How fast is the economy growing? How big is GDP? Is factory output rising? | `A191RL1Q225SBEA` (real GDP growth), `GDPC1`, `GDP`, `INDPRO`, `TCU` |
| Jobs and unemployment | What is the unemployment rate? How many jobs were added? Are layoffs rising? | `UNRATE`, `PAYEMS`, `ICSA`, `JTSJOL`, `CIVPART`, `LNS12300060` |
| Prices and inflation | What is inflation? Core inflation? What do markets expect? | `CPIAUCSL`, `CPILFESL`, `PCEPI`, `PCEPILFE`, `PPIFIS`, `T10YIE`, `MICH` |
| Interest rates and the yield curve | Where is the fed funds rate? The 10-year yield? Is the curve inverted? What are mortgage rates? | `FEDFUNDS`, `DFF`, `DGS2`, `DGS10`, `T10Y2Y`, `DFII10`, `MORTGAGE30US`, `BAMLH0A0HYM2` |
| Money, credit and the Fed | How big is the Fed's balance sheet? Is M2 growing? Are consumers borrowing? | `WALCL`, `WRESBAL`, `RRPONTSYD`, `M2SL`, `TOTALSL`, `DRCCLACBS` |
| Markets and the dollar | How is the stock market doing? Is volatility up? How strong is the dollar? What is oil? | `SP500`, `VIXCLS`, `DTWEXBGS`, `DEXUSEU`, `DCOILWTICO` |
| Housing | Are builders building? Are home prices rising? | `HOUST`, `PERMIT`, `HSN1F`, `EXHOSLUSM495S`, `CSUSHPINSA`, `MSPUS`, `MSACSR` |
| Income, spending and saving | Is income keeping up? Are consumers spending? What is the saving rate? | `PI`, `DSPIC96`, `PCE`, `PSAVERT`, `RSAFS`, `UMCSENT` |
| Government and trade | How large is the debt? The deficit? The trade deficit? | `GFDEBTN`, `GFDEGDQ188S`, `FYFSD`, `MTSDS133FMS`, `A091RC1Q027SBEA`, `BOPGSTB` |
| Recession | Are we in a recession? What does the Sahm rule say? | `USREC`, `SAHMREALTIME`, `RECPROUSM156N` |
| States, countries | Unemployment in a state? Inflation in another country? | `CAUR`, `TXUR` (pattern `<ST>UR`); `dismal fred series search "<place> <measure>"` |

### What `dismal fred` is not for

Knowing the boundary saves time and prevents wrong answers.

- **The full detail of the source agencies.** FRED carries the headline BLS
  and BEA series and many detailed ones, but not every table or series, and
  its search does not know BLS survey codes or BEA table numbers. For
  exhaustive BLS or BEA work use [`dismal bls`](../bls/practitioners-guide.md)
  and [`dismal bea`](../bea/practitioners-guide.md); the ids FRED shares with
  them are listed in [series-ids.md](series-ids.md).
- **Licensed market data beyond a window.** The S&P 500, Dow Jones and some
  other vendor series are available for the most recent ten years only, and a
  few (LBMA gold prices) were withdrawn. `dismal fred series info` shows
  `observation_start`.
- **Intraday or real-time prices.** Daily series arrive the next business
  day.
- **Forecasts.** FRED carries a few published nowcasts and projections
  (search for them), but most series are measurements. Say so rather than
  extrapolating.
- **Release text and analysis.** The release itself, the methodology notes
  and the charts live on the sources' sites and on fred.stlouisfed.org; the
  series `notes` (`dismal fred series info --notes`) summarise them.
- **Microdata.** `dismal fred` returns published aggregates.

---

## 2. The research workflow

Every question, simple or complex, goes through the same steps. Skipping the
first one is the most common source of wrong answers.

1. **Frame the question precisely.** Decide the items in the table below.
2. **Find candidate series** ([section 3](#3-finding-the-right-series)).
3. **Verify the series** is the measure you mean: title, units, frequency,
   seasonal adjustment, coverage and last update (`dismal fred series info`).
4. **Fetch once**, with the window, transformation and frequency you need
   ([section 4](#4-fetching-exactly-what-you-need)).
5. **Transform in code** what the API did not (ratios, spreads, rolling
   averages, rankings). Do not do arithmetic by eye.
6. **Sanity-check** the result: period, units, magnitude, missing values,
   vintage ([section 6](#6-reading-fred-data-correctly)).
7. **Report with provenance:** value, units, period, series id, seasonal
   adjustment, vintage and retrieval date, with caveats
   ([section 7.4](#74-answer-template)).

| Decide | Options | Sensible default |
| --- | --- | --- |
| Measure | level, rate (%), index, price, count | what the question names; "inflation" means the 12-month change in a price index |
| Transformation | none, change, percent change, year-over-year, annualized, log | `--units pc1` for inflation and growth of levels; points (`ch1`/`chg`) for rates |
| Frequency | native, or aggregated to monthly/quarterly/annual | native for the latest value; monthly averages for comparisons across daily series |
| Aggregation | average, sum, end of period | average for rates and indexes; end of period for stocks and balances; sum for flows that add |
| Seasonal adjustment | SA, NSA, SAAR | SA for month-to-month; NSA for year-over-year CPI; what the source publishes |
| Vintage | current, or as of a date | current; `--as-of` for "what was known then" |
| Geography | U.S., state, country | U.S. unless stated |
| Time | latest, a range, full history | latest plus a year or two of context |

---

## 3. Finding the right series

FRED has excellent search, so the ladder is short. Start at the top; each
step down costs a request.

| Step | Command | Cost | Covers |
| --- | --- | --- | --- |
| 1 | `dismal fred search "words"` | free, offline | ~150 curated headline series, with everyday-phrase aliases |
| 2 | `dismal fred series search "words" [--order-by popularity] [filters]` | 1 request | every series in FRED |
| 3 | `dismal fred releases -q "words"`, `dismal fred releases series ID`, `dismal fred categories ...` | cached / 1 request | browse by publication or by topic |
| 4 | `dismal fred series info ID...` | 1 request per id | verify title, units, frequency, adjustment, coverage, last update |

### 3.1 Write queries in FRED vocabulary

The offline search matches words in series titles and curated tags, tolerates
typos and word order, skips small words ("of", "in", "the") and knows many
everyday phrases as a whole. These score 100:

- **Growth:** `gdp growth`, `real gdp`, `economic growth`, `industrial
  production`, `retail sales`, `consumer sentiment`.
- **Jobs:** `unemployment rate`, `jobs report`, `nonfarm payrolls`,
  `initial jobless claims`, `job openings`, `quits rate`, `labor force
  participation rate`, `prime age employment rate`, `wage growth`.
- **Prices:** `inflation rate`, `consumer price index`, `core inflation`,
  `core pce`, `pce inflation`, `producer prices`, `inflation expectations`,
  `oil prices`, `gas prices`, `food prices`, `rent inflation`.
- **Rates:** `fed funds rate`, `10 year treasury yield`, `2 year treasury
  yield`, `yield curve`, `real interest rate`, `mortgage rates`, `prime rate`,
  `credit spreads`.
- **Money and markets:** `money supply`, `fed balance sheet`, `bank
  reserves`, `stock market`, `vix`, `dollar index`, `euro exchange rate`.
- **Housing, fiscal, trade:** `housing starts`, `building permits`, `home
  prices`, `house prices`, `existing home sales`, `national debt`, `budget
  deficit`, `trade deficit`, `recession indicator`, `sahm rule`.

Beyond these, name the concept rather than asking a question. A word that
appears in no title or tag counts against the match.

| You might type | What happens | Type instead |
| --- | --- | --- |
| `what is inflation right now` | nothing: the question words count as misses | `inflation rate` |
| `interest rates` | several series tie at 100 (fed funds, Treasury yields, prime, mortgage) | name the rate: `fed funds rate`, `10 year treasury yield`, `mortgage rates` |
| `home prices` vs `house prices` | the median sales price (`MSPUS`) vs the Case-Shiller index (`CSUSHPINSA`) | pick by what you need: a dollar figure or an index |
| `gold price`, `bitcoin price` | nothing, correctly: not in the catalog (gold was withdrawn from FRED) | `dismal fred series search` if you must |
| `unemployment in ohio` | nothing offline: only a few states are in the catalog | `dismal fred data OHUR` (pattern `<ST>UR`) or `dismal fred series search "unemployment rate ohio"` |

### 3.2 Read the score

| Score | Meaning | What to do |
| --- | --- | --- |
| 100 | exact id, tag, title or known everyday phrase | use it, after choosing among ties |
| ~92-99 | every query word found | almost always right; read the title |
| below ~90 | partial or fuzzy match | read titles; reformulate; or go to step 2 |
| nothing | no result above `--min-score` (55) | reformulate, then `dismal fred series search` |

Ties at 100 are normal and usually differ in frequency or adjustment: the fed
funds rate is `FEDFUNDS` (monthly) and `DFF` (daily); the 10-year yield is
`DGS10` (daily) and `GS10` (monthly); the CPI is `CPIAUCSL` (SA) and
`CPIAUCNS` (NSA). Choose deliberately using the `frequency` and `seasonal`
columns; do not just take the first row.

```bash
dismal fred search "fed funds rate" --limit 4 --format csv --columns id,score,frequency,title
```

### 3.3 Search all of FRED

When the catalog has nothing, or you need a specific country, state or
detail, use the API's search. Plain queries match thousands of series;
`--order-by popularity` puts the ones people actually use first, and the
filters narrow by frequency, adjustment and tags:

```bash
dismal fred series search "median household income" --order-by popularity -n 10
dismal fred series search "unemployment rate" --frequency m --tag usa -n 10
dismal fred series search "unemployment rate" --seasonal nsa --tag usa -n 10
dismal fred series search "consumer price index germany" --order-by popularity -n 5
dismal fred series search "exports to china" -n 10
dismal fred series search "DEX" --id -n 50                    # ids starting with DEX: exchange rates
dismal fred series search "home price index" --exclude-tag discontinued --order-by popularity
```

Tips:

- Read `observation_end` and `last_updated`: a popular series may have been
  discontinued years ago (the `discontinued` tag catches most).
- Use `--tag` with the source (`bls`, `bea`, `frb`, `census`), the geography
  (`usa`, a state name) or the adjustment (`sa`, `nsa`).
- `--order-by last_updated --sort desc` finds what moved most recently;
  `dismal fred series updates` lists the latest updates across FRED.
- Browse by publication when the question is "what is in the jobs report":
  `dismal fred releases -q employment` then `dismal fred releases series 50`.

### 3.4 Read the id

FRED ids are mnemonics, but families follow patterns
([series-ids.md](series-ids.md)): `DGS<n>` daily and `GS<n>` monthly Treasury
yields; `T10Y2Y`/`T10Y3M` spreads; `D<...>` daily versions of monthly series
(`DFF`, `DTB3`, `DPRIME`); `DEX<ccy>US`/`DEXUS<ccy>` exchange rates;
`<ST>UR` state unemployment rates; `...SL`/`...SA` seasonally adjusted and
`...NS`/`...NSA` not; `...96` chained (real) dollars; BLS ids kept verbatim
(`LNS11300060`, `CUSR0000SEHA`) and BEA codes with a `SBEA` suffix
(`A191RL1Q225SBEA`).

**Verify every id you construct** with `dismal fred series info`; an unknown id is
a warning (and exit 6 with `--strict`), not silent zeros.

---

## 4. Fetching exactly what you need

### 4.1 Pick the time window

| Need | Flags | Notes |
| --- | --- | --- |
| The newest value | `dismal fred latest ID...` | one tiny request per series |
| Recent context | `--years N` | the last N calendar years including this one |
| A specific span | `--start 2021-01 --end 2024-06` | inclusive; also `YYYY`, `YYYY-Qn`, `YYYY-Hn`; sent to the API, so only those rows are transferred |
| Everything since a date | `--start 2000` | runs to the latest observation |
| Full history | no date flags | the default; a daily series since 1962 is about 16,000 rows |

**Fetch a cushion for comparisons** you compute yourself (a year for
year-over-year changes, the window length for rolling averages). When the API
computes the change (`--units pc1`), it handles the cushion itself.

### 4.2 Let the API transform

`--units` applies FRED's own transformations, so the numbers match the
website and you do not have to align dates:

| `--units` | Meaning | Use for |
| --- | --- | --- |
| `lin` | levels (default) | the value itself |
| `chg` | change from the previous observation | monthly payroll gains, point changes in rates |
| `ch1` | change from a year ago | year-over-year change in a rate (points) |
| `pch` | percent change from the previous observation | month-over-month inflation, quarterly growth (not annualized) |
| `pc1` | percent change from a year ago | 12-month inflation, year-over-year growth |
| `pca` | compounded annual rate of change | annualized monthly or quarterly growth, comparable with `A191RL1Q225SBEA` |
| `cch`, `cca` | continuously compounded (annual) rate | log-change growth rates |
| `log` | natural log | charts and regressions |

Rules of thumb: rates and shares change by **points** (`chg`, `ch1`); levels,
indexes and prices by **percent** (`pch`, `pc1`, `pca`). A transformation of
an already-transformed series (a percent change of `A191RL1Q225SBEA`) is
almost never what you want.

### 4.3 Aggregate to a lower frequency

`--frequency` turns daily into weekly, monthly, quarterly or annual data on
the server (never the other way), with `--aggregation`:

| Aggregation | Use for | Examples |
| --- | --- | --- |
| `avg` (default) | rates, yields, indexes, prices | monthly average of `DGS10`, annual average CPI |
| `eop` | stocks and balances, "where did it end" | quarter-end `WALCL`, year-end `M2SL`, the last `DFF` of a month |
| `sum` | flows that add across periods | monthly totals of a weekly flow |

Aggregating weekly data to months uses calendar months; `--frequency m` on
`ICSA` gives the average weekly claims of each month. The week-ending
convention of the source stays (`wef`, `wem`, ... let you pick one).

### 4.4 Vintages: what was known when

FRED keeps every past version of a revised series (ALFRED). `--as-of DATE`
returns the values as published on that date, with `realtime_start` and
`realtime_end` columns showing the period during which each value was
current; `dismal fred series vintages ID` lists the dates on which a series was
released or revised.

```bash
dismal fred series vintages PAYEMS --format csv | tail -3        # recent release/revision dates
dismal fred data PAYEMS --as-of 2024-02-02 --start 2023-10 --format csv  # the January 2024 jobs report as printed
```

Use vintages to reproduce what a decision-maker knew, to measure revisions,
or to avoid look-ahead bias in backtests. Everything without `--as-of` is the
current vintage.

### 4.5 Shape and format

| Use | Flags |
| --- | --- |
| Analysis in pandas, R or SQL; several measures per series | default long layout, `--format json`, `csv` or `parquet` |
| A spreadsheet, a chart, or arithmetic across series | `--layout wide --format csv` (one column per series id) |
| Streaming, line-by-line processing, appending to logs | `--format jsonl` |
| A local data store | `--format parquet -o file.parquet` |
| Reading at a terminal | `--format table` (the default on a TTY) |
| Only some columns | `--columns date,value` |
| Titles, units and update time on every row | `--meta` (one extra request per series) |

The wide layout carries only values and keys rows by date; mixing a daily
and a monthly series produces mostly-empty monthly columns, so aggregate
first (`--frequency m`). `dismal fred data` never caches observations; pull once to
Parquet or CSV for iterative analysis.

### 4.6 Budget your requests

A key may make 120 requests per minute; there is no daily quota. One `dismal fred
data` call issues one request per series (two with `--meta`), each returning
up to 100,000 observations per page.

| Call | Requests |
| --- | --- |
| `dismal fred latest` with 10 ids | 10 (20 with `--meta`) |
| `dismal fred data` 1 id, any window | 1 (2 if more than 100,000 rows) |
| `dismal fred data` 50 ids `--years 5` | 50, and a warning on stderr |
| `dismal fred search` | 0 |
| `dismal fred series search`, `dismal fred series info ID` | 1 each |
| `dismal fred releases`, `dismal fred categories` (after the first call) | 0 |

Batch ids into one call, prefer `--latest` for monitoring, and pause a
minute if you see exit code 4.

---

## 5. Recipes: from data to answers

Each recipe states the question, the series, the command and the arithmetic.
Series ids come from the curated catalog unless noted. Results change with
every release, so no outputs are shown.

### 5.1 Setup

```bash
export FRED_API_KEY=...        # free: https://fred.stlouisfed.org/docs/api/api_key.html
```

Simple answers need only `dismal fred` and `jq`. For arithmetic across rows or
series, a small pandas helper keeps the recipes short:

```python
import json
import subprocess

import pandas as pd


def fred(*args: str) -> pd.DataFrame:
    """Run a `dismal fred` command and return its JSON output as a DataFrame."""
    proc = subprocess.run(
        ["dismal", "fred", *args, "--format", "json"], capture_output=True, text=True, check=True
    )
    df = pd.DataFrame(json.loads(proc.stdout))
    if "date" in df.columns:
        df["date"] = pd.to_datetime(df["date"])
    return df


def wide(*args: str) -> pd.DataFrame:
    """One column per series id, indexed by date."""
    return fred(*args, "--layout", "wide").set_index("date")
```

Most changes below come from `--units`, computed by the API. Where a recipe
shifts dates itself it uses `s.shift(12, freq="MS")` (twelve months) rather
than row offsets, so a missing month produces a gap instead of silently
comparing the wrong months.

You can also skip the subprocess and use the library directly; see
[python-api.md](python-api.md).

### 5.2 Growth and output

#### How fast is the economy growing?

BEA's headline is already a series: real GDP, percent change from the
preceding quarter at a seasonally adjusted annual rate.

```bash
dismal fred data A191RL1Q225SBEA --years 3 --columns date,value --format csv
```

For the year-over-year rate, ask the API for `pc1` on the level:

```bash
dismal fred data GDPC1 --units pc1 --years 3 --columns date,value --format csv
```

A quarterly annualized rate above the year-over-year rate means growth is
picking up.

#### How big is the economy?

```bash
dismal fred latest GDP GDPC1 --meta --columns series_id,date,value,units --format csv
```

`GDP` is current dollars, `GDPC1` chained 2017 dollars, both in billions at
an annual rate. Say "seasonally adjusted annual rate".

#### Is industry expanding?

```bash
dismal fred data INDPRO --units pc1 --years 3 --columns date,value --format csv   # year over year
dismal fred latest TCU --format csv                                                # capacity utilization, percent
```

### 5.3 Prices and inflation

#### What is inflation?

The 12-month change in the CPI, with core and the Fed's preferred PCE
measures, all computed by the API:

```bash
dismal fred latest CPIAUCSL CPILFESL PCEPI PCEPILFE --units pc1 --meta \
  --columns series_id,date,value,title --format csv
```

Each `value` is the percent change from a year earlier. The PCE series lag
the CPI by about two weeks, so the dates can differ; report each with its own
month.

#### Is inflation speeding up or slowing down?

Compare the annualized one-month and three-month rates with the 12-month
rate. `pca` annualizes the latest change; the three-month rate needs a
little arithmetic on the index:

```python
core = wide("data", "CPILFESL", "--years", "3")["CPILFESL"]
ann_1m = ((core / core.shift(1, freq="MS")) ** 12 - 1) * 100
ann_3m = ((core / core.shift(3, freq="MS")) ** 4 - 1) * 100
yoy = (core / core.shift(12, freq="MS") - 1) * 100
print(pd.DataFrame({"1m_ann": ann_1m, "3m_ann": ann_3m, "12m": yoy}).dropna().tail(6).round(1))
```

Short-run rates above the 12-month rate mean inflation is accelerating.

#### What do markets and consumers expect?

```bash
dismal fred latest T5YIE T10YIE T5YIFR MICH --meta --columns series_id,date,value,title --format csv
```

Breakevens (`T5YIE`, `T10YIE`) are the inflation rates that make nominal and
inflation-indexed Treasuries break even; `T5YIFR` is the five-year rate five
years ahead; `MICH` is the Michigan survey's one-year expectation.

#### What is $100 from 2000 worth today?

Scale by the ratio of annual-average CPI (NSA, which is never revised):

```bash
dismal fred data CPIAUCNS --frequency a --start 2000 --columns date,value --format json \
  | jq '(.[-1].value / .[0].value) * 100'
```

The last annual average is for the latest complete year; for a month-to-month
comparison use the monthly series and two specific dates.

#### How much have food, rent or energy prices risen?

```bash
dismal fred latest CPIUFDSL CUSR0000SEHA CPIENGSL --units pc1 --meta --columns series_id,date,value,title --format csv
```

For dollar prices of specific goods (gasoline, oil, natural gas):

```bash
dismal fred latest GASREGW DCOILWTICO DHHNGSP --meta --columns series_id,date,value,units --format csv
```

### 5.4 Jobs and the labor market

#### What is the unemployment rate, and how has it changed?

```bash
dismal fred latest UNRATE --format csv                       # level, percent
dismal fred latest UNRATE --units ch1 --format csv           # change from a year ago, points
dismal fred latest UNRATE --units chg --format csv           # change from last month, points
```

Rates change by points; never report `pc1` of a rate.

#### How many jobs were added last month?

```bash
dismal fred data PAYEMS --units chg --years 1 --descending --columns date,value --format csv
```

Values are thousands of jobs. The latest two months are preliminary and get
revised; compare with the 3-month average:

```python
jobs = fred("data", "PAYEMS", "--units", "chg", "--years", "2").set_index("date")["value"]
print(pd.DataFrame({"change": jobs, "3m_avg": jobs.rolling(3).mean()}).tail(6).round(0))
```

#### Are layoffs rising?

Initial claims are weekly and noisy; the four-week average is the standard
read:

```python
claims = fred("data", "ICSA", "--years", "1").set_index("date")["value"]
print(pd.DataFrame({"claims": claims, "4wk_avg": claims.rolling(4).mean()}).tail(6).round(0))
```

Or let the API average by month: `dismal fred data ICSA --frequency m --years 2`.

#### How tight is the labor market?

Job openings per unemployed person (both in thousands, both monthly):

```python
w = wide("data", "JTSJOL", "UNEMPLOY", "--years", "5").dropna()
print((w["JTSJOL"] / w["UNEMPLOY"]).tail(6).round(2))
```

`dropna()` drops the latest month where unemployment is out but JOLTS is not.
Add `JTSQUR` (quits rate) and `JTSHIR` (hires rate) for the churn picture.

#### Is a recession starting?

The Sahm rule is a series:

```bash
dismal fred data SAHMREALTIME --years 3 --columns date,value --format csv    # 0.50 or more triggers
```

`USREC` marks NBER recession months (1/0); `RECPROUSM156N` is a model-based
probability.

#### Participation and employment rates

```bash
dismal fred latest CIVPART LNS11300060 EMRATIO LNS12300060 --meta --columns series_id,date,value,title --format csv
```

The prime-age (25-54) employment-population ratio (`LNS12300060`) is the
cleanest read of labor-market health because it ignores ageing.

### 5.5 Interest rates and the yield curve

#### Where are rates today?

```bash
dismal fred latest DFEDTARL DFEDTARU DFF SOFR DGS3MO DGS2 DGS10 DGS30 --columns series_id,date,value --format csv
```

The target range (`DFEDTARL`-`DFEDTARU`), the effective rate (`DFF`), SOFR
and the Treasury curve. Daily series are dated the business day they
describe; the latest is usually yesterday.

#### Is the yield curve inverted, and for how long?

```python
spread = fred("data", "T10Y2Y", "--years", "3").set_index("date")["value"].dropna()
inverted = spread < 0
print("latest:", spread.iloc[-1], "days inverted in window:", int(inverted.sum()))
```

`T10Y2Y` is the 10-year minus 2-year yield in percentage points; `T10Y3M`
the 10-year minus 3-month version the recession literature prefers.

#### Monthly averages versus month-end levels

```bash
dismal fred data DGS10 --frequency m --years 5 --columns date,value --format csv                      # average
dismal fred data DGS10 --frequency m --aggregation eop --years 5 --columns date,value --format csv    # month-end
```

Use averages to compare with monthly series (inflation, unemployment) and
end-of-period values to mark a balance sheet or a portfolio.

#### Real interest rates

```bash
dismal fred latest DFII10 --format csv                     # 10-year TIPS yield: the market real rate
```

Or compute nominal minus expected inflation: `DGS10` minus `T10YIE`.

#### Mortgage rates and the spread to Treasuries

```python
w = wide("data", "MORTGAGE30US", "DGS10", "--frequency", "w", "--years", "5").dropna()
print((w["MORTGAGE30US"] - w["DGS10"]).tail(6).round(2))
```

Both are aggregated to weeks so the dates align; the spread is in points.

#### Credit conditions

```bash
dismal fred latest BAMLH0A0HYM2 BAMLC0A0CM BAMLC0A4CBBB --meta --columns series_id,date,value,title --format csv
```

Option-adjusted spreads in percentage points over Treasuries; wider means
more stress. `STLFSI4` and `NFCI` summarise financial conditions in one
index each.

### 5.6 Money, credit and the Fed

#### How big is the Fed's balance sheet, and how fast is it shrinking?

```bash
dismal fred data WALCL --frequency q --aggregation eop --start 2019 --columns date,value --format csv   # quarter-end, millions
dismal fred data WALCL --units ch1 --years 2 --columns date,value --format csv                            # change from a year ago
```

`WALCL` is the Wednesday level in millions of dollars; use `eop` for stocks.
`WRESBAL` (reserves) and `RRPONTSYD` (reverse repo) show where the liquidity
sits.

#### Is the money supply growing?

```bash
dismal fred data M2SL --units pc1 --years 5 --columns date,value --format csv
```

#### Are households stretched?

```bash
dismal fred latest TOTALSL DRCCLACBS TDSP --units lin --meta --columns series_id,date,value,title,units --format csv
dismal fred data TOTALSL --units pc1 --years 3 --columns date,value --format csv
```

Consumer credit (billions), the credit-card delinquency rate (percent,
quarterly) and the debt-service ratio (percent of disposable income).

### 5.7 Markets, the dollar and commodities

```bash
dismal fred data SP500 --units pc1 --years 3 --frequency m --columns date,value --format csv   # 12-month change, monthly average
dismal fred latest VIXCLS DTWEXBGS DEXUSEU DEXJPUS DCOILWTICO --meta --columns series_id,date,value,units --format csv
```

The S&P 500 and the Dow are licensed and start ten years ago; the dollar
index (`DTWEXBGS`) is trade-weighted, higher means a stronger dollar;
exchange rates are quoted as the title says (`DEXUSEU` dollars per euro,
`DEXJPUS` yen per dollar).

### 5.8 Housing

```bash
dismal fred latest HOUST PERMIT HSN1F EXHOSLUSM495S MSACSR --meta --columns series_id,date,value,units --format csv
dismal fred data CSUSHPINSA --units pc1 --years 5 --columns date,value --format csv    # home price inflation
dismal fred data MORTGAGE30US --frequency m --years 5 --columns date,value --format csv
```

Starts, permits and sales are annual rates in thousands of units; Case-Shiller
is an index (January 2000 = 100) published with a two-month lag and not
seasonally adjusted in the `NSA` version; `MSPUS` is the median sales price in
dollars, quarterly.

### 5.9 Government and trade

```bash
dismal fred latest GFDEBTN GFDEGDQ188S --meta --columns series_id,date,value,units --format csv   # debt, and debt to GDP
dismal fred data FYFSD --start 2000 --columns date,value --format csv                               # annual deficit (negative = deficit), millions
dismal fred data MTSDS133FMS --years 2 --columns date,value --format csv                            # monthly deficit
dismal fred data A091RC1Q027SBEA --years 5 --columns date,value --format csv                        # interest payments, billions at an annual rate
dismal fred data BOPGSTB --years 3 --columns date,value --format csv                                # trade balance, millions, monthly
```

Fiscal-year deficits and the monthly Treasury statement are not seasonally
adjusted; compare months with the same month a year earlier.

### 5.10 Vintages and revisions

#### What did the jobs report say when it came out?

Find the release date, then fetch the vintage:

```bash
dismal fred series vintages PAYEMS --format json | jq -r '.[-3:][].vintage_date'   # the last three release dates
dismal fred data PAYEMS --as-of 2024-02-02 --start 2023-10 --units chg --columns date,value,realtime_start --format csv
```

#### How much was a number revised?

```python
first = fred("data", "PAYEMS", "--as-of", "2024-02-02", "--start", "2024-01", "--end", "2024-01")
now = fred("data", "PAYEMS", "--start", "2024-01", "--end", "2024-01")
print("first print:", first["value"][0], "current:", now["value"][0])
```

Payrolls are revised twice in the following months and benchmarked each
February; GDP goes through advance, second and third estimates and annual
updates; the CPI (NSA) is never revised. `--as-of` makes every one of those
reproducible.

### 5.11 States and other countries

```bash
dismal fred latest CAUR TXUR NYUR FLUR OHUR --meta --columns series_id,date,value,title --format csv
dismal fred series search "unemployment rate" --tag "ohio" -n 5 --order-by popularity
dismal fred series search "consumer price index japan" --order-by popularity -n 5
dismal fred series search "gdp per capita" --tag "oecd" --order-by popularity -n 10
```

State unemployment rates follow `<ST>UR`; most other state and international
series are easiest to find with the live search and a geography word or tag.
International series come from the OECD, IMF, World Bank and national
sources with their own frequencies, units and lags: read `dismal fred series info`
before comparing across countries.

### 5.12 Monitoring and pipelines

#### What is coming out this week?

```bash
dismal fred releases dates --days 7 --format csv
```

The FRED release calendar; `dismal fred releases -q "<name>"` gives a release's id
and `dismal fred releases series ID` what it contains.

#### Has anything new been released?

Keep a watchlist and compare the latest observations with the last run:

```bash
touch latest.jsonl
dismal fred latest -S watchlist.txt --strict --format jsonl --columns series_id,date,value > latest.new.jsonl || exit
if ! cmp -s latest.new.jsonl latest.jsonl; then
  diff latest.jsonl latest.new.jsonl || true   # new dates or revised values
  mv latest.new.jsonl latest.jsonl
fi
```

`|| exit` keeps a failed call (rate limit, network) from replacing the last
good snapshot. One request per series, cheap to run daily. `dismal fred series
updates` shows what changed across all of FRED most recently.

#### Keep a local data set current

Revisions mean appending only the newest row leaves stale history behind.
Each run, re-pull a window that covers the revision period (two years is safe
for most monthly series, four for GDP after an annual update) and replace
those rows; pull deep history once.

```bash
dismal fred data -S ids.txt --years 2 --strict --format parquet -o recent.parquet
```

[`examples/github-actions/weekly-pull.yml`](../../examples/fred/github-actions/weekly-pull.yml)
is a scheduled workflow that does this and commits the files.

---

## 6. Reading FRED data correctly

### 6.1 Units and transformations

- **Percent versus percentage points.** Rates and shares (unemployment,
  yields, spreads, participation) change by points: use `chg`/`ch1`. Levels,
  indexes and prices change by percent: use `pch`/`pc1`/`pca`.
- **Annual rates.** Quarterly and monthly BEA flows (GDP, income, spending,
  housing starts) are seasonally adjusted *annual* rates. `pca` annualizes a
  change; `pch` does not. The GDP growth people quote is `A191RL1Q225SBEA`,
  which is `pca` of `GDPC1` to rounding.
- **Some series are already changes.** `A191RL1Q225SBEA` is a percent change;
  `T10Y2Y` is a spread; `SAHMREALTIME` is a difference in points. Report
  `value`; do not transform them again unless you mean to.
- **Index bases differ** (`1982-84=100`, `2017=100`, `Jan 2000=100`). Compare
  percent changes, or rebase.
- **Units are in the metadata**, not the row: `--meta` or `dismal fred series info`
  tells you thousands, millions, billions, percent or an index.

### 6.2 Frequencies and dates

- `date` is the **first day of the period** for monthly, quarterly and annual
  series (`2024-04-01` is 2024Q2), the actual day for daily series, and the
  week-ending day for weekly ones. Weekly conventions differ by source:
  initial claims are dated Saturdays, mortgage rates Thursdays, the Fed's
  balance sheet Wednesdays.
- **Daily series have holes.** Markets close on holidays; the value is `.` in
  the API and `null` here. Date-aligned arithmetic keeps a hole from shifting
  a comparison.
- **Aggregation** (`--frequency`) uses calendar periods and the method you
  choose; averages of daily rates are the convention for monthly comparisons,
  end-of-period values for stocks.
- **Mixing frequencies in a wide table** leaves gaps; aggregate first.

### 6.3 Seasonal adjustment

Most monthly and quarterly economic series are seasonally adjusted (`SA`,
`SAAR` for annual-rate flows); financial market series and some prices are
not (`NSA`). Many series exist in both forms under different ids
(`CPIAUCSL`/`CPIAUCNS`, `CSUSHPISA`/`CSUSHPINSA`). Use SA for month-to-month
changes and trends, NSA for year-over-year CPI (BLS's headline convention)
and for contracts, and compare NSA series with the same period a year
earlier.

### 6.4 Vintages, revisions and `last_updated`

Without `--as-of`, every observation is the current vintage, after all
revisions. `last_updated` (`--meta`, `series info`) says when the series
last changed; `observation_end` what the newest period is. For "as first
published" questions, backtests and revision studies use `--as-of`;
`realtime_start`/`realtime_end` bracket the life of each value, and
`9999-12-31` means "still current".

### 6.5 Release timing

"Latest" is the latest *published* period, and it differs by series.
Approximate lags (see `dismal fred releases dates` for exact dates):

| Series | Published |
| --- | --- |
| Treasury yields, fed funds, SOFR, exchange rates, oil, VIX (`DGS*`, `DFF`, `SOFR`, `DEX*`, `DCOIL*`, `VIXCLS`) | the next business day |
| Initial claims (`ICSA`) | Thursday, for the week ended Saturday |
| Mortgage rates (`MORTGAGE30US`) | Thursday |
| Fed balance sheet (`WALCL`, `WRESBAL`) | Thursday, for Wednesday |
| Jobs report (`UNRATE`, `PAYEMS`, `CES0500000003`) | usually the first Friday after the month |
| CPI (`CPIAUCSL`, ...), PPI | about two weeks after the month |
| Retail sales, industrial production, housing starts | mid-month for the previous month |
| Personal income, spending and PCE prices (`PI`, `PCE`, `PCEPI`) | about four weeks after the month |
| GDP (`GDP`, `GDPC1`, `A191RL1Q225SBEA`) | about four weeks after the quarter (advance), then revised twice |
| JOLTS (`JTSJOL`, `JTSQUR`) | about five weeks after the month |
| Case-Shiller (`CSUSHPINSA`) | the last Tuesday of the month, for two months earlier |
| M2 (`M2SL`) | about four weeks after the month |
| Federal debt (`GFDEBTN`), deficits | quarterly / monthly / fiscal year, with short lags |

Consequences: always report the period with the value; when combining series
(ratios, spreads, real values), align on dates and drop periods where one
side is missing.

### 6.6 Sources and lineage

FRED republishes; the source owns the methodology. The series `notes`
(`dismal fred series info --notes`) name the source and often the source's own id,
and the `source` column of `dismal fred search` shows the agency. For deep work in a
source's own structure, the sibling sources are better: `dismal bls` for BLS surveys
and `dismal bea` for BEA tables; many ids are shared or trivially mapped
([series-ids.md](series-ids.md)).

### 6.7 Discontinued series and licensing

Series end: methodologies change, programs stop, licenses lapse. Check
`observation_end` and the `discontinued` tag before relying on a popular id,
and prefer the successor FRED names in the notes. Licensed market data (S&P
Dow Jones indices) cover the most recent ten years only; some vendor series
were withdrawn entirely.

### 6.8 Nominal and real

`...96` series (`PCEC96`, `DSPIC96`) and chained-dollar series (`GDPC1`) are
real; to deflate a nominal series yourself, divide by a price index rebased
to the period you want (`CPIAUCSL` for household measures, `PCEPI` for
consumption, `GDPDEF` for GDP). The real interest rate is `DFII10` (market)
or `DGS10 - T10YIE` (nominal minus expected inflation).

---

## 7. Using `dismal fred` from an agent

[agents.md](agents.md) is the contract (invariants, exit codes, schema);
[`examples/skill/SKILL.md`](../../examples/skill/SKILL.md) is a ready-made skill.
This section is the judgment layer on top: how to turn a user's question into
a correct, sourced answer with the fewest requests.

### 7.1 Protocol

1. **Classify the request.** Latest value, change, history, comparison,
   derived metric (spreads, ratios, real values, rolling averages), a past
   vintage, or something FRED does not have (intraday prices, forecasts,
   microdata). For the last, say so and stop.
2. **Frame it** with the table in [section 2](#2-the-research-workflow):
   measure, transformation, frequency and aggregation, seasonal adjustment,
   vintage, geography, time span.
3. **Resolve ids, cheapest first.**
   - Check the [question playbook](#8-question-playbook).
   - `dismal fred search "<concept>" --limit 5 --format json`. Accept the top hit if
     its score is at least 90 and its `frequency`/`seasonal` match the
     framing; choose among ties deliberately.
   - Otherwise reformulate in FRED vocabulary
     ([section 3.1](#31-write-queries-in-fred-vocabulary)) and retry once, then
     `dismal fred series search "<words>" --order-by popularity -n 10 --format json`
     with filters.
   - Confirm an unfamiliar id with `dismal fred series info ID --format json`
     (units, frequency, adjustment, `observation_end`).
   - If several candidates remain plausible, show them to the user and ask.
   - Never invent an id; a wrong one is a warning and an empty result.
4. **Plan one fetch.** All ids in one call; `--units` for the change you
   need; `--frequency` to align daily with monthly; the narrowest window that
   covers the comparison; `latest` when only the current value matters;
   `--as-of` for vintages. Count the requests.
5. **Run it** with `--format json` (or `jsonl`) and `--strict`. Parse stdout
   only. Handle the exit code ([section 7.3](#73-exit-codes)).
6. **Compute in code** what the API did not. Align series on `date`.
7. **Sanity-check.** Is the date what you expected? Units right (percent,
   points, thousands, billions, annual rate)? Any `null` values? Do the
   series' latest dates differ? Is the series discontinued?
8. **Answer** with the template in [section 7.4](#74-answer-template).

### 7.2 Decision rules

| Situation | Rule |
| --- | --- |
| "Inflation" with no qualifier | `CPIAUCSL --units pc1`; mention core (`CPILFESL`) and PCE (`PCEPILFE`) if the Fed is the context |
| "Unemployment" with no qualifier | `UNRATE`, SA, changes in points (`ch1`/`chg`) |
| "Jobs added" | `PAYEMS --units chg`, thousands |
| "Interest rates" with no qualifier | ask, or report the policy rate (`DFF`) and the 10-year yield (`DGS10`) together |
| "The Fed raised/cut rates" | `DFEDTARU`/`DFEDTARL` (target range), not the effective rate |
| "GDP growth" | `A191RL1Q225SBEA` (annualized quarterly), with `GDPC1 --units pc1` for year over year |
| "Mortgage rates" | `MORTGAGE30US`, weekly, Thursdays |
| "The stock market" | `SP500`, note the ten-year window |
| A rate or spread changed | report percentage points |
| A level, index or price changed | report percent; say "annualized" when you used `pca` |
| Daily versus monthly series in one answer | aggregate the daily one with `--frequency m` |
| Series with different latest dates | report each with its own date; align before combining |
| The user asks what was known on a date | `--as-of`; say "as published on that date" |
| `null` values | holidays or missing data; say so, do not interpolate |
| No key (`dismal fred config` shows `api_key: "(not set)"`) | stop: every live request needs `FRED_API_KEY` |
| User asks for a forecast | FRED data describe the past (apart from a few published nowcasts); say so and offer the history |

### 7.3 Exit codes

| Code | Do |
| --- | --- |
| 0 | parse stdout |
| 2 | your command is wrong: read stderr; fix flags, dates, units or `--columns` |
| 3 | the API rejected something (unknown id when not batched, raising a frequency, bad units): read stderr and fix |
| 4 | rate limit: wait a minute, then retry |
| 5 | network: retry once after a pause |
| 6 | (`--strict`) a series returned no data: check the id and the window; discontinued? |
| 7 | configuration: `FRED_API_KEY` missing or rejected |

### 7.4 Answer template

```
<Measure> was <value> <units> in/on <period> (<seasonally adjusted | not seasonally adjusted>)<, annualized>.
<Change, in points for rates and spreads or percent for levels and indexes, with the comparison period>.
<One caveat if it matters: preliminary, a different latest date, a holiday gap, a licensed window, a vintage>.
Source: FRED (Federal Reserve Bank of St. Louis), series <ID> (<source agency>); retrieved <YYYY-MM-DD><, vintage of <date>>.
```

Always include the period and the series id; a number without them cannot be
checked. Name the original source agency when the notes give it.

### 7.5 Worked examples

**"What's the unemployment rate, and is it higher than a year ago?"**

```bash
dismal fred search "unemployment rate" --limit 3 --format json       # UNRATE, 100, monthly, SA
dismal fred latest UNRATE --meta --strict --format json              # level and date
dismal fred latest UNRATE --units ch1 --format json                   # change from a year ago, points
```

Answer: "The unemployment rate was {value}% in {month year} (seasonally
adjusted), {ch1:+} points from a year earlier. Source: FRED series UNRATE
(BLS); retrieved {today}."

**"Is the yield curve inverted?"**

```bash
dismal fred search "yield curve" --limit 2 --format json              # T10Y2Y, T10Y3M
dismal fred latest T10Y2Y T10Y3M --format json                        # spreads in points, latest business day
```

Answer with both spreads and their date; negative means inverted. If the
user asks "for how long", fetch `--years 3` and count the days below zero.

**"What did the January jobs report say about payrolls?"**

```bash
dismal fred series vintages PAYEMS --format json | jq -r '.[-12:][].vintage_date'   # find the early-February release date
dismal fred data PAYEMS --as-of 2024-02-02 --start 2023-12 --end 2024-01 --units chg --format json
```

Answer with the change in thousands "as published on 2 February 2024", and
offer the current (revised) figure for contrast.

**"What's the price of gold?"**

Not available: FRED withdrew the LBMA gold series. Say so and, if useful,
point to the source (LBMA) rather than substituting a different commodity.

### 7.6 Anti-patterns

- Calling `dismal fred data` once per id in a loop (one call takes many ids).
- Fetching full history when the question needs the latest value, or
  omitting `--start` when you only need a year.
- Taking the top search hit without checking frequency and seasonal
  adjustment (daily `DFF` versus monthly `FEDFUNDS`).
- Reporting `pc1` of a rate, or a percent change of a series that is already
  a change or a spread.
- Putting a daily and a monthly series in one wide table without
  `--frequency`.
- Comparing index levels across series with different bases.
- Treating a licensed ten-year series as full history.
- Presenting a current-vintage number as "what the report said at the time".
- Parsing stderr, or relying on the default output format.
- Naming `--meta` columns (`title`, `units`) in `--columns` without `--meta`:
  they do not exist and the command exits 2.

---

## 8. Question playbook

Starting points for common questions. Ids are national and from the curated
catalog unless noted.

| Question | Series | Flags / notes |
| --- | --- | --- |
| Headline inflation, year over year | `CPIAUCSL` | `--units pc1` |
| Inflation, month over month (annualized) | `CPIAUCSL` | `--units pch` (`pca` annualized) |
| Core inflation | `CPILFESL`, `PCEPILFE` | `--units pc1` |
| PCE inflation (the Fed's measure) | `PCEPI`, `PCEPILFE` | `--units pc1` |
| Producer prices | `PPIFIS`, `PPIACO` | `--units pc1` |
| Inflation expectations | `T5YIE`, `T10YIE`, `T5YIFR`, `MICH` | daily breakevens; monthly survey |
| Food, rent, energy, used cars (CPI components) | `CPIUFDSL`, `CUSR0000SEHA`, `CPIENGSL`, `CUSR0000SETA02` | `--units pc1` |
| Gasoline, oil, natural gas ($) | `GASREGW`, `DCOILWTICO`, `DCOILBRENTEU`, `DHHNGSP` | weekly / daily |
| Unemployment rate | `UNRATE` | `--units ch1` for the year-ago change in points |
| Broad underemployment (U-6) | `U6RATE` | |
| Participation, employment-population (prime age) | `CIVPART`, `LNS11300060`, `EMRATIO`, `LNS12300060` | points |
| Payroll jobs added | `PAYEMS` | `--units chg`, thousands |
| Private and manufacturing payrolls | `USPRIV`, `MANEMP` | `--units chg` |
| Wages | `CES0500000003`, `AHETPI`, `ECIWAG` | `--units pc1` |
| Initial and continued claims | `ICSA`, `CCSA` | weekly; `--frequency m` for monthly averages |
| Job openings, quits, hires, layoffs | `JTSJOL`, `JTSQUR`, `JTSHIR`, `JTSLDL` | a month behind payrolls |
| Productivity, unit labor costs | `OPHNFB`, `ULCNFB` | `--units pc1` or `pca` |
| Real GDP growth | `A191RL1Q225SBEA` | already annualized percent |
| Real GDP, nominal GDP, potential | `GDPC1`, `GDP`, `GDPPOT` | `--units pc1` for growth |
| GDP per capita | `A939RX0Q048SBEA` | |
| Industrial production, capacity utilization | `INDPRO`, `TCU` | `--units pc1`; percent |
| Retail sales, durable goods orders | `RSAFS`, `DGORDER` | `--units pc1` |
| Consumer sentiment | `UMCSENT` | index |
| Personal income, disposable income, spending, saving rate | `PI`, `DSPIC96`, `PCE`, `PSAVERT` | `--units pc1`; saving rate in percent |
| Fed funds rate (monthly, daily), target range | `FEDFUNDS`, `DFF`, `DFEDTARU`/`DFEDTARL` | |
| SOFR, prime rate, interest on reserves | `SOFR`, `DPRIME`, `IORB` | daily |
| Treasury yields | `DGS1MO`, `DGS3MO`, `DGS6MO`, `DGS1`, `DGS2`, `DGS5`, `DGS10`, `DGS30` | `--frequency m` for monthly averages |
| Yield curve spreads | `T10Y2Y`, `T10Y3M` | points; negative = inverted |
| Real yields | `DFII10` | or `DGS10` minus `T10YIE` |
| Mortgage rates | `MORTGAGE30US`, `MORTGAGE15US` | weekly |
| Corporate yields and credit spreads | `AAA`, `BAA`, `BAMLH0A0HYM2`, `BAMLC0A0CM`, `BAMLC0A4CBBB` | spreads in points |
| Financial conditions, stress | `NFCI`, `STLFSI4` | indexes |
| Money supply | `M2SL`, `M1SL` | `--units pc1` |
| Fed balance sheet, reserves, reverse repo | `WALCL`, `WRESBAL`, `RRPONTSYD` | `--frequency q --aggregation eop` |
| Consumer credit, business loans, delinquencies, debt service | `TOTALSL`, `BUSLOANS`, `DRCCLACBS`, `TDSP` | |
| Stock market, volatility | `SP500`, `DJIA`, `NASDAQCOM`, `VIXCLS` | ten-year window for S&P and Dow |
| Exchange rates, dollar index | `DEXUSEU`, `DEXJPUS`, `DEXCHUS`, `DEXUSUK`, `DEXCAUS`, `DEXMXUS`, `DTWEXBGS` | daily |
| Housing starts, permits, completions | `HOUST`, `PERMIT`, `COMPUTSA` | thousands, annual rate |
| Home sales, supply | `HSN1F`, `EXHOSLUSM495S`, `MSACSR` | |
| Home prices | `CSUSHPINSA` (index), `MSPUS` (median $), `USSTHPI` | `--units pc1` |
| Homeownership, rental vacancy | `RHORUSQ156N`, `RRVRUSQ156N` | quarterly, percent |
| Federal debt, debt to GDP | `GFDEBTN`, `GFDEGDQ188S` | |
| Deficit (annual, monthly), receipts, spending, interest | `FYFSD`, `MTSDS133FMS`, `FGRECPT`, `FGEXPND`, `A091RC1Q027SBEA` | negative = deficit |
| Trade balance, exports, imports | `BOPGSTB`, `EXPGS`, `IMPGS`, `NETEXP` | |
| Recession indicators | `USREC`, `SAHMREALTIME`, `RECPROUSM156N` | |
| Median household / personal income | `MEHOINUSA672N`, `MEPAINUSA672N` | annual, real |
| Population | `POPTHM`, `CNP16OV` | thousands |
| State unemployment rate | `<ST>UR` (`CAUR`, `TXUR`, ...) | pattern; SA |
| Anything else, other countries | `dismal fred series search "..." --order-by popularity` | 1 request |

---

## 9. Troubleshooting

| Symptom | Likely cause | Fix |
| --- | --- | --- |
| `dismal fred search` finds nothing | question words, or the series is not in the curated catalog | reformulate ([section 3.1](#31-write-queries-in-fred-vocabulary)); then `dismal fred series search` |
| Warning `series X does not exist` (exit 6 with `--strict`) | wrong or old id | `dismal fred series search X --id`, or search by words |
| Warning `no observations returned for X` | the window is before the series starts or after it ends; a discontinued series | `dismal fred series info X` for `observation_start`/`observation_end` |
| Exit 3 mentioning frequency | `--frequency` higher than the series' own (monthly to daily) | aggregate down only, or drop `--frequency` |
| Exit 3 mentioning units or an invalid value | a transformation the series cannot take (`log` of a negative, `pch` of a spread) | use `chg`/`ch1`, or compute yourself |
| Exit 2 `unknown column(s)` | `--columns` names a column that was not produced (`title` without `--meta`, `realtime_start` without `--as-of`) | the error lists the available columns |
| Exit 4 | more than 120 requests in a minute | wait a minute; batch ids; prefer `--latest` |
| Exit 7 | `FRED_API_KEY` not set, or the API rejected it | get a key at <https://fred.stlouisfed.org/docs/api/api_key.html>; `dismal fred doctor` |
| `null` values in a daily series | holidays and market closures | expected; skip them in arithmetic |
| A series stops years ago | discontinued, or a licensed window | read the notes; find the successor; `--exclude-tag discontinued` in search |
| The S&P 500 starts ten years ago | licensing | expected; longer history is not available on FRED |
| Numbers differ from a news report | vintage (revised since), units (annual rate), or seasonal adjustment | `--as-of` the report's date; check `--meta` units and `seasonal_adjustment` |
| Wide CSV full of blanks | daily and monthly series mixed | `--frequency m` |
| Output is a table in a script | the default format follows the terminal | always pass `--format` |
| `dismal fred releases -q x` filters instead of going quiet | `-q` means `--query` on `releases` and `categories` | put the global flag first: `dismal fred -q data ...` |
| Latest dates differ across series | different release schedules | expected; report each date |

`dismal fred doctor` checks the configuration and makes one live request; run it
first when something unexpected happens.

---

## 10. Further reading

In this repository:

- [usage.md](usage.md): every command and flag
- [agents.md](agents.md): the contract for automations and agents
- [series-ids.md](series-ids.md): how to find and read series ids
- [output-formats.md](output-formats.md): record schemas per format
- [configuration.md](configuration.md): environment variables, limits, caching
- [python-api.md](python-api.md): using `dismal.fred.FREDClient` directly

From the Federal Reserve Bank of St. Louis:

- [FRED API documentation](https://fred.stlouisfed.org/docs/api/fred/) and
  [API keys](https://fred.stlouisfed.org/docs/api/api_key.html)
- [ALFRED](https://alfred.stlouisfed.org/): archival FRED, the vintages
  behind `--as-of`
- [Release calendar](https://fred.stlouisfed.org/releases/calendar)
- [FRED Blog](https://fredblog.stlouisfed.org/): worked examples with the
  same series
- Each series' page on fred.stlouisfed.org: notes, sources, related series

Sibling sources of `dismal` for the source agencies' own structure:
[`dismal bls`](../bls/practitioners-guide.md) and
[`dismal bea`](../bea/practitioners-guide.md).
