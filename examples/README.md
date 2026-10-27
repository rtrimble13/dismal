# Examples

One directory per source, plus one agent skill that covers all three. Every
script assumes the source's key is exported (`BLS_API_KEY`, `BEA_API_KEY`,
`FRED_API_KEY`) and that `dismal` is installed
(`uv tool install git+https://github.com/rtrimble13/dismal`).

## `bls/`

| Path | What it shows |
| --- | --- |
| [`bls/cli-recipes.sh`](bls/cli-recipes.sh) | Everyday `dismal bls` command lines: ranges, wide CSV, Parquet, discovery, jq |
| [`bls/python_api.py`](bls/python_api.py) | Using `dismal.bls.BLSClient` directly and converting to pandas |
| [`bls/series-ids.txt`](bls/series-ids.txt) | A `--series-file` input with comments |
| [`bls/github-actions/weekly-pull.yml`](bls/github-actions/weekly-pull.yml) | Scheduled workflow that pulls BLS data and commits CSV/Parquet |

## `bea/`

| Path | What it shows |
| --- | --- |
| [`bea/cli-recipes.sh`](bea/cli-recipes.sh) | Everyday `dismal bea` command lines: tables, frequencies, regional data, wide CSV, Parquet, discovery, jq |
| [`bea/python_api.py`](bea/python_api.py) | Using `dismal.bea.BEAClient` directly and converting to pandas |
| [`bea/github-actions/weekly-pull.yml`](bea/github-actions/weekly-pull.yml) | Scheduled workflow that pulls BEA data and commits CSV/Parquet |

## `fred/`

| Path | What it shows |
| --- | --- |
| [`fred/cli-recipes.sh`](fred/cli-recipes.sh) | Everyday `dismal fred` command lines: ranges, transformations, wide CSV, Parquet, vintages, discovery, jq |
| [`fred/python_api.py`](fred/python_api.py) | Using `dismal.fred.FREDClient` directly and converting to pandas |
| [`fred/series-ids.txt`](fred/series-ids.txt) | A `--series-file` input with comments |
| [`fred/github-actions/weekly-pull.yml`](fred/github-actions/weekly-pull.yml) | Scheduled workflow that pulls FRED data and commits CSV/Parquet |

## `skill/`

| Path | What it shows |
| --- | --- |
| [`skill/SKILL.md`](skill/SKILL.md) | One agent skill (`dismal-data`) that wraps `dismal bls`, `dismal bea` and `dismal fred`, with a section on choosing the source |

The contract these examples rely on is in [`docs/agents.md`](../docs/agents.md).
