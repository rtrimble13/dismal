from __future__ import annotations

from dismal.bea.catalog import (
    CatalogEntry,
    bundled_datasets,
    bundled_datasets_note,
    dataset_description,
    table_catalog,
)
from dismal.bea.datasets import DATASETS, dataset_info
from dismal.bea.models import Dataset
from dismal.bea.search import score_text, search_datasets, search_rows, search_tables


def test_bundled_catalogs_are_well_formed() -> None:
    entries = table_catalog()
    assert len(entries) > 60
    keys = [(e.dataset, e.id) for e in entries]
    assert len(keys) == len(set(keys))
    for e in entries:
        info = dataset_info(e.dataset)
        assert info.known, e.dataset
        names = dict(e.params)
        if info.table_param:
            assert names.get(info.table_param) == e.id, e.id
        for p in info.required:
            assert (
                p in names
                or p in {"Frequency", "Year"}
                or (p == "Industry" and "Industry" in info.defaults)
            ), (e.id, p)
        if e.frequency:
            assert all(
                f.strip() in (info.frequencies or (f.strip(),)) for f in e.frequency.split(",")
            ), e.id
        assert e.tags and e.title
    datasets = bundled_datasets()
    assert {d.name for d in datasets} == set(DATASETS)
    assert "bea datasets --refresh" in bundled_datasets_note()
    assert (
        dataset_description("nipa") == "Standard NIPA tables" and dataset_description("ZZ") is None
    )


def test_catalog_entry_command_and_record() -> None:
    e = CatalogEntry(
        "T10101", "NIPA", "GDP growth", (("TableName", "T10101"),), "Q,A", "percent", ("gdp",)
    )
    assert e.command == "dismal bea data NIPA TableName=T10101 -F Q"
    rec = e.to_record()
    assert (
        rec["params"] == "TableName=T10101" and rec["tags"] == ["gdp"] and "NIPA" in e.search_text
    )
    regional = CatalogEntry(
        "SAINC1",
        "Regional",
        "x",
        (("TableName", "SAINC1"), ("LineCode", "1"), ("GeoFips", "STATE")),
        "A",
    )
    assert (
        regional.command == "dismal bea data Regional TableName=SAINC1 LineCode=1 GeoFips=STATE"
    )  # no -F: Regional has none


def test_score_bands() -> None:
    assert score_text("real gdp", "anything", ["real gdp"]) == 100.0
    assert score_text("Personal Income", "personal income") == 100.0
    assert score_text("personal income", "Table 2.1. Personal Income and Its Disposition") == 95.0
    assert score_text("invest", "Private Fixed Investment by Type") == 75.0
    typo = score_text("persnal income", "Personal Income and Its Disposition")
    assert 80 < typo < 90
    assert score_text("zzzz", "Personal income") == 0.0
    assert score_text("", "x") == 0.0


def test_search_tables_rankings() -> None:
    entries = table_catalog()
    assert search_tables("real gdp", entries, limit=1)[0].id == "T10101"
    assert search_tables("gdp growth", entries, limit=1)[0].id == "T10101"
    assert search_tables("persnal income monthly", entries, limit=1)[0].id == "T20600"
    assert search_tables("pce price index monthly", entries, limit=1)[0].id == "T20804"
    assert search_tables("state personal income", entries, limit=1)[0].id == "SAINC1"
    assert search_tables("trade balance goods and services", entries, limit=1)[0].id == "BalGdsServ"
    assert search_tables("corporate profits", entries, limit=1)[0].id == "T11200"
    assert search_tables("t10105", entries)[0].score == 100.0
    assert all(
        h.dataset == "Regional" for h in search_tables("gdp", entries, dataset="regional", limit=0)
    )
    assert search_tables("zzzz qqqq", entries) == []
    rec = search_tables("real gdp", entries, limit=1)[0].to_record()
    assert (
        rec["kind"] == "table" and rec["command"].startswith("dismal bea data") and "score" in rec
    )


def test_search_datasets() -> None:
    datasets = bundled_datasets()
    assert search_datasets("nipa", datasets)[0].id == "NIPA"
    hits = search_datasets("international", datasets, limit=0)
    assert {h.id for h in hits} >= {"ITA", "IIP", "IntlServTrade"}
    assert all(h.kind == "dataset" for h in hits)
    assert (
        search_datasets("regional", [Dataset("Regional", "Regional data sets")])[0].score == 100.0
    )


def test_search_rows_generic() -> None:
    rows = [
        {"key": "06000", "description": "California"},
        {"key": "48000", "description": "Texas"},
    ]
    hits = search_rows(
        "california", rows, text_of=lambda r: r["description"], id_of=lambda r: r["key"]
    )
    assert [r["key"] for _, r in hits] == ["06000"]
    assert (
        search_rows("48000", rows, text_of=lambda r: r["description"], id_of=lambda r: r["key"])[0][
            0
        ]
        == 100.0
    )
    assert (
        len(
            search_rows(
                "a",
                rows,
                text_of=lambda r: r["description"],
                id_of=lambda r: r["key"],
                min_score=0,
                limit=0,
            )
        )
        == 2
    )
