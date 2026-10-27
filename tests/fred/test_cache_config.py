from __future__ import annotations

from pathlib import Path

import pytest

from dismal.fred.cache import FileCache
from dismal.fred.config import Settings


def test_file_cache(tmp_path: Path) -> None:
    cache = FileCache(tmp_path / "c")
    assert cache.read_json("x.json") is None
    cache.write_json("x.json", {"a": 1})
    assert cache.read_json("x.json") == {"a": 1}
    assert cache.is_fresh("x.json", 60) and not cache.is_fresh("x.json", -1)
    assert not cache.is_fresh("missing.json", 60)
    cache.write_text("bad.json", "{")
    assert cache.read_json("bad.json") is None
    assert cache.clear() == 2 and cache.clear() == 0


def test_settings_from_env(tmp_path: Path) -> None:
    key = "0123456789abcdef0123456789abcdef"
    s = Settings.from_env(
        {
            "FRED_API_KEY": f" {key} ",
            "FRED_API_BASE_URL": "https://example.test/fred/",
            "FRED_TIMEOUT": "5",
            "FRED_MAX_RETRIES": "0",
            "FRED_CACHE_DIR": str(tmp_path),
            "FRED_FORMAT": "CSV",
            "NO_COLOR": "1",
        }
    )
    assert (
        s.api_key == key
        and s.masked_api_key().endswith("cdef")
        and s.masked_api_key().startswith("*")
    )
    assert s.base_url == "https://example.test/fred" and s.timeout == 5.0 and s.max_retries == 0
    assert s.cache_dir == tmp_path and s.default_format == "csv" and s.no_color
    assert s.has_api_key and s.api_key_looks_valid
    empty = Settings.from_env({"HOME": "/tmp"})
    assert (
        empty.api_key is None
        and empty.masked_api_key() == "(not set)"
        and not empty.api_key_looks_valid
    )
    assert empty.cache_dir.name == "fred"
    assert Settings.from_env({"XDG_CACHE_HOME": "/x"}).cache_dir == Path("/x/dismal/fred")
    assert not Settings.from_env({"FRED_API_KEY": key.upper()}).api_key_looks_valid
    with pytest.raises(ValueError, match="FRED_TIMEOUT"):
        Settings.from_env({"FRED_TIMEOUT": "fast"})
    with pytest.raises(ValueError, match="FRED_MAX_RETRIES"):
        Settings.from_env({"FRED_MAX_RETRIES": "many"})
    assert Settings.from_env({"FRED_API_KEY": "ab"}).masked_api_key() == "**"
    assert "dismal/" in Settings.from_env({}).user_agent
