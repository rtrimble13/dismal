# 0005. Offline fuzzy search over a curated catalog with RapidFuzz

Date: 2026-10-24
Status: accepted

## Context

BLS and BEA cannot search for series at all; users must know ids like
`CUUR0000SA0` or that real GDP growth is NIPA table `T10101`. FRED has a good
full-text search endpoint, but it costs a request, returns hundreds of series
for plain queries and ranks by its own relevance. Agents in particular need to
turn "core inflation" or "mortgage rates" into an id instantly and
deterministically, without spending request quota.

## Decision

Each source has the same layers:

1. **`dismal <source> search`** - offline, zero-quota fuzzy search over a
   *curated* JSON catalog of headline series or tables (id, title, frequency,
   units, tags, ...). Scoring is per query token: exact tag = 1.0, whole word =
   0.95, substring = 0.75, fuzzy (RapidFuzz ratio >= 72) = 0.8 x ratio,
   averaged and scaled to 0-100; exact id/tag/title = 100. Ties keep catalog
   order so national headline series rank first. Multi-word everyday phrases
   are matched through aliases (ADR 0009).
2. An **exhaustive** layer over the agency's complete inventory.
3. A **live** layer that describes one series or table through the API.

The per-source specifics: `dismal bls search` covers ~130 series plus the
survey list, the exhaustive layer is `dismal bls series list --survey XX
--query ...` over the flat-file directories (ADR 0013), and `dismal bls
popular` / `dismal bls series info` are live. `dismal bea search` covers ~75
tables and indicators and each hit carries a ready-to-run `command`; the
exhaustive layer is `dismal bea tables list` / `dismal bea values --query ...`
over the API's metadata (ADR 0016), and `dismal bea tables show` is live.
`dismal fred search` covers ~150 series, requires a ratio of at least 85 for
tokens shorter than five letters (so `gold` is not a typo of `sold`), and the
exhaustive layer is the API's own `dismal fred series search` plus
`releases`/`categories` browsing (ADR 0020).

RapidFuzz was chosen over `difflib` for speed and better partial matching, and
over embedding/vector approaches for zero infrastructure.

## Consequences

- The curated catalogs must be maintained by hand; wrong ids are the main
  risk, so contributors verify with `dismal bls series info`, `dismal bea
  tables show` or `dismal fred series info`.
- Search results are deterministic and explainable (score bands), which suits
  agents.
- Not every series or table is discoverable offline; the docs make the layers
  explicit so users know when to switch.
