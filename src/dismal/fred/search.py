"""Fuzzy search over the curated series catalog using RapidFuzz.

Scores are 0-100. An exact (case-insensitive) match on a series id scores 100;
otherwise the best of a few RapidFuzz scorers is used so that both typos
(``unemploymnt``) and word-order differences (``rate unemployment``) are
tolerated. Curated series may also carry *aliases*, everyday phrases
(``mortgage rates``) that match only the query as a whole. See
``docs/adr/0005-fuzzy-search.md`` and ``docs/adr/0012-catalog-aliases.md``.
"""

from __future__ import annotations

from collections.abc import Callable, Iterable, Sequence
from dataclasses import dataclass, field
from typing import Any

from rapidfuzz import fuzz, utils

from dismal.fred.catalog import CatalogEntry


@dataclass(frozen=True)
class SearchHit:
    kind: str  # "series"
    id: str
    title: str
    score: float
    extra: dict[str, Any] = field(default_factory=dict)

    def to_record(self) -> dict[str, Any]:
        rec: dict[str, Any] = {
            "kind": self.kind,
            "id": self.id,
            "title": self.title,
            "score": round(self.score, 1),
        }
        rec.update(self.extra)
        return rec


_FUZZY_FLOOR = 72.0  # minimum RapidFuzz ratio for a token to earn fuzzy credit
_SHORT_WORD = 5  # shorter tokens need a closer match: "gold" is not a typo of "sold"
_SHORT_WORD_FLOOR = 85.0
_STOP_WORDS = frozenset({"a", "an", "the", "of", "in", "for", "us", "u", "s", "on"})


def _singular(word: str) -> str:
    if len(word) > 4 and word.endswith("ies"):
        return word[:-3] + "y"
    if len(word) > 3 and word.endswith("s") and not word.endswith("ss"):
        return word[:-1]
    return word


def phrase_key(text: str) -> tuple[str, ...]:
    """Normalise a phrase for alias matching.

    Case, punctuation, word order, simple plurals and a few small words are
    ignored, so ``rate of mortgages``, ``mortgage rates`` and ``Mortgage rate``
    share a key.
    """
    words = utils.default_process(text).split()
    return tuple(sorted(_singular(w) for w in words if w not in _STOP_WORDS))


def score_text(
    query: str, text: str, tags: Sequence[str] = (), aliases: Sequence[str] = ()
) -> float:
    """Return a 0-100 relevance score of ``text`` (plus ``tags`` and ``aliases``) for ``query``.

    The whole query scores 100 when it equals the text or a tag, or when its
    :func:`phrase_key` equals an alias's. Otherwise each query token earns a
    credit, and the score is the mean credit. Small words ("of", "in", "the",
    "us", ...) are skipped unless the query has nothing else:

    * 1.00 - the token equals a tag
    * 0.95 - the token is a whole word of the text or of a tag
    * 0.75 - the token is a substring of a word (``employ`` in ``employment``)
    * 0.8 x ratio - the closest word is a fuzzy match (typos), ratio >= 0.72
      (>= 0.85 for tokens shorter than five letters)
    * 0.00 - no match

    Alias words earn no per-token credit, so an alias such as ``mortgage rates``
    cannot make ``rates`` alone match a mortgage series. Exact tag hits outrank
    incidental word hits, and ties are left to the caller (which keeps the
    curated catalog order).
    """
    q = utils.default_process(query)
    t = utils.default_process(text)
    if not q or not t:
        return 0.0
    norm_tags = [utils.default_process(tag) for tag in tags]
    if q == t or q in norm_tags:
        return 100.0
    if aliases:
        key = phrase_key(query)
        if key and any(key == phrase_key(alias) for alias in aliases):
            return 100.0
    words = set(t.split())
    tag_words = {w for tag in norm_tags for w in tag.split()}
    credits: list[float] = []
    for tok in [w for w in q.split() if w not in _STOP_WORDS] or q.split():
        if tok in norm_tags:
            credits.append(1.0)
        elif tok in words or tok in tag_words:
            credits.append(0.95)
        elif any(tok in w for w in words | tag_words):
            credits.append(0.75)
        else:
            best = max((fuzz.ratio(tok, w) for w in words | tag_words), default=0.0)
            floor = _FUZZY_FLOOR if len(tok) >= _SHORT_WORD else _SHORT_WORD_FLOOR
            credits.append(0.8 * best / 100.0 if best >= floor else 0.0)
    if not credits:
        return 0.0
    return round(100.0 * sum(credits) / len(credits), 1)


def search_series(
    query: str,
    entries: Iterable[CatalogEntry],
    *,
    limit: int = 20,
    min_score: float = 55.0,
) -> list[SearchHit]:
    hits: list[SearchHit] = []
    q_upper = query.strip().upper()
    for entry in entries:  # catalog order breaks ties: headline series come first
        exact = entry.series_id == q_upper
        score = 100.0 if exact else score_text(query, entry.title, entry.tags, entry.aliases)
        if score >= min_score:
            hits.append(
                SearchHit(
                    kind="series",
                    id=entry.series_id,
                    title=entry.title,
                    score=score,
                    extra={
                        "frequency": entry.frequency,
                        "seasonal": entry.seasonal,
                        "units": entry.units,
                        "source": entry.source,
                    },
                )
            )
    return _top(hits, limit)


def search_rows(
    query: str,
    rows: Iterable[dict[str, Any]],
    *,
    text_of: Callable[[dict[str, Any]], str],
    id_of: Callable[[dict[str, Any]], str],
    limit: int = 20,
    min_score: float = 55.0,
) -> list[tuple[float, dict[str, Any]]]:
    """Generic fuzzy search over arbitrary dict rows (used for releases and categories)."""
    scored: list[tuple[float, dict[str, Any]]] = []
    q_upper = query.strip().upper()
    for row in rows:
        score = 100.0 if id_of(row).upper() == q_upper else score_text(query, text_of(row))
        if score >= min_score:
            scored.append((score, row))
    scored.sort(key=lambda t: -t[0])  # sort() is stable: input order breaks ties
    return scored[:limit] if limit else scored


def _top(hits: Sequence[SearchHit], limit: int) -> list[SearchHit]:
    ordered = sorted(enumerate(hits), key=lambda ih: (-ih[1].score, ih[0]))  # stable on input order
    chosen = [h for _, h in ordered]
    return chosen[:limit] if limit else chosen
