# Changelog

All notable changes to this project are documented here. The format follows
[Keep a Changelog](https://keepachangelog.com/en/1.1.0/) and versions follow
[Semantic Versioning](https://semver.org/) as `vMAJOR.MINOR.PATCH` git tags.

Releases are cut by the **Bump version** GitHub Actions workflow, which moves the
*Unreleased* section below under the new version heading.

## [Unreleased]
### Added

- `dismal`: one command-line client and Python package consolidating the
  former stand-alone `bls`, `bea` and `fred` tools
  ([ADR 0010](docs/adr/0010-one-cli-per-source-subcommands.md)). Each source
  is a subcommand that keeps every existing command, flag and output:
  `dismal bls ...`, `dismal bea ...`, `dismal fred ...`.
- Top-level maintenance commands aggregated across the sources:
  `dismal config`, `dismal doctor`, `dismal cache info|clear`,
  `dismal version`. The per-source variants (`dismal bls doctor`, ...) remain.
- `-v`/`-q` are accepted before or after the source (`dismal -q bls data ...`
  and `dismal bls -q data ...`).
- `dismal.core`: the code the sources share (file cache, output serialisers,
  settings base, `DismalError`/`ExitCode`, CLI plumbing), written once.
- Documentation: umbrella pages in `docs/`, the source-specific pages under
  `docs/bls/`, `docs/bea/`, `docs/fred/`, the ADRs of all three tools
  renumbered into one series, examples per source and one merged agent skill.

### Changed

- Console scripts: `bls`, `bea` and `fred` are replaced by `dismal <source>`.
- Python imports: `bls` -> `dismal.bls`, `bea` -> `dismal.bea`,
  `fred` -> `dismal.fred` (module paths move 1:1; class names are unchanged).
  `__version__` lives in `dismal`.
- Default cache directories: `~/.cache/dismal/<source>` instead of
  `~/.cache/<source>` (`<SOURCE>_CACHE_DIR` still overrides).
- Default User-Agent: `dismal/<version> (+https://github.com/rtrimble13/dismal)`.
- stderr diagnostics are prefixed with the source: `dismal bls: warning: ...`,
  `dismal fred: error: ...`.
- `version` prints `dismal X.Y.Z (python ...)` for every source; one version
  covers the whole package.
- `config` records carry a `source` field.
- BLS: `--series-file` reports an unreadable file as a usage error (exit 2),
  as `fred` already did.

### Carried over

The functionality of the last releases of the three tools is included
unchanged: `bls` 0.1.0 plus its unreleased search improvements (tag synonyms,
catalog aliases, small-word skipping), `bea` 0.1.0, and the initial `fred`
release (data with units, frequency aggregation and ALFRED vintages; series,
releases and categories discovery). See the former changelogs in those
repositories for their histories.
