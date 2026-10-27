#!/usr/bin/env bash
# Everyday `dismal fred` recipes. Requires FRED_API_KEY in the environment.
set -euo pipefail

# --- discovery (offline, no requests) ------------------------------------------
dismal fred search "mortgage rates" --limit 5
dismal fred search "yield curve" --limit 3 --format json | jq -r '.[].id'
dismal fred search "jobs report"

# --- discovery (live) ------------------------------------------------------------
dismal fred series search "median home price" --order-by popularity -n 10
dismal fred series search "unemployment rate" --frequency m --tag usa -n 10
dismal fred series info UNRATE CPIAUCSL DGS10 --notes
dismal fred releases dates --days 7
dismal fred releases series 53 -n 50
dismal fred categories

# --- latest values ---------------------------------------------------------------
dismal fred latest UNRATE PAYEMS FEDFUNDS DGS10 MORTGAGE30US --meta --format table
UNRATE=$(dismal fred latest UNRATE --format json | jq -r '.[0].value')
echo "Unemployment rate: ${UNRATE}%"

# --- ranges, transformations and layouts ------------------------------------------
# CPI and core CPI, 12-month percent change, last 5 years, one column per series
dismal fred data CPIAUCSL CPILFESL --units pc1 --years 5 --layout wide --format csv --output inflation.csv

# 10-year and 2-year yields, monthly averages since 2015, plus the spread
dismal fred data DGS10 DGS2 T10Y2Y --frequency m --start 2015 --layout wide --format csv --output yields.csv

# Real GDP growth at an annual rate (BEA's own series) and the level in chained dollars
dismal fred data A191RL1Q225SBEA GDPC1 --years 5 --format csv

# Monthly payroll changes in thousands, newest first
dismal fred data PAYEMS --units chg --years 2 --descending --columns date,value

# Fed balance sheet, weekly, end of period by quarter
dismal fred data WALCL --frequency q --aggregation eop --start 2019

# --- vintages (ALFRED) ---------------------------------------------------------------
# Payrolls as first published on 2 February 2024
dismal fred data PAYEMS --as-of 2024-02-02 --start 2023-06 --format csv
dismal fred series vintages PAYEMS --format csv | tail -5

# --- files and bulk ---------------------------------------------------------------------
dismal fred data --series-file series-ids.txt --start 2000 --format parquet --output fred_2000_on.parquet --strict
printf 'UNRATE\nCIVPART\n' | dismal fred data -S - --years 2 --format csv

# --- raw API shape --------------------------------------------------------------------------
dismal fred data UNRATE --latest --raw | jq '.series[0].observations[0]'

# --- health ------------------------------------------------------------------------------------
dismal fred config
dismal fred doctor >/dev/null && echo "API reachable"
