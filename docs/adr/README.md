# Architecture Decision Records

Decisions that shape `dismal` and would be costly to reverse. One file per
decision, numbered in order of acceptance, following the
[MADR](https://adr.github.io/madr/) short form: context, decision, consequences.

`dismal` consolidates the former `bls`, `bea` and `fred` CLIs (ADR 0010).
Decisions shared by every source are recorded once; decisions that hold for
one source only are marked with that source and prefixed in their title.

| # | Scope | Title | Status |
| --- | --- | --- | --- |
| [0001](0001-record-architecture-decisions.md) | Shared | Record architecture decisions | accepted |
| [0002](0002-python-typer-cli.md) | Shared | Python package with a Typer CLI over a library core | accepted |
| [0003](0003-api-key-from-environment.md) | Shared | API key only from the environment | accepted |
| [0004](0004-tidy-records-and-output-formats.md) | Shared | Tidy records as the canonical shape; JSON, JSONL, CSV, Parquet, table | accepted |
| [0005](0005-fuzzy-search.md) | Shared | Offline fuzzy search over a curated catalog with RapidFuzz | accepted |
| [0006](0006-version-from-git-tags.md) | Shared | Version derived from `vX.Y.Z` git tags; workflow-driven releases | accepted |
| [0007](0007-linux-only-ci.md) | Shared | Linux-only GitHub Actions | accepted |
| [0008](0008-stable-exit-codes-and-streams.md) | Shared | Stable exit codes; data on stdout, diagnostics on stderr | accepted |
| [0009](0009-catalog-aliases.md) | Shared | Everyday-phrase aliases and small-word skipping in catalog search | accepted |
| [0010](0010-one-cli-per-source-subcommands.md) | Shared | One CLI, one subcommand per source | accepted |
| [0011](0011-bls-client-side-filtering.md) | BLS | Fetch whole years, filter dates and frequencies client-side | accepted |
| [0012](0012-bls-chunking-and-retries.md) | BLS | Transparent chunking and retries in the client | accepted |
| [0013](0013-bls-flat-file-discovery.md) | BLS | Exhaustive series discovery via BLS flat files | accepted |
| [0014](0014-bea-client-side-filtering.md) | BEA | Request whole years, filter sub-annual bounds and `--latest` client-side | accepted |
| [0015](0015-bea-per-table-requests-and-retries.md) | BEA | One request per table, retries, rate-limit mapping | accepted |
| [0016](0016-bea-metadata-discovery.md) | BEA | Discovery through the API's metadata methods, cached | accepted |
| [0017](0017-bea-generic-datasets-with-static-hints.md) | BEA | Generic `GetData` pass-through plus static per-dataset hints | accepted |
| [0018](0018-fred-server-side-windows-transformations-vintages.md) | FRED | Date windows, transformations, aggregation and vintages are the API's job | accepted |
| [0019](0019-fred-per-series-requests-pagination-retries.md) | FRED | One request per series, pagination, retries, rate-limit mapping | accepted |
| [0020](0020-fred-discovery-through-the-api.md) | FRED | Discovery through search, releases and categories, with cached metadata | accepted |

To add one: copy the template below to `NNNN-short-title.md`, add a row here.
Prefix the title with `BLS:`, `BEA:` or `FRED:` when the decision concerns one
source only.

```markdown
# NNNN. Title

Date: YYYY-MM-DD
Status: proposed | accepted | superseded by NNNN

## Context
## Decision
## Consequences
```
