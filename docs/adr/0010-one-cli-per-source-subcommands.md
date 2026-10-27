# 0010. One CLI, one subcommand per source

Date: 2026-10-27
Status: accepted

## Context

`bls`, `bea` and `fred` were three repositories with identical skeletons: the
same `pyproject.toml`, Makefile, CI and release workflows, documentation
layout and ADR set. Their cache, output, configuration, error and CLI
plumbing modules were identical modulo the package name; only `client`,
`models`, `periods`, `records`, `search` and `catalog` were genuinely
API-specific. Every improvement to a shared module had to be ported twice,
every release cut three times, and agents had to install and learn three
tools that differed only in name. The two younger projects already recorded
that they inherited most of their decisions from `bls` (ADR 0001).

## Decision

- One repository and one distribution, `dismal`, with one console script,
  `dismal`. The old `bls`, `bea` and `fred` console scripts are not installed.
- Each source is a subcommand that keeps every existing command, argument and
  flag unchanged: `bls data LNS14000000` becomes `dismal bls data
  LNS14000000`, `bea tables list NIPA` becomes `dismal bea tables list NIPA`,
  `fred series search "mortgage"` becomes `dismal fred series search
  "mortgage"`.
- The global `-v/--verbose` and `-q/--quiet` options are accepted both before
  and after the source (`dismal -v bls data ...`, `dismal bls -v data ...`);
  `--version`/`-V` lives at the root.
- The maintenance commands (`config`, `doctor`, `cache info|clear`, `version`)
  exist per source (`dismal bls doctor`) and aggregated at the top level
  (`dismal doctor` runs all three).
- Shared code lives in `dismal.core`: cache, output serialisers, the settings
  base, the error base (`DismalError`, `ExitCode`) and the CLI plumbing
  (`handle_errors`, global options, output options). The per-source packages
  `dismal.bls`, `dismal.bea` and `dismal.fred` keep their `client`, `models`,
  `periods`, `records`, `search`, `catalog` and command modules.
- Environment variables are unchanged (`BLS_*`, `BEA_*`, `FRED_*`; `NO_COLOR`
  shared). The default cache directory is `$XDG_CACHE_HOME/dismal/<source>`
  (`~/.cache/dismal/bls`, ...); the default User-Agent is
  `dismal/<version> (+https://github.com/rtrimble13/dismal)`.
- One version for the whole package, derived from the `dismal` repository's
  git tags (ADR 0006).
- Python imports move one-to-one to `dismal.<source>`: `bls.client` becomes
  `dismal.bls.client`, `from fred import FREDClient` becomes `from dismal.fred
  import FREDClient`; exception class names are unchanged.
- The three old repositories are archived and deleted after the port; their
  ADRs are consolidated here (shared decisions once, source-specific ones
  prefixed with the source).

## Alternatives considered

- **A shared library package depended on by three CLIs.** Rejected: it
  removes the duplicated modules but still leaves three repositories, three
  CI pipelines and three releases to coordinate, plus a fourth for the
  library.
- **A hook-first layout, `dismal data <source> ...`.** Rejected: the `data`
  and `search` options differ per source (BLS surveys and `--catalog`, BEA
  datasets and `NAME=VALUE` parameters, FRED units, aggregation and
  vintages), so each hook would still need per-source subcommands and the
  help would mix three vocabularies.

## Consequences

- One CI pipeline, one release, one changelog; a fix to shared code lands once
  for every source. Agents install one tool and learn one set of conventions.
- Breaking rename: every command gains the `dismal ` prefix and every import
  the `dismal.` prefix. Scripts, skills and notebooks written for the old
  tools must be updated; there is no compatibility shim.
- A bug in `dismal.core` affects all sources at once, and a version bump
  covers all sources even when only one changed.
- The per-source packages must keep their API-specific modules independent of
  each other; cross-source behaviour belongs in `dismal.core` or in the
  top-level aggregated commands only.
