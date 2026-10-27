"""Bundled, offline catalogs: the dataset list and a curated set of popular tables.

Both live in ``bea/data`` as JSON. The dataset snapshot is refreshed from the
live API with ``dismal bea datasets --refresh`` (cached under ``BEA_CACHE_DIR``); the
curated table catalog is maintained in the repository.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from importlib import resources
from typing import Any

from dismal.bea.cache import FileCache
from dismal.bea.datasets import dataset_info
from dismal.bea.models import Dataset

DATASETS_CACHE_NAME = "datasets.json"
DATASETS_TTL_SECONDS = 7 * 24 * 3600


@dataclass(frozen=True)
class CatalogEntry:
    """One curated table (or indicator) with the parameters that fetch it."""

    id: str
    dataset: str
    title: str
    params: tuple[tuple[str, str], ...] = ()
    frequency: str = ""  # available Frequency codes, preferred first, e.g. "Q,A"
    units: str = ""
    tags: tuple[str, ...] = field(default_factory=tuple)

    @property
    def search_text(self) -> str:
        return " ".join([self.id, self.title, self.dataset, *self.tags])

    @property
    def command(self) -> str:
        """A ready-to-run ``dismal bea data`` invocation for this entry."""
        parts = ["dismal", "bea", "data", self.dataset]
        parts += [f"{k}={v}" for k, v in self.params]
        if self.frequency and dataset_info(self.dataset).has_frequency:
            parts += ["-F", self.frequency.split(",")[0].strip()]
        return " ".join(parts)

    def to_record(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "dataset": self.dataset,
            "title": self.title,
            "frequency": self.frequency,
            "units": self.units,
            "params": " ".join(f"{k}={v}" for k, v in self.params),
            "command": self.command,
            "tags": list(self.tags),
        }


def _load_json(name: str) -> Any:
    with resources.files("dismal.bea.data").joinpath(name).open("r", encoding="utf-8") as fh:
        return json.load(fh)


def bundled_datasets() -> list[Dataset]:
    raw = _load_json("datasets.json")
    return [Dataset(name=d["name"], description=d["description"]) for d in raw["datasets"]]


def bundled_datasets_note() -> str:
    return str(_load_json("datasets.json").get("note", ""))


def cached_datasets(cache: FileCache) -> list[Dataset] | None:
    raw = cache.read_json(DATASETS_CACHE_NAME)
    if not isinstance(raw, list):
        return None
    try:
        return [Dataset(name=d["name"], description=d["description"]) for d in raw]
    except (KeyError, TypeError):
        return None


def store_datasets(cache: FileCache, datasets: list[Dataset]) -> None:
    cache.write_json(
        DATASETS_CACHE_NAME, [{"name": d.name, "description": d.description} for d in datasets]
    )


def table_catalog() -> list[CatalogEntry]:
    raw = _load_json("catalog.json")
    entries = []
    for item in raw["tables"]:
        entries.append(
            CatalogEntry(
                id=item["id"],
                dataset=item["dataset"],
                title=item["title"],
                params=tuple((str(k), str(v)) for k, v in item.get("params", {}).items()),
                frequency=item.get("frequency", ""),
                units=item.get("units", ""),
                tags=tuple(item.get("tags", [])),
            )
        )
    return entries


def dataset_description(name: str, datasets: list[Dataset] | None = None) -> str | None:
    wanted = name.lower()
    for d in datasets or bundled_datasets():
        if d.name.lower() == wanted:
            return d.description
    return None
