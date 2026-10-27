from __future__ import annotations

from pathlib import Path

import pytest

from dismal.bea.cache import FileCache
from dismal.bea.config import Settings


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
    key = "ABCDEFGH-1234-5678-9ABC-DEF012345678"
    s = Settings.from_env(
        {
            "BEA_API_KEY": f" {key} ",
            "BEA_API_BASE_URL": "https://example.test/api/data/",
            "BEA_TIMEOUT": "5",
            "BEA_MAX_RETRIES": "0",
            "BEA_CACHE_DIR": str(tmp_path),
            "BEA_FORMAT": "CSV",
            "NO_COLOR": "1",
        }
    )
    assert (
        s.api_key == key
        and s.masked_api_key().endswith("5678")
        and s.masked_api_key().startswith("*")
    )
    assert s.base_url == "https://example.test/api/data"
    assert s.timeout == 5.0 and s.max_retries == 0
    assert s.cache_dir == tmp_path and s.default_format == "csv" and s.no_color
    assert s.has_api_key and s.api_key_looks_valid
    empty = Settings.from_env({"HOME": "/tmp"})
    assert empty.api_key is None and empty.masked_api_key() == "(not set)"
    assert empty.cache_dir.name == "bea" and not empty.api_key_looks_valid
    assert Settings.from_env({"XDG_CACHE_HOME": "/x"}).cache_dir == Path("/x/dismal/bea")
    with pytest.raises(ValueError, match="BEA_TIMEOUT"):
        Settings.from_env({"BEA_TIMEOUT": "fast"})
    with pytest.raises(ValueError, match="BEA_MAX_RETRIES"):
        Settings.from_env({"BEA_MAX_RETRIES": "many"})
    assert Settings.from_env({"BEA_API_KEY": "ab"}).masked_api_key() == "**"
    assert "dismal/" in Settings.from_env({}).user_agent
