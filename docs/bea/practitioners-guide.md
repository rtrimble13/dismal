# Practitioner's guide

How to use `dismal bea` to answer real questions with the official U.S. economic
accounts: GDP, income, spending, prices, industries, states and counties, and
the country's transactions with the rest of the world.

This guide answers two questions: *what can I use `dismal bea` for?* and *how
would I use `dismal bea` to do X?* It is written for people doing research in a
terminal or a notebook, and it doubles as a reference for agents (skills, coding
assistants, scheduled jobs) that answer questions with BEA data. It is the
sibling of the [`bls`](../bls/practitioners-guide.md) and
[`fred`](../fred/practitioners-guide.md) practitioner's guides and follows the
same layout.

It is about using the tool well, not about every flag. For those, see
[usage.md](usage.md) (command reference), [agents.md](agents.md) (the
machine contract: exit codes, schemas, budget) and
[table-ids.md](table-ids.md) (datasets, tables and how to find them).

**Agents:** read [section 7](#7-using-dismal-bea-from-an-agent) first, then use
[section 8](#8-question-playbook) as a lookup table and the recipes in
[section 5](#5-recipes-from-data-to-answers) as templates.

## Contents

1. [What you can answer with `dismal bea`](#1-what-you-can-answer-with-dismal-bea)
2. [The research workflow](#2-the-research-workflow)
3. [Finding the right table](#3-finding-the-right-table)
4. [Fetching exactly what you need](#4-fetching-exactly-what-you-need)
5. [Recipes: from data to answers](#5-recipes-from-data-to-answers)
6. [Reading BEA data correctly](#6-reading-bea-data-correctly)
7. [Using `dismal bea` from an agent](#7-using-dismal-bea-from-an-agent)
8. [Question playbook](#8-question-playbook)
9. [Troubleshooting](#9-troubleshooting)
10. [Further reading](#10-further-reading)

---

## 1. What you can answer with `dismal bea`

`dismal bea` reaches every dataset the BEA Data API publishes (`dismal bea datasets`). In
practice that covers the national income and product accounts (GDP and
everything that feeds it), monthly income and spending, BEA's price indexes,
output by industry, the regional accounts for states, counties and metro
areas, and the international accounts.

| Domain | Typical questions | Dataset | Good starting tables |
| --- | --- | --- | --- |
| Growth | How fast is the economy growing? What drove growth last quarter? How big is GDP? | `NIPA` | `T10101` (real GDP growth), `T10102` (contributions), `T10105` (GDP, dollars), `T10106` (real GDP, chained dollars) |
| Prices | What is PCE inflation? Core PCE? The GDP deflator? | `NIPA` | `T20804` (PCE price indexes, monthly), `T20304` (quarterly), `T10104` (GDP price indexes) |
| Income, spending, saving | How fast is personal income growing? What is the saving rate? Are consumers spending? | `NIPA` | `T20600` (income, monthly), `T20100` (quarterly), `T20805`/`T20806` (PCE, monthly), `T20301` (real PCE growth) |
| Government, trade, investment | How large is the deficit in the accounts? Are exports growing? Is business investment rising? | `NIPA` | `T30100`, `T40100`, `T40205`, `T50100`, `T50305`/`T50306` |
| Income by type and industry | What are corporate profits? How much goes to labor? | `NIPA` | `T11200`, `T11000`, `T60200D`, `T61600D` |
| Detailed consumption | How much do households spend on a particular product? | `NIUnderlyingDetail` | `U20404`/`U20405`/`U20406` |
| Industries | Which industries are growing? What share of GDP is manufacturing? | `GDPbyIndustry` | TableID `1` (value added), `5` (share of GDP), `8` (quantity indexes), `10` (real value added), `15` (gross output) |
| States | Which states grew fastest? What is personal income per capita in my state? Where is the cost of living highest? | `Regional` | `SAGDP1`/`SQGDP1` (GDP), `SAINC1`/`SQINC1` (income, population), `SARPP` (price parities), `SAEMP25N` (jobs) |
| Counties and metros | How is my county's economy doing? | `Regional` | `CAINC1`, `CAGDP2`, `CAGDP9`, and the `MA*` tables (`dismal bea tables list Regional`) |
| Trade and the balance of payments | What is the trade deficit? The current-account balance? Trade with a country? | `ITA` | indicators `BalGds`, `BalServ`, `BalGdsServ`, `BalCurrAcct`, `ExpGdsServ`, `ImpGdsServ` |
| Investment position | What does the U.S. own abroad and owe to foreigners? | `IIP` | `TypeOfInvestment=Net`, `FinAssets`, `FinLiabs` with `Component=Pos` |
| Capital stock | How large is the stock of fixed assets? How much is invested each year? | `FixedAssets` | `FAAt101`, `FAAt105`, `FAAt201` |
| Multinationals, services trade, input-output | Foreign direct investment, services by country, industry linkages | `MNE`, `IntlServTrade`, `IntlServSTA`, `InputOutput` | find parameters with `dismal bea datasets show` and `dismal bea values` |

### What `dismal bea` is not for

Knowing the boundary saves time and prevents wrong answers.

- **Statistics from other agencies.** The CPI, unemployment, payroll jobs and
  wages are BLS (use [`dismal bls`](../bls/practitioners-guide.md)); interest
  rates are the Federal Reserve's (use
  [`dismal fred`](../fred/practitioners-guide.md)); retail sales, housing
  starts and the monthly goods-trade figures are Census; weekly jobless claims
  are the Department of Labor's. Say so rather than substituting a BEA series.
- **Monthly trade.** The joint Census-BEA monthly trade release is not in
  the API; the `ITA` dataset is annual and quarterly.
- **Data as first published.** The API returns today's values for every
  period, after every revision. For "what did the advance estimate say", use
  a real-time archive such as ALFRED (St. Louis Fed) or BEA's news-release
  archive.
- **Nowcasts and forecasts.** GDPNow is the Atlanta Fed's; BEA publishes
  measurements, not predictions.
- **Release text, dates and charts.** The release schedule, highlights and
  the interactive tables live on bea.gov, not in the API.
- **Microdata.** `dismal bea` returns published aggregates.

---

## 2. The research workflow

Every question, simple or complex, goes through the same steps. Skipping the
first one is the most common source of wrong answers.

1. **Frame the question precisely.** Decide the items in the table below.
2. **Find the table and parameters** ([section 3](#3-finding-the-right-table)).
3. **Verify the lines** you need: title, units, frequencies and the series
   id each line produces (`dismal bea tables show`).
4. **Fetch once**, with a range that covers any comparison you need
   ([section 4](#4-fetching-exactly-what-you-need)).
5. **Transform in code** (changes, ratios, shares, rankings). Do not do
   arithmetic by eye.
6. **Sanity-check** the result: period, units and `unit_mult`, annual rate or
   not, vintage, suppressed cells ([section 6](#6-reading-bea-data-correctly)).
7. **Report with provenance:** value, units, period, table and line (or
   series id), estimate vintage, retrieval date and caveats
   ([section 7.4](#74-answer-template)).

| Decide | Options | Sensible default |
| --- | --- | --- |
| Measure | level (dollars), real level (chained dollars), percent change, index, share, per capita | what the question names; "growth" means a percent change at an annual rate |
| Nominal or real | current dollars, chained (2017) dollars, price index | real for growth and volumes, nominal for sizes and shares |
| Geography | U.S., state, county, metro, country | U.S. (`NIPA`) unless stated; states and below are `Regional` |
| Frequency | annual, quarterly, monthly | quarterly for GDP, monthly for income/spending/prices, annual below the state level |
| Time | latest, a range, full history | latest plus a year or two of context |
| Transformation | level, change, annualized change, year-over-year, contribution, share, rank | percent changes for levels and indexes; points for rates and shares |

---

## 3. Finding the right table

The API has no search; it has metadata methods. `dismal bea` gives you a ladder
of discovery tools. Start at the top; each step down covers more and costs a
little more.

| Step | Command | Cost | Covers |
| --- | --- | --- | --- |
| 1 | `dismal bea search "words"` | free, offline | ~75 curated headline tables and indicators, each with a ready-to-run `command` |
| 2 | `dismal bea search "words" --kind all`, `dismal bea datasets --query "words"` | free, offline | which dataset a topic belongs to |
| 3 | `dismal bea tables list DATASET --query "words"` | 1 request, cached 7 days | every table of the dataset |
| 4 | `dismal bea tables show DATASET TABLE` | 1 request | the lines of a table: series ids, titles, units, frequencies, latest value |
| 5 | `dismal bea values DATASET PARAMETER [--filter K=V]` | 1 request, cached 7 days | any parameter: line codes, geographies, industries, indicators, years |
| 6 | `dismal bea datasets show DATASET` | 1 request, cached 7 days | the dataset's parameters and which are required |

### 3.1 Write queries in BEA vocabulary

The offline search matches words in table titles and curated tags, tolerates
typos and word order, and knows the common names: `gdp`, `real gdp`, `gdp
growth`, `pce`, `inflation`, `core pce`, `personal income`, `saving rate`,
`disposable income`, `consumer spending`, `corporate profits`, `investment`,
`exports`, `imports`, `trade balance`, `current account`, `state gdp`, `county`,
`per capita`, `regional price parities`, `value added`, `gross output`.

Name the concept rather than asking a question. A word that appears in no
title or tag counts against the match.

| You might type | What happens | Type instead |
| --- | --- | --- |
| `how fast is the economy growing` | nothing: the question words count as misses | `gdp growth` |
| `inflation` | PCE price index tables, correctly; the CPI is BLS data | `pce price index` (or `dismal bls search cpi`) |
| `unemployment`, `jobs report` | nothing, correctly: not BEA data | use `dismal bls` |
| `gdp` | many tables at 100: levels, real levels, growth, prices | add the measure: `gdp growth`, `real gdp`, `gdp price index` |
| `texas gdp` | the state GDP tables (the geography is a parameter, not a table) | `state gdp`, then `--geo 48000` |

Useful exact terms (all score 100): `real gdp`, `gdp growth`, `nominal gdp`,
`gdi`, `gnp`, `pce`, `core pce`, `deflator`, `personal income`, `disposable
income`, `saving rate`, `consumer spending`, `corporate profits`, `national
income`, `fixed investment`, `net exports`, `trade balance`, `current
account`, `niip`, `state gdp`, `county gdp`, `per capita personal income`,
`rpp`, `value added`, `gross output`.

### 3.2 Read the score and the `command`

| Score | Meaning | What to do |
| --- | --- | --- |
| 100 | exact table id, tag or title | use it, after choosing among ties |
| ~92-99 | every query word found | almost always right; read the title |
| below ~90 | partial or fuzzy match | read titles; reformulate; or go to step 3 |
| nothing | no result above `--min-score` (55) | reformulate, then `dismal bea tables list DATASET --query ...` |

Ties at 100 are normal and usually differ in the *measure*: `T10101` (percent
change), `T10105` (current dollars) and `T10106` (chained dollars) all match
`gdp`. Choose by the `title` and `units` columns, not the first row. Every hit
carries a `command` that fetches it with the preferred frequency; copy it and
add a time range.

```bash
dismal bea search "gdp" --limit 6 --format csv --columns id,score,frequency,units,command
```

### 3.3 Read the table numbers

NIPA table ids encode the printed table number: `T` + section + subsection +
variant, so Table 1.1.5 is `T10105`, Table 2.1 is `T20100`, Table 2.3.4 is
`T20304` and Table 6.16D is `T61600D`. The sections are 1 GDP, 2 personal
income and outlays, 3 government, 4 foreign transactions, 5 saving and
investment, 6 income and employment by industry, 7 supplemental. The variant
digit says what the table measures:

| Variant | Measure | Example |
| --- | --- | --- |
| `.1` | percent change from preceding period (annual rate) | `T10101` |
| `.2` | contributions to percent change (percentage points) | `T10102` |
| `.3` | quantity indexes (2017=100) | `T10103` |
| `.4` | price indexes (2017=100) | `T10104` |
| `.5` | current dollars | `T10105` |
| `.6` | chained (2017) dollars | `T10106` |

Monthly tables sit in section 2 (`T20600` income, `T20801`-`T20807` PCE).
`NIUnderlyingDetail` ids start with `U`, `FixedAssets` with `FAAt`.

Regional table names are prefix + subject + number: `SA`/`SQ` state annual
or quarterly, `CA` county annual, `MA` metro annual; `INC` personal income,
`GDP` gross domestic product, `EMP` employment, `PCE` consumption, `RPP`
price parities, `RPI` real personal income; a trailing `N` means NAICS
industry detail. So `SQGDP9` is quarterly real GDP by state and industry,
`CAINC1` the county income summary.

### 3.4 Learn the lines and parameters before fetching

A table is a set of lines, and each line becomes a series in the output.
`dismal bea tables show` lists them with their ids, units, frequencies and latest
value, which is the fastest way to know what you will get:

```bash
dismal bea tables show NIPA T10101          # A191RL Gross domestic product, DPCERL ..., in "Percent change, annual rate"
dismal bea tables show NIPA T20600          # personal income, DPI, saving rate ... monthly
dismal bea tables show GDPbyIndustry 1      # one series per industry
dismal bea tables show Regional SAINC1      # the LineCode values of a Regional table
```

Regional tables take a *line code* and a *geography*; `GDPbyIndustry` takes an
industry; `ITA` an indicator and a country. Look them up once, from the cache:

```bash
dismal bea values Regional LineCode --filter TableName=SAGDP2N      # industries of state GDP
dismal bea values Regional GeoFips --query "new york"                # 36000 = New York state
dismal bea values GDPbyIndustry Industry --limit 0                   # 11, 21, 22, 23, 31G, ..., GDP, PVT, G
dismal bea values ITA Indicator --query "current account"
dismal bea values ITA AreaOrCountry --query china
dismal bea values NIPA Year --filter TableName=T10101                # first and last year per frequency
```

Geography codes (`GeoFips`): `STATE` all states and DC, `COUNTY` all counties,
`MSA` all metro areas, `00000` the United States, a 2-digit state FIPS plus
`000` (`06000` California, `48000` Texas), a 5-digit county FIPS (`06037` Los
Angeles County) or a 5-digit metro code. Comma lists work, so `--geo
06000,48000,36000` fetches three states in one request.

**Verify every parameter you construct.** A wrong table or line does not fail
silently: it exits 3 with the API's own message, which counts towards the
30-errors-per-minute limit. Prefer the cached discovery commands to guessing.

---

## 4. Fetching exactly what you need

### 4.1 Pick the time window

| Need | Flags | Notes |
| --- | --- | --- |
| The newest value | `dismal bea latest DATASET ...` | requests the last three calendar years and keeps the newest row per series |
| Recent context | `--years N` | the last N calendar years including this one |
| A specific span | `--start 2021-01 --end 2024-Q2` | inclusive; also `YYYY`, `YYYY-Qn`, `YYYY-Hn`, `2024Q2`, `2024M06` |
| Everything since a date | `--start 2000` | runs to the current year |
| Full history | `Year=ALL` | NIPA quarterly GDP back to 1947; county tables can be tens of MB |
| The API's own shortcuts | `Year=LAST5`, `Year=LAST10` | where the dataset supports them (Regional does) |

With no date flags the last three calendar years are requested. A period is
kept when any part of it overlaps the range, so `--start 2020-06` keeps the
2020 annual value and 2020Q2.

**Fetch a cushion for comparisons.** To compute a year-over-year change
yourself, start a year before the first row you need (four quarters, twelve
months). The same applies to rolling averages.

### 4.2 Pick the frequency

`-F/--frequency` takes `A`, `Q` or `M` (or `annual`, `quarterly`,
`monthly`) and is repeatable; `ITA` and `IIP` use `QSA`/`QNSA`. Most NIPA
tables exist annually and quarterly; the section-2 monthly tables exist
monthly, quarterly and annually. Ask for one frequency per fetch unless you
want mixed rows (`frequency` tells them apart; the wide layout then has a row
per period of each kind). `dismal bea values NIPA Year --filter TableName=...`
shows which frequencies a table has and from which year.

### 4.3 Let the table do the arithmetic

BEA publishes most derived measures as their own tables, computed the right
way (Fisher indexes, chained dollars, contributions). Prefer them to your own
arithmetic:

| You want | Use the table | Not |
| --- | --- | --- |
| Growth of real GDP or its components | `T10101` (percent change, annual rate) | percent changes of `T10105` (those are nominal) |
| What contributed how much to growth | `T10102` (percentage points, additive) | growth rates of chained-dollar components (not additive) |
| Real levels | `T10106` chained dollars | deflating `T10105` yourself |
| Inflation | `T20804`/`T20304`/`T10104` price indexes, then compute percent changes | the "implicit" ratio of nominal to real, unless you want the deflator (`T10109`) |
| Shares of GDP by industry | `GDPbyIndustry` table `5` | dividing table `1` by GDP yourself (fine, but the table exists) |

What you still compute yourself: year-over-year changes of indexes and
levels, annualized changes from monthly indexes, ratios across series, per
capita figures not in `T70100`, rankings and gaps across states.

### 4.4 Shape and format

| Use | Flags |
| --- | --- |
| Analysis in pandas, R or SQL; several measures per series | default long layout, `--format json`, `csv` or `parquet` |
| A spreadsheet, a chart, or arithmetic across series | `--layout wide --format csv` (one column per series id) |
| Streaming, line-by-line processing, appending to logs | `--format jsonl` |
| A local data store | `--format parquet -o file.parquet` |
| Reading at a terminal | `--format table` (the default on a TTY) |
| Only some columns | `--columns series_id,series_title,period,value` |
| The table's footnotes | `--notes` (adds a `notes` column; `note_ref` is always present) |

The wide layout carries only values: titles, units and notes are dropped, and
the columns are series ids (`A191RL`, `SAINC1-1:06000`). Use the long layout,
or `dismal bea tables show`, to map ids to titles.

`dismal bea data` never caches observations, so every call costs a request. For
iterative analysis, pull once to Parquet or CSV and work from the file.

### 4.5 Budget your requests

There is no daily quota. A key may make 100 requests, receive 100 MB and
cause 30 errors per minute; exceeding any of these blocks the key for one
hour (exit code 4). A `dismal bea data` call is one request per `--table` value;
everything else is one request.

| Call | Requests | Size |
| --- | --- | --- |
| `dismal bea latest NIPA -t T10101 -F Q` | 1 | small |
| `dismal bea data NIPA -t T10105 -t T10106 -F Q --years 10` | 2 | small |
| `dismal bea data NIPA -t T10105 -F Q Year=ALL` | 1 | a few MB (every quarter since 1947) |
| `dismal bea data Regional -t SAINC1 -l 1 -g STATE --years 10` | 1 | small |
| `dismal bea data Regional -t CAINC1 -l 1 -g COUNTY Year=ALL` | 1 | tens of MB; keep the years narrow |
| `dismal bea search`, cached `dismal bea tables list` / `dismal bea values` / `dismal bea datasets show` | 0 | |

Errors are the limit to watch: a loop that guesses line codes can hit 30
errors in a minute. Resolve parameters from the cached metadata first.

---

## 5. Recipes: from data to answers

Each recipe states the question, the table, the command and the arithmetic.
Table ids come from the curated catalog; line titles and series ids are as
published and are easy to confirm with `dismal bea tables show`. Results change with
every release, so no outputs are shown.

### 5.1 Setup

```bash
export BEA_API_KEY=...        # free: https://apps.bea.gov/API/signup/
```

Simple answers need only `dismal bea` and `jq`. For arithmetic across rows or
series, a small pandas helper keeps the recipes short:

```python
import json
import subprocess

import pandas as pd


def bea(*args: str) -> pd.DataFrame:
    """Run a `dismal bea` command and return its JSON output as a DataFrame."""
    proc = subprocess.run(
        ["dismal", "bea", *args, "--format", "json"], capture_output=True, text=True, check=True
    )
    df = pd.DataFrame(json.loads(proc.stdout))
    if "date" in df.columns:
        df["date"] = pd.to_datetime(df["date"])
    return df


def wide(*args: str) -> pd.DataFrame:
    """One column per series id, indexed by the period's first day."""
    return bea(*args, "--layout", "wide").set_index("date").drop(columns=["year", "period"])
```

Changes below are computed by shifting the *dates* (`s.shift(4, freq="QS")`
for four quarters, `s.shift(12, freq="MS")` for twelve months), not the rows,
so a missing period produces a gap instead of silently comparing the wrong
periods.

You can also skip the subprocess and use the library directly; see
[python-api.md](python-api.md).

### 5.2 Growth and GDP

#### How fast did the economy grow last quarter?

Table 1.1.1 is the headline: real GDP and its components, percent change from
the preceding quarter at a seasonally adjusted annual rate.

```bash
dismal bea latest NIPA --table T10101 --frequency Q \
  --columns series_id,series_title,period,value,unit --format csv
```

Read the row whose `series_id` is `A191RL` (line 1, "Gross domestic
product"). The number is an *annual rate*: 3.0 means the economy grew at a
pace that would compound to 3.0% over a year, not that it grew 3.0% in the
quarter. The other rows are the components (personal consumption
expenditures `DPCERL`, investment, exports, imports, government).

#### Is growth speeding up or slowing down?

Compare the latest annualized quarterly rate with the four-quarter (year over
year) change, computed from real GDP in chained dollars:

```python
real = wide("data", "NIPA", "-t", "T10106", "-F", "Q", "--years", "4")["A191RX"]
yoy = (real / real.shift(4, freq="QS") - 1) * 100
qoq_ann = ((real / real.shift(1, freq="QS")) ** 4 - 1) * 100
print(pd.DataFrame({"q/q annualized": qoq_ann, "y/y": yoy}).dropna().tail(6).round(1))
```

A quarterly rate above the year-over-year rate means growth is picking up.
The quarterly rates you compute this way match `T10101` to rounding.

#### What drove growth?

Contributions are additive percentage points of the headline rate:

```bash
dismal bea latest NIPA -t T10102 -F Q --columns line_number,series_title,period,value --format csv
```

Line 1 is the total (equal to real GDP growth); the indented lines below it
are the contributions of consumption, investment (including the change in
inventories), net exports and government. Use these, not growth rates of
chained-dollar components, when you say "consumer spending accounted for
most of the growth" ([section 6.2](#62-nominal-real-and-chained-dollars)).

#### How big is the economy?

```bash
dismal bea latest NIPA -t T10105 -t T10106 -F Q --columns series_id,series_title,period,value,unit,unit_mult --format csv
```

`A191RC` (table `T10105`) is GDP in current dollars and `A191RX` (`T10106`)
real GDP in chained 2017 dollars, both in millions (`unit_mult` 6) at an
annual rate. Divide by one million for trillions. Report the quarter and say
"seasonally adjusted annual rate".

#### GDP per capita and population

Table 7.1 has per capita GDP and income in current and chained dollars with
the population used to compute them:

```bash
dismal bea latest NIPA -t T70100 -F Q --columns line_number,series_title,period,value,unit --format csv
```

#### Annual growth, and growth over a decade

Use the annual rows of `T10101` for calendar-year growth. For cumulative
growth, divide chained-dollar levels; do not add up annual rates:

```bash
dismal bea data NIPA -t T10106 -F A --start 2014 --end 2024 --format json --columns series_id,year,value \
  | jq '[.[] | select(.series_id == "A191RX")] | (.[-1].value / .[0].value - 1) * 100'
```

#### GDP versus GDI

Gross domestic income measures the same economy from the income side and can
diverge from GDP for several quarters. Table 1.17.1 shows both growth rates
and their average; `T11000` has GDI by type of income.

```bash
dismal bea latest NIPA -t T11701 -F Q --columns line_number,series_title,period,value --format csv
```

### 5.3 Inflation: PCE price indexes

#### What is PCE inflation?

The Federal Reserve's preferred inflation measure is the 12-month change in
the PCE price index; "core" excludes food and energy. Table 2.8.4 has the
monthly indexes (2017=100):

```python
p = wide("data", "NIPA", "-t", "T20804", "-F", "M", "--years", "3")
yoy = (p / p.shift(12, freq="MS") - 1) * 100
print(yoy[["DPCERG", "DPCCRG"]].dropna().tail(3).round(1))   # headline, core
```

`DPCERG` is the PCE price index and `DPCCRG` the index excluding food and
energy. For the quarterly measure (what the GDP release reports) use `T20304`
and shift by four quarters.

#### Is inflation speeding up or slowing down?

Annualize short-run changes of the index and compare them with the 12-month
rate:

```python
core = wide("data", "NIPA", "-t", "T20804", "-F", "M", "--years", "3")["DPCCRG"]
ann_1m = ((core / core.shift(1, freq="MS")) ** 12 - 1) * 100
ann_3m = ((core / core.shift(3, freq="MS")) ** 4 - 1) * 100
yoy = (core / core.shift(12, freq="MS") - 1) * 100
print(pd.DataFrame({"1m_ann": ann_1m, "3m_ann": ann_3m, "12m": yoy}).dropna().tail(6).round(1))
```

Short-run rates above the 12-month rate mean inflation is accelerating.
Monthly PCE indexes are revised with each release and in the annual update,
so the latest few months move.

#### What is driving PCE inflation?

Compare 12-month changes of the major types of product in the same table:
goods, durable goods, nondurable goods, services, and the addenda for food and
energy. `dismal bea tables show NIPA T20804` lists the lines; `T20807` gives BEA's
own monthly percent changes.

#### The GDP deflator and the PCE-CPI gap

Table 1.1.4 has price indexes for GDP and its components (`A191RG` for GDP);
Table 1.1.7 the corresponding percent changes. The PCE price index usually
runs below the CPI because of its weights, its broader scope (including
spending made on households' behalf) and its formula; when the question is
"inflation" without qualification, say which measure you used and that the
CPI is a BLS statistic.

### 5.4 Income, spending and saving

#### Personal income and the saving rate

Table 2.6 is the monthly income statement of the household sector:

```bash
dismal bea latest NIPA -t T20600 -F M --columns line_number,series_id,series_title,period,value,unit --format csv
```

Read "Personal income" (`A065RC`), "Disposable personal income" (`A067RC`),
"Personal consumption expenditures" (`DPCERC`) and "Personal saving as a
percentage of disposable personal income" (`A072RC`, the saving rate). Levels
are at a seasonally adjusted annual rate, scaled by `unit_mult`; check it,
because the API's scale can differ from the printed table's billions.

For income growth, use percent changes of levels in the same table over 12
months, or the quarterly table `T20100` with its annual rows.

#### Are consumers still spending?

Real PCE growth by major type of product, quarterly at annual rates:

```bash
dismal bea data NIPA -t T20301 -F Q --years 3 --layout wide --format csv
```

Monthly, in chained dollars (`T20806`) or current dollars (`T20805`):

```python
pce = wide("data", "NIPA", "-t", "T20806", "-F", "M", "--years", "2")
print((pce / pce.shift(1, freq="MS") - 1).mul(100).round(2).tail(6))   # month-over-month, %
```

#### Spending on a particular product

The underlying-detail tables break PCE into hundreds of products
(`U20405` current dollars, `U20406` chained dollars, `U20404` price indexes).
They are large; narrow with `--columns` and read line titles with
`dismal bea tables show NIUnderlyingDetail U20405` first.

### 5.5 Government, trade and investment in the accounts

```bash
dismal bea latest NIPA -t T30100 -F Q --columns line_number,series_title,period,value --format csv   # receipts, expenditures, net lending
dismal bea latest NIPA -t T40100 -F Q --columns line_number,series_title,period,value --format csv   # exports, imports, net exports
dismal bea data NIPA -t T50305 -t T50306 -F Q --years 3 --columns table_name,series_id,series_title,period,value --format csv  # fixed investment, nominal and real
dismal bea latest NIPA -t T11200 -F Q --columns line_number,series_title,period,value --format csv   # national income: compensation, profits, ...
dismal bea latest NIPA -t T61600D -F Q --columns line_number,series_title,period,value --format csv  # corporate profits by industry
```

Government "net lending or net borrowing" in `T30100` is the accounts'
measure of the deficit and differs from the Treasury's budget deficit in
coverage and timing. Corporate profits appear only with the second GDP
estimate, so their latest quarter lags GDP's by a month.

### 5.6 Industries

#### Which industries are growing?

Value added by industry in current dollars (table `1`) and real terms (table
`10`), annual and quarterly; quantity indexes (table `8`) for growth rates:

```python
q = wide("data", "GDPbyIndustry", "-t", "8", "-F", "A", "--industry", "ALL", "--years", "4")
growth = (q / q.shift(1, freq="YS") - 1) * 100
print(growth.iloc[-1].sort_values(ascending=False).round(1).head(10))
```

Columns are `8:<industry code>`; map codes to names with the long layout
(`series_title`) or `dismal bea values GDPbyIndustry Industry`. Common codes: `11`
agriculture, `21` mining, `22` utilities, `23` construction, `31G`
manufacturing, `42` wholesale, `44RT` retail, `48TW` transportation, `51`
information, `52` finance and insurance, `53` real estate, `54` professional
services, `62` health care, `72` accommodation and food, `G` government,
`PVT` private industries, `GDP` all industries.

#### What share of GDP is manufacturing?

```bash
dismal bea data GDPbyIndustry -t 5 -F A --industry 31G --industry 52 --industry 53 --years 5 --layout wide --format csv
```

Table `5` is value added as a percentage of GDP, so the values are shares in
percent; compare across years as point differences.

### 5.7 States, metros and counties

All states come back in one request with `--geo STATE`; the series id is
`<table>-<line>:<fips>` and `series_title` is the state name.

#### Rank states by GDP growth

```python
g = wide("data", "Regional", "-t", "SQGDP9", "--line", "1", "--geo", "STATE", "--years", "3")
yoy = (g / g.shift(4, freq="QS") - 1) * 100
latest = yoy.dropna(how="all").iloc[-1].sort_values(ascending=False)
print(latest.round(1).head(10))
```

`SQGDP9` is quarterly real GDP by state (chained dollars, annual rate); line
1 is all industries. For annual growth use `SAGDP9N`. Column labels are
`SQGDP9-1:<fips>`; join to names from the long layout if you need them.

#### Personal income per capita by state, and the cost of living

```bash
dismal bea latest Regional -t SAINC1 --line 3 --geo STATE --columns series_title,period,value,unit --format csv
dismal bea latest Regional -t SARPP --line 1 --geo STATE --columns series_title,period,value --format csv
```

`SAINC1` line 3 is per capita personal income in dollars (line 1 total
income in thousands of dollars, line 2 population). `SARPP` line 1 is the
all-items regional price parity, an index with the U.S. at 100 that says how
much more or less things cost in a state; dividing income by RPP/100 gives a
cost-of-living-adjusted comparison (BEA publishes it directly as `SARPI`).

#### Compare a state with the nation

```bash
dismal bea data Regional -t SQINC1 --line 1 --geo 00000,06000,48000 --years 5 --layout wide --format csv
```

`00000` is the United States. Quarterly state personal income is in millions
of dollars at an annual rate; compute percent changes before comparing.

#### A county

```bash
dismal bea values Regional GeoFips --query "travis"          # 48453 = Travis County, TX
dismal bea data Regional -t CAINC1 --line 3 --geo 48453 --years 10 --format csv
dismal bea data Regional -t CAGDP9 --line 1 --geo 48453 --years 10 --format csv
```

County data are annual, published about eleven months after the year ends,
and small-county cells can be suppressed `(D)`. `--geo COUNTY` fetches every
county (3,000+ rows per year): keep the years narrow.

#### Metro areas

```bash
dismal bea tables list Regional --query "metropolitan"
dismal bea values Regional GeoFips --query "austin"
```

Metro tables are the `MA*` family (`MAGDP2`, `MAINC1`, `MARPP`, ...) with
5-digit metro codes.

### 5.8 Trade and the international accounts

#### The trade deficit and the current account

```bash
dismal bea data ITA Indicator=BalGds,BalServ,BalGdsServ,BalCurrAcct AreaOrCountry=AllCountries \
  -F QSA --years 3 --layout wide --format csv
```

Balances are millions of dollars; a negative balance is a deficit. `QSA` is
seasonally adjusted quarterly, `QNSA` not adjusted, `A` annual. Quarterly ITA
data come out about two and a half months after the quarter ends.

#### Trade with one country

```bash
dismal bea values ITA AreaOrCountry --query china                      # the exact key
dismal bea data ITA Indicator=ExpGdsServ,ImpGdsServ,BalGdsServ AreaOrCountry=China -F A --years 5 --layout wide --format csv
```

Country detail is annual and quarterly not seasonally adjusted (`A`, `QNSA`);
if `-F QSA` returns nothing for a country, that is why.

#### The net international investment position

```bash
dismal bea data IIP TypeOfInvestment=Net,FinAssets,FinLiabs Component=Pos -F QNSA --years 3 --layout wide --format csv
```

Positions are end-of-period stocks in millions of dollars; `Net` is assets
minus liabilities.

### 5.9 Monitoring and pipelines

#### Has anything new been released?

Keep a watchlist of commands and compare the latest periods with the last run:

```bash
touch latest.jsonl
{
  dismal bea latest NIPA -t T10101 -F Q --strict --format jsonl --columns series_id,period,value
  dismal bea latest NIPA -t T20804 -F M --strict --format jsonl --columns series_id,period,value
} > latest.new.jsonl || exit
if ! cmp -s latest.new.jsonl latest.jsonl; then
  diff latest.jsonl latest.new.jsonl || true   # new periods or revised values
  mv latest.new.jsonl latest.jsonl
fi
```

`|| exit` keeps a failed call (rate limit, network) from replacing the last
good snapshot. Two requests, cheap to run daily. GDP and the monthly income
and outlays reports are published at 8:30 a.m. Eastern.

#### Keep a local data set current

Revisions mean appending only the newest row leaves stale history behind.
Each run, re-pull a window that covers the revision period and replace those
rows; the annual update each September revises at least the previous three
years, so four years is a safe window. Pull deep history (`Year=ALL`) only
once.

```bash
dismal bea data NIPA -t T10101 -t T10105 -t T10106 -F Q --years 4 --strict --format parquet -o nipa_recent.parquet
```

[`examples/bea/github-actions/weekly-pull.yml`](../../examples/bea/github-actions/weekly-pull.yml)
is a scheduled workflow that does this and commits the files.

---

## 6. Reading BEA data correctly

### 6.1 Annual rates

Quarterly and monthly NIPA *flows* (GDP, income, spending, investment) are
expressed at seasonally adjusted annual rates: the quarter's value multiplied
by four (the month's by twelve) after seasonal adjustment. Quarterly growth
rates in the `.1` tables are annualized too: the quarter-over-quarter change
compounded over four quarters. Say "at an annual rate" when you report either.
Stocks (fixed assets, the investment position) and annual data are not
annualized.

### 6.2 Nominal, real and chained dollars

- **Current dollars** (`.5` tables) are what was actually paid; they grow
  with prices and volumes.
- **Chained (2017) dollars** (`.6` tables) remove price change using a
  chain-weighted Fisher index. Use them for growth and volumes.
- **Chained-dollar components do not add up** to the chained-dollar total
  (the residual grows away from 2017). Never compute a share or a
  contribution from chained dollars; use the `.2` contributions tables for
  "what drove growth" and current dollars for shares.
- **Index levels are not comparable across series** unless they share a base;
  compare percent changes, or rebase each to a common period.
- **Implicit price deflators** (`T10109`) are the ratio of nominal to real;
  the chain-type price indexes (`T10104`) are the primary price measures.

### 6.3 Units and magnitudes

Every row carries `unit` and `unit_mult`, the power of ten the value is
expressed in. NIPA levels come back in millions of dollars (`unit_mult` 6)
even where the printed table shows billions; percent changes and shares are
`unit_mult` 0; Regional income is thousands of dollars (3), per capita figures
dollars (0), state GDP millions (6), county GDP thousands (3). Read
`unit_mult` rather than assuming: `value * 10 ** unit_mult` is the figure in
dollars (or persons). Report the units BEA uses ("billions of dollars at an
annual rate") rather than converting silently.

### 6.4 Vintages and revisions

The API always returns the current vintage; a value pulled last month may have
changed since.

- **Quarterly GDP** is published three times: the *advance* estimate about
  four weeks after the quarter ends, the *second* about eight weeks, the
  *third* about twelve weeks. Each can move the growth rate by several tenths.
- **Monthly income and spending** and the **PCE price index** are revised
  with each of the next releases.
- **The annual update** every September revises the previous three years (and
  sometimes more) of all the national tables; the regional and industry
  accounts follow in the weeks after.
- **Comprehensive updates** every five years or so (most recently September
  2023) can change definitions, methods and the reference year for chained
  dollars (currently 2017), revising the whole history.
- **Regional** annual state data are revised in September, county and metro
  data when they are next published.

Practice: record the retrieval date with every result; say which estimate
(advance, second, third) a quarter is on when it matters; for "as first
published" questions use a vintage archive (ALFRED) or the news-release
archive on bea.gov.

### 6.5 Release timing

"Latest" is the latest *published* period, and it differs by dataset.
Approximate lags; see the BEA release schedule for exact dates:

| Release | Dataset / tables | Published |
| --- | --- | --- |
| GDP (advance, second, third) | `NIPA` quarterly tables | about 4, 8 and 12 weeks after the quarter ends (late January, April, July, October for the advance estimate) |
| Corporate profits | `NIPA` `T11200`, `T61600D` | with the second and third GDP estimates |
| Personal income and outlays (income, PCE, PCE prices) | `NIPA` `T20600`, `T20801`-`T20807` | about four weeks after the month ends |
| GDP by industry | `GDPbyIndustry` | about three months after the quarter ends, alongside a later GDP estimate; annual update in September |
| GDP by state, state personal income (quarterly) | `Regional` `SQGDP*`, `SQINC*` | about three months after the quarter ends |
| State annual GDP and personal income, RPPs | `Regional` `SA*` | September (income), December (RPPs) |
| County and metro income and GDP | `Regional` `CA*`, `MA*` | November and December for the previous year |
| International transactions | `ITA` | about two and a half months after the quarter ends (March, June, September, December) |
| Investment position | `IIP` | about three months after the quarter ends |
| Fixed assets | `FixedAssets` | annually, after the annual update |
| Direct investment and multinationals | `MNE` | annually, one to two years after the reference year |
| Input-output tables | `InputOutput` | annually, about a year after the reference year |

Consequences: always report the period with the value; when combining series
(ratios, real values, state versus nation), align on dates and drop periods
where one side is missing.

### 6.6 Which inflation, which growth

- **PCE price index versus CPI.** The PCE index (BEA) and the CPI (BLS)
  differ in weights, scope and formula; the PCE index usually runs lower. The
  Fed targets PCE; many contracts and the public use the CPI. Name the one
  you report.
- **GDP versus GDI.** Two measures of the same economy that diverge in the
  short run; `T11701` shows both and their average.
- **Quarterly versus annual growth.** A calendar-year growth rate (annual rows
  of `T10101`) compares year averages; the "Q4 over Q4" rate compares end
  points. They differ, sometimes by a lot.
- **State GDP versus personal income.** GDP measures production in the state;
  personal income measures what residents receive, including from elsewhere.

### 6.7 Seasonal adjustment

National quarterly and monthly tables are seasonally adjusted; annual data
need no adjustment. In `ITA`, `QSA` is adjusted and `QNSA` is not, and
country detail is `QNSA` only; `IIP` is `QNSA`. Regional quarterly tables
(`SQ*`) are adjusted. Compare unadjusted quarters with the same quarter a year
earlier, not the previous quarter.

### 6.8 Suppressed and missing values

`value` is `null` when BEA reports `(D)` (suppressed to avoid disclosing
individual companies' data, common in county and industry detail), `(NA)`,
`(*)` or a blank; `raw_value` keeps the marker in the Python API, and `--raw`
shows it. A table that has no data for a frequency or year returns no rows
(exit 6 with `--strict`); the API also answers some bad parameters with an
error (exit 3) rather than an empty set. Date-aligned arithmetic
(`shift(..., freq=...)`) keeps a gap from shifting comparisons.

### 6.9 Geography codes and names

Regional output carries `geo_fips` and the name in `series_title`. States are
the 2-digit FIPS plus `000`; counties the 5-digit FIPS; metros the 5-digit
CBSA code; `00000` is the United States. County boundaries and metro
definitions change occasionally (Connecticut's planning regions replaced its
counties in BEA data from 2024); check `dismal bea values Regional GeoFips` when a
code returns nothing.

---

## 7. Using `dismal bea` from an agent

[agents.md](agents.md) is the contract (invariants, exit codes, schema);
[`examples/skill/SKILL.md`](../../examples/skill/SKILL.md) is a ready-made skill.
This section is the judgment layer on top: how to turn a user's question into
a correct, sourced answer with the fewest requests.

### 7.1 Protocol

1. **Classify the request.** Latest value, change, history, comparison,
   derived metric (growth, shares, per capita, rankings), or not BEA data
   (CPI, unemployment, interest rates, monthly trade). For the last, say so
   and stop.
2. **Frame it** with the table in [section 2](#2-the-research-workflow):
   measure, nominal or real, geography, frequency, time span, transformation.
3. **Resolve the table and parameters, cheapest first.**
   - Check the [question playbook](#8-question-playbook).
   - `dismal bea search "<concept>" --limit 5 --format json`. Accept the top hit if
     its score is at least 90 and its `units` match the framed measure; take
     its `command` as the starting point.
   - Otherwise reformulate in BEA vocabulary
     ([section 3.1](#31-write-queries-in-bea-vocabulary)) and retry once, then
     `dismal bea tables list DATASET --query ...`.
   - Confirm lines and parameters from the cache: `dismal bea tables show`,
     `dismal bea values ... --filter`. Never guess a line code, geography or
     industry; a wrong one costs an error and a request.
   - If several tables remain plausible (levels versus growth, nominal versus
     real), show them to the user and ask.
4. **Plan one fetch.** All tables in one call (`--table` is repeatable); the
   narrowest window that covers the comparison (plus a year's cushion when
   computing changes yourself); `latest` when only the current value matters.
5. **Run it** with `--format json` (or `jsonl`) and `--strict`. Parse stdout
   only. Handle the exit code ([section 7.3](#73-exit-codes)).
6. **Compute in code**, never by eye. Align series on `date`; use `unit_mult`.
7. **Sanity-check.** Is the period what you expected? Is the value an annual
   rate? Units right (millions, billions, percent, index)? Magnitude
   plausible? Any `null` values? Do the series' latest periods differ?
8. **Answer** with the template in [section 7.4](#74-answer-template).

### 7.2 Decision rules

| Situation | Rule |
| --- | --- |
| "GDP growth" with no qualifier | `T10101` line 1 (`A191RL`), latest quarter, "at a seasonally adjusted annual rate" |
| "How big is GDP" | `T10105` `A191RC` (current dollars) unless "real" is asked; convert millions to trillions and say "annual rate" |
| "Inflation" | PCE price index `T20804` `DPCERG`, 12-month change; mention core `DPCCRG`; say that the CPI is BLS data |
| "Consumer spending" | `T20301` for growth, `T20805`/`T20806` for levels |
| "Personal income", "saving rate" | `T20600` `A065RC` / `A072RC` |
| "What drove growth" | `T10102` contributions, never component growth rates |
| A state or county | `Regional`; income `SAINC1`/`CAINC1`, GDP `SQGDP9`/`SAGDP9N`/`CAGDP9`; `--geo` from `dismal bea values` |
| A share, a rate or a contribution changed | report percentage points |
| A level or index changed | report percent; say "annualized" when you compounded |
| Nominal and real both available | real for growth, nominal for sizes and shares |
| Series with different latest periods | report each with its own period; align before combining |
| A quarter on its advance estimate | say "advance estimate; revised twice in the next two months" |
| `null` values | say "suppressed" or "not available"; do not interpolate |
| No key (`dismal bea config` shows `api_key: "(not set)"`) | stop: every live request needs `BEA_API_KEY` |
| User asks for a forecast | BEA data describe the past; say so, and offer the relevant history |

### 7.3 Exit codes

| Code | Do |
| --- | --- |
| 0 | parse stdout |
| 2 | your command is wrong: read stderr; it names a missing parameter, a bad date or an unknown column |
| 3 | the API rejected a table, line or parameter (its message is on stderr): fix it from `dismal bea tables list` / `dismal bea values`; do not retry blindly |
| 4 | rate limit: the key is blocked for an hour; stop and tell the user |
| 5 | network: retry once after a pause |
| 6 | (`--strict`) no rows: the table lacks that frequency or year; check `dismal bea values NIPA Year --filter TableName=...` |
| 7 | configuration: `BEA_API_KEY` missing or rejected |

### 7.4 Answer template

```
<Measure> was <value> <units> in <period> (<seasonally adjusted annual rate | annual | ...>), per BEA's <advance | second | third | latest> estimate.
<Change, in points for rates and shares or percent for levels and indexes, with the comparison period and whether it is annualized>.
<One caveat if it matters: a coming revision, suppressed cells, a different latest period, nominal versus real>.
Source: U.S. Bureau of Economic Analysis, <dataset> table <TABLE> line <N> (series <ID>); retrieved <YYYY-MM-DD>.
```

Always include the period and the table and line (or series id); a number
without them cannot be checked. BEA data are public domain; the API's
[terms of service](https://apps.bea.gov/API/_pdf/BEA_API_Terms_of_Service.pdf)
ask that published applications credit BEA as the source.

### 7.5 Worked examples

**"How fast is the economy growing, and is that faster than last year?"**

```bash
dismal bea search "gdp growth" --limit 3 --format json      # T10101, score 100, command included
dismal bea data NIPA -t T10101 -F Q --years 2 --strict --format json --columns series_id,period,value \
  | jq '[.[] | select(.series_id == "A191RL")] | {latest: .[-1], year_ago: .[-5]}'
```

Answer: "Real GDP grew at a {latest.value}% seasonally adjusted annual rate in
{latest.period}, compared with {year_ago.value}% in {year_ago.period}. Source:
BEA NIPA table 1.1.1 line 1 (A191RL); retrieved {today}." Name the estimate
(advance, second, third) if the quarter is recent.

**"What is core inflation by the Fed's measure?"**

```bash
dismal bea data NIPA -t T20804 -F M --years 2 --strict --format json --columns series_id,period,value \
  | jq '[.[] | select(.series_id == "DPCCRG")] | {period: .[-1].period, yoy: ((.[-1].value / .[-13].value - 1) * 100)}'
```

Answer with the percent to one decimal and the month, naming the series as the
PCE price index excluding food and energy (NIPA table 2.8.4). `.[-13]` is the
same month a year earlier only if no month is missing; the pandas recipe in
[section 5.3](#53-inflation-pce-price-indexes) aligns by date.

**"Which states have the highest income per person?"**

Run `dismal bea latest Regional -t SAINC1 --line 3 --geo STATE --strict --format
json`, sort by `value`, and report the top states with the year, noting that
state income per capita is annual and not adjusted for price differences
(`SARPP` or the `SARPI` tables for that).

**"What was the CPI last month?"**

Not BEA data: the CPI is a BLS statistic. Say so and offer the PCE price
index instead of substituting it silently (or run `dismal bls latest CUUR0000SA0`).

### 7.6 Anti-patterns

- Calling `dismal bea data` once per table in a loop (one call takes several
  `--table` values) or once per state (one `--geo STATE` call returns all).
- Fetching `Year=ALL` of a county table when the question needs one year.
- Guessing line codes, geographies or industries instead of reading them from
  the cache; the errors count towards the hourly block.
- Reporting an annualized quarterly rate as a quarterly change, or a
  quarterly change as an annual one.
- Computing shares or contributions from chained dollars.
- Comparing index levels across series, or nominal levels across years as if
  they were volumes.
- Forgetting `unit_mult`: a NIPA level of 27,720,709 is millions, so $27.7
  trillion.
- Combining series without aligning dates (state data lag national data by
  months).
- Treating an advance estimate as final.
- Parsing stderr, or relying on the default output format.
- Passing `-F` to `dismal bea values` expecting a frequency: there it means
  `--filter`.

---

## 8. Question playbook

Starting points for common questions. Add a time range or `--latest`; the
commands fetch the whole table, and `--columns` or a `series_id` filter picks
the line.

| Question | Command | Read |
| --- | --- | --- |
| Real GDP growth, latest quarter | `dismal bea latest NIPA -t T10101 -F Q` | `A191RL`, percent, annual rate |
| Real GDP growth, calendar year | `dismal bea data NIPA -t T10101 -F A --years 3` | `A191RL` |
| What drove growth | `dismal bea latest NIPA -t T10102 -F Q` | contributions, percentage points |
| GDP in dollars | `dismal bea latest NIPA -t T10105 -F Q` | `A191RC`, millions, annual rate |
| Real GDP level | `dismal bea latest NIPA -t T10106 -F Q` | `A191RX`, millions of chained 2017 dollars |
| GDP price index, deflator | `dismal bea latest NIPA -t T10104 -F Q`, `-t T10109` | `A191RG`; 2017=100 |
| GDP per capita, population | `dismal bea latest NIPA -t T70100 -F Q` | current and chained dollars |
| GDP and GDI growth | `dismal bea latest NIPA -t T11701 -F Q` | both and their average |
| PCE inflation (headline, core), monthly | `dismal bea data NIPA -t T20804 -F M --years 2` | `DPCERG`, `DPCCRG`; compute the 12-month change |
| PCE inflation, quarterly | `dismal bea data NIPA -t T20304 -F Q --years 2` | compute the 4-quarter change |
| Personal income, DPI, saving rate | `dismal bea latest NIPA -t T20600 -F M` | `A065RC`, `A067RC`, `A072RC` |
| Consumer spending growth | `dismal bea latest NIPA -t T20301 -F Q` | real PCE by type, annual rate |
| Consumer spending levels, monthly | `dismal bea latest NIPA -t T20805 -F M` (`T20806` real) | billions, annual rate |
| Spending on a product | `dismal bea tables show NIUnderlyingDetail U20405`, then `dismal bea data NIUnderlyingDetail -t U20405 -F M` | line titles |
| Government receipts, spending, net lending | `dismal bea latest NIPA -t T30100 -F Q` | millions, annual rate |
| Exports, imports, net exports | `dismal bea latest NIPA -t T40100 -F Q` | millions, annual rate |
| Business investment | `dismal bea latest NIPA -t T50305 -F Q` (`T50306` real) | by type |
| Corporate profits | `dismal bea latest NIPA -t T11200 -F Q`, `-t T61600D` | lags GDP by a month |
| Compensation, wages by industry | `dismal bea latest NIPA -t T60200D -F Q`, `-t T20200B` | |
| Value added by industry | `dismal bea data GDPbyIndustry -t 1 -F A --industry ALL --years 3` | billions |
| Industry shares of GDP | `dismal bea data GDPbyIndustry -t 5 -F A --industry ALL --years 3` | percent |
| Real growth by industry | `dismal bea data GDPbyIndustry -t 8 -F A --industry ALL --years 4` | quantity indexes; compute changes |
| State real GDP growth | `dismal bea data Regional -t SQGDP9 --line 1 --geo STATE --years 3` | compute the 4-quarter change |
| State GDP, annual | `dismal bea data Regional -t SAGDP2N --line 1 --geo STATE --years 5` (`SAGDP9N` real) | millions |
| State personal income, population, per capita | `dismal bea latest Regional -t SAINC1 --line 1 --geo STATE` (lines 2, 3) | thousands; persons; dollars |
| State income by component | `dismal bea latest Regional -t SAINC4 --line 10 --geo STATE` | `dismal bea values Regional LineCode --filter TableName=SAINC4` for the lines |
| State cost of living (RPP) | `dismal bea latest Regional -t SARPP --line 1 --geo STATE` | U.S. = 100 |
| State jobs by industry | `dismal bea latest Regional -t SAEMP25N --line 10 --geo STATE` | number of jobs |
| County income per capita | `dismal bea data Regional -t CAINC1 --line 3 --geo <fips> --years 10` | dollars; annual |
| County GDP | `dismal bea data Regional -t CAGDP9 --line 1 --geo <fips> --years 10` | thousands of chained dollars |
| Metro tables | `dismal bea tables list Regional --query metropolitan` | `MA*` tables, 5-digit metro codes |
| Trade balance, current account | `dismal bea data ITA Indicator=BalGdsServ,BalCurrAcct AreaOrCountry=AllCountries -F QSA --years 3` | millions; negative = deficit |
| Trade with a country | `dismal bea data ITA Indicator=ExpGdsServ,ImpGdsServ AreaOrCountry=<key> -F A --years 5` | key from `dismal bea values ITA AreaOrCountry` |
| Net international investment position | `dismal bea data IIP TypeOfInvestment=Net Component=Pos -F QNSA --years 3` | millions |
| Capital stock, investment in fixed assets | `dismal bea data FixedAssets -t FAAt101 --years 5`, `-t FAAt105` | billions |
| Foreign direct investment | `dismal bea datasets show MNE`, `dismal bea values MNE DirectionOfInvestment` | parameters vary; see the API guide |

---

## 9. Troubleshooting

| Symptom | Likely cause | Fix |
| --- | --- | --- |
| `dismal bea search` finds nothing | question words, or the table is not in the curated catalog | reformulate ([section 3.1](#31-write-queries-in-bea-vocabulary)); then `dismal bea tables list DATASET --query ...` |
| Exit 2 `NIPA needs the parameter(s): Frequency` | a required parameter is missing | add `-F A|Q|M`; `dismal bea datasets show DATASET` lists requirements |
| Exit 2 `expected PARAMETER=VALUE` | a positional that is not `NAME=VALUE` (for example a bare table id) | use `--table` or `TableName=...` |
| Exit 3 with the API's message | wrong table, line, geography, indicator or industry | look it up: `dismal bea tables list`, `dismal bea values ... --filter` |
| Exit 3 for every request, mentioning the UserId | key rejected | exit 7 is more usual; check `BEA_API_KEY` has 36 characters (`dismal bea doctor`) |
| Warning `no observations returned`, or exit 6 with `--strict` | the table has no rows for that frequency or year (monthly table with `-F Q`, a year before the series starts, country detail with `-F QSA`) | `dismal bea values NIPA Year --filter TableName=...`; change `-F` |
| Rows outside `--start/--end` | overlap rule: a quarter or year that overlaps the range is kept | add `-F Q`, or filter by `date` |
| Exit 2 `unknown column(s)` | `--columns` names a column that was not produced (`notes` without `--notes`, a dimension of another dataset) | the error lists the available columns |
| Exit 4 | more than 100 requests, 100 MB or 30 errors in a minute | wait an hour; stop guessing parameters |
| Exit 7 | `BEA_API_KEY` not set, or the API rejected it | register at <https://apps.bea.gov/API/signup/>; `dismal bea doctor` |
| Values look a thousand times too small or large | `unit_mult` ignored, or millions in one table and billions in another | read `unit` and `unit_mult` |
| Growth looks four times too high | a quarterly rate at an annual rate | say "annualized", or de-annualize: `(1 + r/100) ** 0.25 - 1` |
| Components do not sum to the total | chained dollars | use current dollars for shares and `T10102` for contributions |
| State or county data end a year or more ago | publication lag | expected; report the period |
| Output is a table in a script | the default format follows the terminal | always pass `--format` |
| `-F` did something unexpected on `dismal bea values` | there it is `--filter`, not `--frequency` | `dismal bea values DATASET PARAM --filter NAME=VALUE` |
| `dismal bea datasets -q` filters instead of going quiet | `-q` means `--query` on `datasets` | put the global flag first: `dismal bea -q data ...` |
| Latest periods differ across tables | different release schedules | expected; report each period |

`dismal bea doctor` checks the configuration and makes one live request; run it first
when something unexpected happens.

---

## 10. Further reading

In this repository:

- [usage.md](usage.md): every command and flag
- [agents.md](agents.md): the contract for automations and agents
- [table-ids.md](table-ids.md): datasets, tables and how to find them
- [output-formats.md](output-formats.md): record schemas per format
- [configuration.md](configuration.md): environment variables, limits, caching
- [python-api.md](python-api.md): using `dismal.bea.BEAClient` directly
- [../bls/practitioners-guide.md](../bls/practitioners-guide.md) and
  [../fred/practitioners-guide.md](../fred/practitioners-guide.md): the same
  guide for the BLS and FRED sources of `dismal`

From BEA:

- [BEA Data API](https://apps.bea.gov/API/signup/): registration,
  [documentation](https://apps.bea.gov/API/docs/index.htm) and the user guide
  with every dataset's parameters
- [Release schedule](https://www.bea.gov/news/schedule)
- [NIPA Handbook](https://www.bea.gov/resources/methodologies/nipa-handbook):
  concepts and methods of the national accounts
- [Measuring the Economy: A Primer on GDP and the NIPAs](https://www.bea.gov/resources/methodologies/measuring-the-economy)
- Methodology pages for the
  [regional](https://www.bea.gov/resources/methodologies/regional-economic-accounts),
  [industry](https://www.bea.gov/resources/methodologies/industry-economic-accounts)
  and [international](https://www.bea.gov/resources/methodologies/international-economic-accounts)
  accounts
- [Interactive data tables](https://apps.bea.gov/itable/), the same tables
  with footnotes and release notes

For data as originally published (vintages), see
[ALFRED](https://alfred.stlouisfed.org/) at the Federal Reserve Bank of St.
Louis.
