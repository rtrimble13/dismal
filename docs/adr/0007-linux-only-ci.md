# 0007. Linux-only GitHub Actions

Date: 2026-10-24
Status: accepted

## Context

The requester needs CI and release automation only for Linux. Cross-platform
matrices triple the runner minutes and add flakiness unrelated to the tool,
which contains no platform-specific code.

## Decision

All workflows run on `ubuntu-latest`. CI tests Python 3.10-3.13 and exercises
every source (`dismal bls`, `dismal bea`, `dismal fred`) in one job; the
Release and Bump version workflows use a single Linux job. The package itself
remains OS-independent (pure Python, `pathlib`, no shell-outs).

## Consequences

- Windows/macOS regressions would be found by users, not CI. The risk is low;
  if it materialises, add OS entries to the matrix without changing anything
  else.
- Faster, cheaper CI.
