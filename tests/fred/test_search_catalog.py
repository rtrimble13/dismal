from __future__ import annotations

import pytest

from dismal.fred.catalog import CatalogEntry, catalog_entry, catalog_note, series_catalog
from dismal.fred.search import phrase_key, score_text, search_rows, search_series


def test_bundled_catalog_is_well_formed() -> None:
    entries = series_catalog()
    assert len(entries) > 120
    ids = [e.series_id for e in entries]
    assert len(ids) == len(set(ids))
    for e in entries:
        assert e.series_id == e.series_id.upper() and e.title and e.units and e.source
        assert e.frequency in {"daily", "weekly", "biweekly", "monthly", "quarterly", "annual"}, (
            e.series_id
        )
        assert e.seasonal in {"SA", "NSA"}, e.series_id
        keys = [phrase_key(a) for a in e.aliases]
        assert all(len(k) > 1 for k in keys), f"{e.series_id}: single words belong in tags"
        assert len(keys) == len(set(keys)), f"{e.series_id}: duplicate aliases"
        assert e.tags
    assert "fred series search" in catalog_note()
    assert catalog_entry("unrate") is not None and catalog_entry("ZZZ") is None


def test_score_bands() -> None:
    assert score_text("core cpi", "anything", ["core cpi"]) == 100.0
    assert score_text("Unemployment Rate", "unemployment rate") == 100.0
    assert score_text("unemployment rate", "Unemployment Rate in Texas") == 95.0
    assert score_text("employ", "Employment level") == 75.0
    typo = score_text("unemploymnt rate", "Unemployment Rate")
    assert 80 < typo < 90
    assert score_text("zzzz", "Unemployment rate") == 0.0 and score_text("", "x") == 0.0
    assert score_text("unemployment in texas", "x", ["unemployment", "texas"]) == 100.0
    assert score_text("the", "The Times") == 95.0


def test_phrase_key_and_aliases() -> None:
    assert phrase_key("rate of mortgages") == phrase_key("Mortgage rates") == ("mortgage", "rate")
    assert phrase_key("price of groceries") == ("grocery", "price")
    assert phrase_key("the of") == ()
    aliases = ["mortgage rates"]
    assert (
        score_text("mortgage rates", "30-Year Fixed Rate Mortgage Average", aliases=aliases)
        == 100.0
    )
    assert (
        score_text("rate of mortgages", "30-Year Fixed Rate Mortgage Average", aliases=aliases)
        == 100.0
    )
    assert score_text("rates", "Something unrelated", aliases=aliases) < 55


def test_search_series_rankings() -> None:
    entries = series_catalog()
    assert search_series("unemployment rate", entries, limit=1)[0].id == "UNRATE"
    assert search_series("unemploymnt rate", entries, limit=1)[0].id == "UNRATE"
    assert search_series("dgs10", entries)[0].score == 100.0
    assert search_series("zzzz qqqq", entries) == []
    rec = search_series("core cpi", entries, limit=1)[0].to_record()
    assert rec["kind"] == "series" and rec["id"] == "CPILFESL" and "source" in rec


@pytest.mark.parametrize(
    ("query", "series_id"),
    [
        ("mortgage rates", "MORTGAGE30US"),
        ("jobs report", "PAYEMS"),
        ("nonfarm payrolls", "PAYEMS"),
        ("fed funds rate", "FEDFUNDS"),
        ("10 year treasury yield", "DGS10"),
        ("yield curve", "T10Y2Y"),
        ("core pce", "PCEPILFE"),
        ("inflation rate", "CPIAUCSL"),
        ("core inflation", "CPILFESL"),
        ("gas prices", "GASREGW"),
        ("oil prices", "DCOILWTICO"),
        ("money supply", "M2SL"),
        ("fed balance sheet", "WALCL"),
        ("housing starts", "HOUST"),
        ("house prices", "CSUSHPINSA"),
        ("initial jobless claims", "ICSA"),
        ("consumer sentiment", "UMCSENT"),
        ("retail sales", "RSAFS"),
        ("gdp growth", "A191RL1Q225SBEA"),
        ("real gdp", "GDPC1"),
        ("unemployment in texas", "TXUR"),
        ("recession indicator", "USREC"),
        ("national debt", "GFDEBTN"),
        ("trade deficit", "BOPGSTB"),
        ("dollar index", "DTWEXBGS"),
        ("vix", "VIXCLS"),
        ("stock market", "SP500"),
        ("saving rate", "PSAVERT"),
        ("industrial production", "INDPRO"),
        ("credit spreads", "BAMLH0A0HYM2"),
        ("sahm rule", "SAHMREALTIME"),
        ("real wages", "LES1252881600Q"),
    ],
)
def test_everyday_phrases(query: str, series_id: str) -> None:
    top = search_series(query, series_catalog(), limit=1)
    assert top and top[0].id == series_id and top[0].score >= 90, top[:1]


@pytest.mark.parametrize("query", ["bitcoin price", "gold price", "ethereum", "weather forecast"])
def test_everyday_phrases_do_not_invent_matches(query: str) -> None:
    assert search_series(query, series_catalog()) == []


def test_search_rows_generic() -> None:
    rows = [
        {"id": "53", "name": "Gross Domestic Product"},
        {"id": "50", "name": "Employment Situation"},
    ]
    hits = search_rows("employment", rows, text_of=lambda r: r["name"], id_of=lambda r: r["id"])
    assert [r["id"] for _, r in hits] == ["50"]
    assert (
        search_rows("53", rows, text_of=lambda r: r["name"], id_of=lambda r: r["id"])[0][0] == 100.0
    )


def test_catalog_entry_record() -> None:
    e = CatalogEntry("X", "t", "monthly", "SA", "u", "src", ("a",), ("b c",))
    rec = e.to_record()
    assert rec["tags"] == ["a"] and rec["aliases"] == ["b c"] and rec["source"] == "src"
    assert "b c" in e.search_text and "src" in e.search_text
