# Finding and reading FRED series ids

Every FRED series has a short id such as `UNRATE` (unemployment rate),
`CPIAUCSL` (CPI-U, all items, SA) or `DGS10` (10-year Treasury yield). Unlike
BLS and BEA ids they rarely encode structure; they are mnemonic, assigned by
the source or by FRED. `dismal fred` offers several routes to an id.

## 1. Offline fuzzy search: `dismal fred search`

```bash
dismal fred search "mortgage rates"
dismal fred search unemploymnt rate          # typos tolerated
dismal fred search "price of gas"            # everyday phrases, any word order
dismal fred search "yield curve"             # T10Y2Y
```

Searches a curated catalog of about 150 widely used series (national
accounts, labor market, prices and inflation expectations, policy and market
interest rates, credit spreads, money and the Fed's balance sheet, markets
and exchange rates, housing, fiscal, trade, recession indicators, a few
state unemployment rates). It is deliberately small and hand-checked; it is
not the universe of FRED series. Contributions to
`src/dismal/fred/data/series_catalog.json` are welcome; see
[development.md](../development.md#adding-a-series-to-the-curated-catalog) for
tags and everyday-phrase aliases.

## 2. All of FRED: `dismal fred series search`

```bash
dismal fred series search "median home price" --order-by popularity
dismal fred series search "unemployment rate" --frequency m --tag sa --tag usa
dismal fred series search "exports to china" -n 10
dismal fred series search DEX --id                      # ids starting with DEX (exchange rates)
```

The API's full-text search over every series, one request per query. Sort
by `popularity` when a plain-language query matches many detailed series;
use `--tag` (`usa`, `monthly`, `sa`, `nsa`, `bls`, `bea`, `frb`, ...) and
`--exclude-tag discontinued` to narrow.

## 3. By release or category

```bash
dismal fred releases -q "employment"           # 50 = Employment Situation
dismal fred releases series 50 -n 200          # every series in that release
dismal fred categories                         # the root of the tree
dismal fred categories children 32991          # Money, Banking, & Finance
dismal fred categories series 115              # Treasury constant-maturity yields
```

## 4. Describe an id: `dismal fred series info`

```bash
dismal fred series info UNRATE CPIAUCSL DGS10 --notes
```

Returns title, frequency, units, seasonal adjustment, first and last
observation, last update and popularity (and the notes, which explain
methodology and sources).

## Reading an id

There is no universal grammar, but families follow patterns:

| Pattern | Meaning | Examples |
| --- | --- | --- |
| BLS ids | FRED carries BLS series under their BLS ids or short mnemonics | `UNRATE` (= `LNS14000000`), `PAYEMS` (= `CES0000000001`), `CPIAUCSL`, `CUSR0000SEHA`, `LNS11300060` |
| BEA NIPA | `<series code><table digits>SBEA`, or a mnemonic | `A191RL1Q225SBEA` (real GDP % change), `GDP`, `GDPC1`, `PCE`, `PCEPI` |
| `DGS<n>` / `GS<n>` | daily / monthly constant-maturity Treasury yields, `n` years (`1MO`, `3MO`, `6MO` months) | `DGS10`, `GS2`, `DGS3MO` |
| `T<a>Y<b>M` / `T<a>Y<b>Y` | spreads between maturities | `T10Y2Y`, `T10Y3M` |
| `D<...>` | the daily version of a monthly series | `DFF` (`FEDFUNDS`), `DTB3` (`TB3MS`), `DPRIME` (`MPRIME`) |
| `DEX<ccy>US` / `DEXUS<ccy>` | exchange rates, units per dollar / dollars per unit | `DEXJPUS`, `DEXUSEU` |
| `BAML...` | ICE BofA bond index yields and spreads | `BAMLH0A0HYM2` |
| `<ST>UR`, `<ST>NGSP`, ... | state series: two-letter postal code plus a suffix | `CAUR`, `TXUR`, `CANGSP` |
| `...SA` / `...NSA`, `...SL` / `...NS` | seasonally adjusted / not | `CPIAUCSL` vs `CPIAUCNS`, `CSUSHPISA` vs `CSUSHPINSA` |
| `...96` | chained (real) dollars | `PCEC96`, `DSPIC96` |

When in doubt, `dismal fred series info ID` is authoritative: it says exactly what
the id measures, how often and in what units.

## Frequencies and seasonal adjustment

FRED series come in every frequency from daily to annual, with
`frequency_short` codes `D`, `W`, `BW`, `M`, `Q`, `SA`, `A`. `--frequency`
aggregates to a lower frequency on the server; it cannot raise one.
`seasonal_adjustment_short` is `SA`, `NSA` or `SAAR` (seasonally adjusted
annual rate, used for flows such as GDP). Many monthly BLS and BEA series exist
in both forms under different ids; `dismal fred series search ... --seasonal nsa`
finds the unadjusted twin.
