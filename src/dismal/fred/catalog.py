"""Bundled, offline catalog: a curated set of popular FRED series.

It lives in ``fred/data/series_catalog.json`` and is maintained in the
repository. Each entry carries search ``tags`` (single words and established
terms) and optional ``aliases`` (everyday phrases matched as a whole); see
``docs/adr/0005-fuzzy-search.md`` and ``docs/adr/0012-catalog-aliases.md``.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from importlib import resources
from typing import Any


@dataclass(frozen=True)
class CatalogEntry:
    """One curated series."""

    series_id: str
    title: str
    frequency: str  # daily, weekly, monthly, quarterly, annual
    seasonal: str  # "SA" or "NSA"
    units: str = ""
    source: str = ""  # publishing agency, e.g. BLS, BEA, Board of Governors
    tags: tuple[str, ...] = field(default_factory=tuple)
    aliases: tuple[str, ...] = field(default_factory=tuple)  # whole-query everyday phrases

    @property
    def search_text(self) -> str:
        return " ".join(
            [self.series_id, self.title, self.source, self.seasonal, *self.tags, *self.aliases]
        )

    def to_record(self) -> dict[str, Any]:
        return {
            "series_id": self.series_id,
            "title": self.title,
            "frequency": self.frequency,
            "seasonal": self.seasonal,
            "units": self.units,
            "source": self.source,
            "tags": list(self.tags),
            "aliases": list(self.aliases),
        }


def _load_json(name: str) -> Any:
    with resources.files("dismal.fred.data").joinpath(name).open("r", encoding="utf-8") as fh:
        return json.load(fh)


def series_catalog() -> list[CatalogEntry]:
    raw = _load_json("series_catalog.json")
    entries = []
    for item in raw["series"]:
        entries.append(
            CatalogEntry(
                series_id=item["id"],
                title=item["title"],
                frequency=item.get("frequency", ""),
                seasonal=item.get("seasonal", ""),
                units=item.get("units", ""),
                source=item.get("source", ""),
                tags=tuple(item.get("tags", [])),
                aliases=tuple(item.get("aliases", [])),
            )
        )
    return entries


def catalog_note() -> str:
    return str(_load_json("series_catalog.json").get("note", ""))


def catalog_entry(series_id: str) -> CatalogEntry | None:
    wanted = series_id.strip().upper()
    for e in series_catalog():
        if e.series_id == wanted:
            return e
    return None
