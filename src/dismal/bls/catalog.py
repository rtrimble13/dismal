"""Bundled, offline catalogs: the survey list and a curated set of popular series.

Both live in ``bls/data`` as JSON. The survey snapshot is refreshed from the
live API with ``dismal bls surveys --refresh`` (cached under ``BLS_CACHE_DIR``); the
curated series catalog is maintained in the repository.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from importlib import resources
from typing import Any

from dismal.bls.cache import FileCache
from dismal.bls.models import Survey

SURVEYS_CACHE_NAME = "surveys.json"
SURVEYS_TTL_SECONDS = 7 * 24 * 3600


@dataclass(frozen=True)
class CatalogEntry:
    """One curated series."""

    series_id: str
    title: str
    survey: str
    frequency: str
    seasonal: str  # "SA" or "NSA"
    units: str = ""
    tags: tuple[str, ...] = field(default_factory=tuple)
    aliases: tuple[str, ...] = field(default_factory=tuple)  # whole-query everyday phrases

    @property
    def search_text(self) -> str:
        return " ".join(
            [self.series_id, self.title, self.survey, self.seasonal, *self.tags, *self.aliases]
        )

    def to_record(self) -> dict[str, Any]:
        return {
            "series_id": self.series_id,
            "title": self.title,
            "survey": self.survey,
            "frequency": self.frequency,
            "seasonal": self.seasonal,
            "units": self.units,
            "tags": list(self.tags),
            "aliases": list(self.aliases),
        }


def _load_json(name: str) -> Any:
    with resources.files("dismal.bls.data").joinpath(name).open("r", encoding="utf-8") as fh:
        return json.load(fh)


def bundled_surveys() -> list[Survey]:
    raw = _load_json("surveys.json")
    return [Survey(abbreviation=s["abbreviation"].upper(), name=s["name"]) for s in raw["surveys"]]


def bundled_surveys_note() -> str:
    return str(_load_json("surveys.json").get("note", ""))


def cached_surveys(cache: FileCache) -> list[Survey] | None:
    raw = cache.read_json(SURVEYS_CACHE_NAME)
    if not isinstance(raw, list):
        return None
    try:
        return [Survey(abbreviation=s["abbreviation"].upper(), name=s["name"]) for s in raw]
    except (KeyError, TypeError, AttributeError):
        return None


def store_surveys(cache: FileCache, surveys: list[Survey]) -> None:
    cache.write_json(
        SURVEYS_CACHE_NAME, [{"abbreviation": s.abbreviation, "name": s.name} for s in surveys]
    )


def series_catalog() -> list[CatalogEntry]:
    raw = _load_json("series_catalog.json")
    entries = []
    for item in raw["series"]:
        entries.append(
            CatalogEntry(
                series_id=item["id"],
                title=item["title"],
                survey=item["survey"].upper(),
                frequency=item.get("frequency", ""),
                seasonal=item.get("seasonal", ""),
                units=item.get("units", ""),
                tags=tuple(item.get("tags", [])),
                aliases=tuple(item.get("aliases", [])),
            )
        )
    return entries


def survey_name(abbreviation: str, surveys: list[Survey] | None = None) -> str | None:
    abbr = abbreviation.upper()
    for s in surveys or bundled_surveys():
        if s.abbreviation == abbr:
            return s.name
    return None
