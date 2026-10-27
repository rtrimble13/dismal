# 0002. Python package with a Typer CLI over a library core

Date: 2026-10-24
Status: accepted

## Context

The tool must be easy to install for researchers (who mostly use Python),
callable from shell pipelines and agent skills, and produce Parquet. Options
considered: Python (Typer/Click/argparse), Go, Rust. Each source
(`dismal bls`, `dismal bea`, `dismal fred`) must offer identical global
options, output flags, panels and help conventions so that scripts and skills
written for one need only small changes for another.

## Decision

Implement `dismal` as a Python 3.10+ package (distribution and import name
`dismal`) with:

- a **library core** per source (`dismal.bls.client`, `dismal.bls.models`,
  `dismal.bls.records`, ... and likewise under `dismal.bea` and `dismal.fred`)
  that has no CLI concerns and is usable from notebooks and other programs,
  plus the shared plumbing in `dismal.core` (ADR 0010);
- a **Typer** CLI (`dismal.cli`, with one `dismal.<source>.cli` package per
  source) on top, one module per command group, each exposing
  `register(app)`; the same global options (`-v`, `-q`, `-V`), output options
  (`-f`, `-o`, `--columns`), panels and help conventions for every source;
- `httpx` for HTTP, `rapidfuzz` for fuzzy matching, `pyarrow` for Parquet,
  `rich` (via Typer) for tables;
- `src/` layout, `hatchling` build backend, `uv` for development.

Command names follow each agency's vocabulary: `dismal bls` has `surveys`,
`series list`, `series info` and `popular`; `dismal bea` has `datasets`,
`tables list`, `tables show` and `values`; `dismal fred` has `series`
(`info`, `search`, `vintages`, `updates`), `releases` and `categories`.
`data`, `latest`, `search`, `config`, `doctor`, `cache` and `version` are
identical across sources.

`pyarrow` is a hard dependency rather than an extra so that `--format parquet`
always works in automations without a second install step.

## Consequences

- Install is `uv tool install` / `pipx install`; startup is ~150 ms, acceptable
  for a network-bound tool.
- Typer vendors Click since 0.27; the code imports only `typer` and raises
  `typer.BadParameter` for usage errors so it works with both old and new
  Typer versions.
- Parquet support costs ~40 MB of wheel on install; judged worth it for
  reliability in pipelines.
- Someone who knows one source can use the others immediately; improvements
  to the shared modules land once for all of them.
