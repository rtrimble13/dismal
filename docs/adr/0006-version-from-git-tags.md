# 0006. Version derived from `vX.Y.Z` git tags; workflow-driven releases

Date: 2026-10-24
Status: accepted

## Context

The project needs `vX.Y.Z` versions, reproducible builds and a low-friction
release process that does not depend on a maintainer's laptop. Storing the
version in source means every release is a commit that edits one line and can
drift from tags. `dismal` ships all three sources in one package, so there is
exactly one version to manage.

## Decision

- The single source of truth is the annotated git tag `vMAJOR.MINOR.PATCH` of
  the `dismal` repository. `hatch-vcs` computes the package version from it at
  build time (`guess-next-dev` between tags, `no-local-version`, fallback
  `0.0.0`). `dismal --version`, `dismal version` and every `dismal <source>
  version` report the same value, as does `dismal.__version__`.
- The **Bump version** workflow (`workflow_dispatch`, choice of
  patch/minor/major) computes the next tag (`scripts/next_version.py`), moves
  the *Unreleased* changelog section under the new version, commits, tags and
  then **calls** the Release workflow. It calls it explicitly because a tag
  pushed with `GITHUB_TOKEN` does not itself trigger `push` workflows.
- The **Release** workflow (also triggered by hand-pushed `v*.*.*` tags)
  builds, asserts the built version equals the tag, runs the tests against the
  installed wheel, and publishes a GitHub release; PyPI publishing is opt-in
  via the `PYPI_PUBLISH` repository variable using trusted publishing.

## Consequences

- No version bump commits in PRs; `CHANGELOG.md` *Unreleased* is the only
  thing contributors touch.
- Checkouts without tags (shallow clones) report `0.0.0`; CI uses
  `fetch-depth: 0`.
- Tags are immutable; mistakes are fixed by a new patch release.
- A release covers every source, even when only one of them changed.
