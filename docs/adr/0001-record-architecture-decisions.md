# 0001. Record architecture decisions

Date: 2026-10-24
Status: accepted

## Context

The `dismal` CLI is meant to be used for years by people and by automations
whose authors will not have the original design discussions available.
Decisions about output shape, exit codes and limits become contracts once
scripts depend on them. The tool serves three agencies' APIs behind one
command (`dismal bls`, `dismal bea`, `dismal fred`), so the records also need
to say where a decision is shared by every source and where one API forced a
different choice.

## Decision

Keep Architecture Decision Records in `docs/adr/`, one Markdown file per
decision, in the MADR short form (context, decision, consequences), indexed in
`docs/adr/README.md`. A decision is recorded when it affects the CLI contract,
the data shape, dependencies, security or the release process. Decisions that
apply to every source are recorded once; decisions that hold for one source
only carry the source name in their title (`BLS:`, `BEA:`, `FRED:`) and say
where they depart from the shared design.

## Consequences

- Changes to contracts must come with a new ADR (or a superseding one), which
  slows down casual breaking changes - intentionally.
- Newcomers and agents can read the "why" without digging through history, and
  people who know one source can see the differences of another at a glance.
