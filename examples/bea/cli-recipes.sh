#!/usr/bin/env bash
# Everyday `dismal bea` recipes. Requires BEA_API_KEY in the environment.
# Docs: ../../docs/bea/usage.md; agent contract: ../../docs/bea/agents.md.
set -euo pipefail

# --- discovery (offline, no requests) ------------------------------------------
dismal bea search "real gdp" --limit 5
dismal bea search "pce price index" --limit 3 --format json | jq -r '.[].command'
dismal bea datasets --query "industry"

# --- discovery (live metadata, cached for a week) -------------------------------
dismal bea datasets show Regional
dismal bea tables list NIPA --query "personal income"
dismal bea tables show NIPA T10101
dismal bea values Regional LineCode --filter TableName=SAINC1
dismal bea values Regional GeoFips --query texas

# --- latest values ---------------------------------------------------------------
dismal bea latest NIPA --table T10101 --frequency Q --format table
GDP_GROWTH=$(dismal bea latest NIPA -t T10101 -F Q --format json | jq -r '.[] | select(.series_id=="A191RL") | .value')
echo "Real GDP growth, latest quarter: ${GDP_GROWTH}% (annual rate)"

# --- ranges, filters and layouts --------------------------------------------------
# Real GDP growth and its components, quarterly, 2019 - Q2 2024, one column per line
dismal bea data NIPA --table T10101 --frequency Q --start 2019 --end 2024-Q2 \
    --layout wide --format csv --output gdp_growth_wide.csv

# Nominal and real GDP levels, annual, two tables merged into one output
dismal bea data NIPA -t T10105 -t T10106 -F A --years 10 --format csv

# Monthly PCE price indexes for the last 2 years, with the table notes attached
dismal bea data NIPA -t T20804 -F M --years 2 --notes --format jsonl

# Personal income by state, last 5 years
dismal bea data Regional -t SAINC1 --line 1 --geo STATE --years 5 --format csv

# Value added by industry, annual, selected industries
dismal bea data GDPbyIndustry -t 1 -F A --industry 11 --industry 21 --industry 31G --years 5

# Balance on goods and current account, quarterly seasonally adjusted
dismal bea data ITA Indicator=BalGds,BalCurrAcct AreaOrCountry=AllCountries -F QSA --years 3

# --- files and bulk ----------------------------------------------------------------
# Everything a table has, as Parquet
dismal bea data NIPA -t T20100 -F Q Year=ALL --format parquet --output personal_income.parquet --strict

# --- raw API shape -------------------------------------------------------------------
dismal bea data NIPA -t T10101 -F Q --latest --raw | jq '.BEAAPI.Results.Data[0]'

# --- health ------------------------------------------------------------------------------
dismal bea config
dismal bea doctor >/dev/null && echo "API reachable"
