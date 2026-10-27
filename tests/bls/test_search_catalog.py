from __future__ import annotations

import pytest

from dismal.bls.catalog import CatalogEntry, bundled_surveys, series_catalog, survey_name
from dismal.bls.models import Survey
from dismal.bls.search import phrase_key, score_text, search_rows, search_series, search_surveys


def test_bundled_catalogs_are_well_formed() -> None:
    entries = series_catalog()
    assert len(entries) > 100
    ids = [e.series_id for e in entries]
    assert len(ids) == len(set(ids))
    assert all(e.survey == e.series_id[:2] for e in entries)
    for e in entries:
        keys = [phrase_key(a) for a in e.aliases]
        assert all(len(k) > 1 for k in keys), f"{e.series_id}: single words belong in tags"
        assert len(keys) == len(set(keys)), f"{e.series_id}: duplicate aliases"
    surveys = bundled_surveys()
    assert Survey("CU", "Consumer Price Index - All Urban Consumers (CPI-U)") in surveys
    assert survey_name("ln") is not None and survey_name("ZZ") is None


def test_score_bands() -> None:
    assert score_text("core cpi", "anything", ["core cpi"]) == 100.0
    assert score_text("Unemployment Rate", "unemployment rate") == 100.0
    assert score_text("core cpi", "All items less food and energy (core CPI)") == 95.0
    assert score_text("employ", "Employment level") == 75.0
    typo = score_text("unemploymnt rate", "Unemployment rate, 16 years and over")
    assert 80 < typo < 90
    assert score_text("zzzz", "Unemployment rate") == 0.0
    assert score_text("", "x") == 0.0
    # Small words neither help nor hurt, unless they are all there is.
    assert score_text("unemployment in texas", "x", ["unemployment", "texas"]) == 100.0
    assert score_text("the", "The Times") == 95.0


def test_search_series_rankings() -> None:
    entries = series_catalog()
    top = search_series("core cpi", entries, limit=2)
    assert {h.id for h in top} == {"CUSR0000SA0L1E", "CUUR0000SA0L1E"}
    assert search_series("unemploymnt rate", entries, limit=1)[0].id == "LNS14000000"
    assert search_series("nonfarm payrolls", entries, limit=1)[0].id == "CES0000000001"
    assert search_series("gas price", entries, limit=1)[0].id == "APU000074714"
    assert search_series("LNS14000000", entries)[0].score == 100.0
    assert all(
        h.survey == "LA" for h in search_series("unemployment", entries, survey="la", limit=0)
    )
    assert search_series("zzzz qqqq", entries) == []
    rec = top[0].to_record()
    assert rec["kind"] == "series" and "frequency" in rec and "score" in rec


def test_phrase_key_ignores_order_plurals_and_small_words() -> None:
    assert phrase_key("price of eggs") == phrase_key("Egg prices") == ("egg", "price")
    assert phrase_key("cost of groceries") == ("cost", "grocery")
    assert phrase_key("inflation in the Northeast") == phrase_key("northeast inflation")
    assert phrase_key("U.S. unemployment rate") == phrase_key("unemployment rates")
    assert phrase_key("the of") == ()


def test_aliases_match_the_whole_query_only() -> None:
    aliases = ["grocery prices"]
    assert score_text("grocery prices", "Food at home", aliases=aliases) == 100.0
    assert score_text("price of groceries", "Food at home", aliases=aliases) == 100.0
    # Unlike a tag, an alias lends no per-word credit: "prices" must not pair
    # with "home" from the title.
    assert score_text("home prices", "Food at home", aliases=aliases) < 55
    assert score_text("home prices", "Food at home", tags=aliases) > 90


@pytest.mark.parametrize(
    ("query", "series_id"),
    [
        ("grocery prices", "CUUR0000SAF11"),
        ("groceries", "CUUR0000SAF11"),
        ("wage growth", "CES0500000003"),
        ("salary", "CIU1020000000000A"),
        ("rent inflation", "CUUR0000SEHA"),
        ("housing costs", "CUUR0000SAH1"),
        ("manufacturing jobs", "CES3000000001"),
        ("california jobs", "SMS06000000000000001"),
        ("hiring", "JTS000000000000000HIL"),
        ("car prices", "CUUR0000SETA01"),
        ("used car prices", "CUUR0000SETA02"),
        ("pay", "CES0500000003"),
        ("new york inflation", "CUURS12ASA0"),
        ("inflation in chicago", "CUURS23ASA0"),
        ("price of eggs", "APU0000708111"),
        ("gas prices", "APU000074714"),
        ("food prices", "CUUR0000SAF1"),
        ("cost of living", "CUUR0000SA0"),
        ("cost of living adjustment", "CWUR0000SA0"),
        ("health care costs", "CUUR0000SAM"),
        ("job growth", "CES0000000001"),
        ("real unemployment rate", "LNS13327709"),
        ("hours worked", "CES0500000002"),
        ("worker productivity", "PRS85006092"),
        ("unemployment rate", "LNS14000000"),
        ("unemployment in texas", "LASST480000000000003"),
        ("jobs in california", "SMS06000000000000001"),
        ("price of a dozen eggs", "APU0000708111"),
        ("duration of unemployment", "LNS13008275"),
    ],
)
def test_everyday_phrases(query: str, series_id: str) -> None:
    top = search_series(query, series_catalog(), limit=1)
    assert top and top[0].id == series_id and top[0].score >= 90


@pytest.mark.parametrize(
    "query", ["home prices", "house prices", "jobless claims", "bar prices", "minimum wage"]
)
def test_everyday_phrases_do_not_invent_matches(query: str) -> None:
    assert search_series(query, series_catalog()) == []


def test_search_surveys() -> None:
    surveys = bundled_surveys()
    assert search_surveys("cu", surveys)[0].id == "CU"
    hits = search_surveys("producer price", surveys, limit=0)
    assert {h.id for h in hits} >= {"WP", "PC"}
    assert all(h.kind == "survey" for h in hits)


def test_search_rows_generic() -> None:
    rows = [
        {"series_id": "A1", "series_title": "Gasoline all types"},
        {"series_id": "B2", "series_title": "Bread"},
    ]
    hits = search_rows(
        "gasoline", rows, text_of=lambda r: r["series_title"], id_of=lambda r: r["series_id"]
    )
    assert [r["series_id"] for _, r in hits] == ["A1"]
    assert (
        search_rows(
            "b2", rows, text_of=lambda r: r["series_title"], id_of=lambda r: r["series_id"]
        )[0][0]
        == 100.0
    )


def test_catalog_entry_record() -> None:
    e = CatalogEntry("X", "t", "XX", "monthly", "SA", "u", ("a",), ("b c",))
    assert e.to_record()["tags"] == ["a"]
    assert e.to_record()["aliases"] == ["b c"]
    assert "XX" in e.search_text and "b c" in e.search_text
