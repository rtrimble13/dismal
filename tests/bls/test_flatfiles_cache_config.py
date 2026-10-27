from __future__ import annotations

from pathlib import Path

import pytest

from dismal.bls.cache import FileCache
from dismal.bls.config import Settings
from dismal.bls.errors import BLSHTTPError
from dismal.bls.flatfiles import fetch_series_file, parse_series_file, series_title_of
from tests.bls.conftest import FakeBLS

CU_SERIES = (
    "series_id\tarea_code\titem_code\tseasonal\tperiodicity_code\tbase_code\tbase_period\tseries_title\t"
    "footnote_codes\tbegin_year\tbegin_period\tend_year\tend_period\n"
    "CUUR0000SA0      \t0000\tSA0\tU\tR\tS\t1982-84=100\t"
    "All items in U.S. city average, all urban consumers, not seasonally adjusted"
    "\t\t1913\tM01\t2025\tM09\n"
    "CUUR0000SETB01   \t0000\tSETB01\tU\tR\tS\t1982-84=100\t"
    "Gasoline (all types) in U.S. city average\t\t1967\tM01\t2025\tM09\n"
)


def test_parse_series_file_strips_and_pads() -> None:
    rows = parse_series_file(CU_SERIES)
    assert rows[0]["series_id"] == "CUUR0000SA0"
    assert rows[1]["series_title"].startswith("Gasoline")
    assert rows[0]["end_period"] == "M09"
    assert series_title_of(rows[0]).startswith("All items")
    assert series_title_of({"series_id": "X", "area_code": "01", "item_name": "Eggs"}) == "Eggs"


def test_fetch_series_file_caches(tmp_path: Path, fake: FakeBLS) -> None:
    fake.flatfiles["cu.series"] = CU_SERIES
    settings = Settings(cache_dir=tmp_path, user_agent="t (t@example.com)")
    text = fetch_series_file("CU", settings, transport=fake.transport)
    assert text == CU_SERIES
    assert fake.requests[-1].headers["user-agent"] == "t (t@example.com)"
    assert (tmp_path / "flatfiles" / "cu.series").is_file()
    n = len(fake.requests)
    assert fetch_series_file("cu", settings, transport=fake.transport) == CU_SERIES
    assert len(fake.requests) == n  # served from cache
    fetch_series_file("cu", settings, transport=fake.transport, refresh=True)
    assert len(fake.requests) == n + 1


def test_fetch_series_file_errors(tmp_path: Path, fake: FakeBLS) -> None:
    settings = Settings(cache_dir=tmp_path)
    with pytest.raises(BLSHTTPError, match="no series directory"):
        fetch_series_file("zz", settings, transport=fake.transport)
    fake.flatfile_status = 403
    with pytest.raises(BLSHTTPError) as exc:
        fetch_series_file("cu", settings, transport=fake.transport)
    assert exc.value.hint and "BLS_USER_AGENT" in exc.value.hint


def test_file_cache(tmp_path: Path) -> None:
    cache = FileCache(tmp_path / "c")
    assert cache.read_json("x.json") is None
    cache.write_json("x.json", {"a": 1})
    assert cache.read_json("x.json") == {"a": 1}
    assert cache.is_fresh("x.json", 60) and not cache.is_fresh("x.json", -1)
    cache.write_text("bad.json", "{")
    assert cache.read_json("bad.json") is None
    assert cache.clear() == 2 and cache.clear() == 0


def test_settings_from_env(tmp_path: Path) -> None:
    s = Settings.from_env(
        {
            "BLS_API_KEY": " abcdefgh ",
            "BLS_API_BASE_URL": "https://example.test/v2/",
            "BLS_TIMEOUT": "5",
            "BLS_MAX_RETRIES": "0",
            "BLS_CACHE_DIR": str(tmp_path),
            "BLS_FORMAT": "CSV",
            "NO_COLOR": "1",
        }
    )
    assert s.api_key == "abcdefgh" and s.masked_api_key() == "****efgh"
    assert s.base_url == "https://example.test/v2"
    assert s.timeout == 5.0 and s.max_retries == 0
    assert s.cache_dir == tmp_path and s.default_format == "csv" and s.no_color
    assert s.has_api_key
    empty = Settings.from_env({"HOME": "/tmp"})
    assert empty.api_key is None and empty.masked_api_key() == "(not set)"
    assert empty.cache_dir.name == "bls"
    with pytest.raises(ValueError, match="BLS_TIMEOUT"):
        Settings.from_env({"BLS_TIMEOUT": "fast"})
    assert Settings.from_env({"BLS_API_KEY": "ab"}).masked_api_key() == "**"
