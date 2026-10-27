# 0009. Everyday-phrase aliases and small-word skipping in catalog search

Date: 2026-10-25
Status: accepted

## Context

`dismal bls search` and `dismal fred search` (ADR 0005) score each query word
against series titles and tags and average the credits. People and agents
phrase questions in everyday language ("grocery prices", "wage growth",
"manufacturing jobs", "unemployment in texas", "mortgage rates", "jobs
report", "fed balance sheet", "price of gas"), and a word that appears in no
title or tag, such as "prices", "growth", "rates", "report" or "in", scores 0
and halves the result. Many natural queries therefore returned nothing or
ranked the wrong series first.

Adding such phrases as ordinary tags fixes the phrase itself but leaks its
words: every word of a tag earns credit on its own. With a `grocery prices`
tag on "Food at home", the query `home prices` (house prices, which BLS does
not publish) matched it at 95, above the 90 that agents treat as a confident
match; with a `mortgage rates` tag, the lone word `rates` would match the
mortgage series at 95.

The problem was first met and solved in the BLS catalog; the FRED catalog
adopted the solution unchanged. The BEA catalog (`dismal bea search`) carries
tags only and has no aliases: its entries are tables and indicators whose
titles already carry the everyday vocabulary, and its scorer does not skip
small words.

## Decision

For the BLS and FRED catalogs:

1. **Single-word synonyms are tags** (`jobs` on payroll employment series,
   `grocery`, `pay`, `hiring`, `salary`). One word leaks nothing but itself.
2. **Multi-word everyday phrases are `aliases`**, an optional catalog field.
   An alias matches only the query as a whole and then scores 100. Both sides
   are normalised with `phrase_key`: case, punctuation, word order, simple
   plurals and the small words `a an the of in for us u s` are ignored, so
   `price of eggs` matches the alias `egg prices`. Alias words earn no
   per-word credit. Matching is exact after normalisation, not fuzzy: a fuzzy
   threshold let `bar prices` match `car prices` at 90.
3. **The same small words are skipped in per-word scoring** unless the query
   consists of nothing else, so `unemployment in texas` scores like
   `unemployment texas`.
4. An alias shared by several series is allowed where the phrase is genuinely
   ambiguous (`car prices` on new and used vehicles in BLS, `fed funds rate`
   on the monthly and daily series in FRED) or names a seasonally
   adjusted/unadjusted pair. Catalog order still breaks ties.
5. A tag that should decide a query (`money supply`, `house prices`,
   `recession indicator`) is given to one series only; related series carry
   narrower tags.

## Consequences

- Common phrasings resolve offline with scores agents can trust; queries for
  data the catalog does not hold (`home prices` and `jobless claims` in BLS,
  `bitcoin price` and `gold price` in FRED) still return nothing, and tests
  pin both.
- Score bands are unchanged in meaning: 100 is still an exact match (now also
  to a normalised alias). A few existing BLS queries score higher
  (`unemployment rate` 97.5 to 100); none of the queries in the docs changed
  its top result except `groceries`, which now ranks food at home above all
  food.
- Small words no longer give incidental credit, so ties they used to break are
  decided by catalog order; the catalogs are ordered accordingly (average and
  median duration of unemployment before the 27-weeks count; headline series
  before their daily, unadjusted or component variants).
- Contributors choose between a tag and an alias; `docs/development.md` and a
  catalog test per source (aliases must have at least two significant words,
  no duplicates per series) enforce the split.
