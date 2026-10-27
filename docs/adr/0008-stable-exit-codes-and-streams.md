# 0008. Stable exit codes; data on stdout, diagnostics on stderr

Date: 2026-10-24
Status: accepted

## Context

The `dismal` CLI is called from scripts and agent skills that must decide
whether to retry, stop, or fix their command, often without a human reading
the output. The same decision must hold for every source so an automation
learns one contract.

## Decision

- Exit codes are an enumerated contract (`dismal.core.errors.ExitCode`),
  identical for every source: 0 ok, 1 unexpected, 2 usage, 3 API/HTTP
  failure, 4 quota or rate limit, 5 network, 6 no data under `--strict`, 7
  configuration. Every error derives from `dismal.core.errors.DismalError`
  through a per-source subclass (`BLSError`, `BEAError`, `FREDError`) that
  carries its code; the CLI maps exceptions in one place (the `handle_errors`
  decorator that `error_handler` in `dismal.core.cli` builds per source).
- stdout carries only the requested data (or nothing on error). All warnings,
  API messages, progress notes and error text go to stderr, prefixed with the
  source: `dismal bls: warning:` / `dismal bls: error:` / `dismal bls: hint:`
  (and `dismal bea:`, `dismal fred:`). `--quiet` silences warnings, never
  errors.
- When stdout is not a terminal the default format is JSON, so a forgotten
  `--format` still yields machine-readable output.

For `dismal bls` code 4 means the daily request quota; for `dismal bea` and
`dismal fred` it means the per-minute rate limit, and code 7 also covers a key
the API rejects (ADR 0003).

## Consequences

- Adding an exit code is a minor change; changing the meaning of an existing
  one is major.
- Table output is never the default in pipelines, avoiding accidental parsing
  of box-drawing characters.
- The aggregated top-level commands (`dismal doctor`, `dismal config`,
  `dismal cache`) use the same codes and prefixes, so a script need not know
  which source produced a line.
