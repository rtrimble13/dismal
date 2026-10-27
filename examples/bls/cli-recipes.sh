#!/usr/bin/env bash
# Everyday `dismal bls` recipes. Requires BLS_API_KEY in the environment.
set -euo pipefail

# --- discovery (offline, no quota) -------------------------------------------
dismal bls search "core cpi" --limit 5
dismal bls search "unemploymnt rate" --limit 3 --format json | jq -r '.[].id'
dismal bls surveys --query "price"

# --- latest values -------------------------------------------------------------
dismal bls latest LNS14000000 CUUR0000SA0 CES0000000001 --format table
UNRATE=$(dismal bls latest LNS14000000 --format json | jq -r '.[0].value')
echo "Unemployment rate: ${UNRATE}%"

# --- ranges, filters and layouts ----------------------------------------------
# CPI-U headline and core, monthly, Jan 2019 - Jun 2024, one column per series
dismal bls data CUUR0000SA0 CUUR0000SA0L1E --start 2019-01 --end 2024-06 \
    --layout wide --format csv --output cpi_wide.csv

# Quarterly productivity with annual averages, 2015-2024
dismal bls data PRS85006092 --start 2015 --end 2024 \
    --frequency quarterly --frequency annual --annual-average --format csv

# 12-month percent changes for the last 3 years, selected columns only
dismal bls data CUUR0000SA0 --years 3 --calculations \
    --columns series_id,date,value,pct_change_12 --format jsonl

# --- files and bulk -----------------------------------------------------------
# Ids from a file, 2000-2024 (splits into several API requests automatically)
dismal bls data --series-file series-ids.txt --start 2000 --end 2024 \
    --format parquet --output bls_2000_2024.parquet --strict

# Ids from stdin
printf 'LNS14000000\nLNS11300000\n' | dismal bls data -S - --years 2 --format csv

# --- exhaustive discovery via flat files ---------------------------------------
export BLS_USER_AGENT="dismal-examples (you@example.com)"
dismal bls series list --survey AP --query "eggs" --limit 5
dismal bls series info APU0000708111

# --- raw API shape --------------------------------------------------------------
dismal bls data LNS14000000 --latest --raw | jq '.Results.series[0].data[0]'

# --- health -----------------------------------------------------------------------
dismal bls config
dismal bls doctor >/dev/null && echo "API reachable"
