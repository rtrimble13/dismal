"""Tests for the ``dismal`` root command: dispatch to sources and aggregated maintenance."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import httpx
import pytest
from typer.testing import CliRunner

from dismal import SOURCES, __version__
from dismal.cli import app
from dismal.core.cli import State
from tests.bea.conftest import VALID_KEY as BEA_KEY
from tests.bea.conftest import FakeBEA
from tests.bls.conftest import FakeBLS
from tests.fred.conftest import VALID_KEY as FRED_KEY
from tests.fred.conftest import FakeFRED

runner = CliRunner()


class FakeAll:
    """Route requests to the fake of the host they target (BLS, BEA or FRED)."""

    def __init__(self) -> None:
        self.bls = FakeBLS()
        self.bea = FakeBEA()
        self.fred = FakeFRED()

    def handler(self, request: httpx.Request) -> httpx.Response:
        host = request.url.host
        if host.endswith("bls.gov"):
            return self.bls.handler(request)
        if host.endswith("bea.gov"):
            return self.bea.handler(request)
        return self.fred.handler(request)

    @property
    def transport(self) -> httpx.MockTransport:
        return httpx.MockTransport(self.handler)


@pytest.fixture
def fakes() -> FakeAll:
    return FakeAll()


@pytest.fixture
def cache_dirs(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> dict[str, Path]:
    dirs = {}
    for source in SOURCES:
        d = tmp_path / source
        monkeypatch.setenv(f"{source.upper()}_CACHE_DIR", str(d))
        dirs[source] = d
    return dirs


@pytest.fixture
def keyed(monkeypatch: pytest.MonkeyPatch) -> dict[str, str]:
    env = {"BLS_API_KEY": "secret-key-1234", "BEA_API_KEY": BEA_KEY, "FRED_API_KEY": FRED_KEY}
    for k, v in env.items():
        monkeypatch.setenv(k, v)
    return env


def run(fakes: FakeAll, *args: str, env: dict[str, str] | None = None) -> Any:
    state = State(transport=fakes.transport)
    return runner.invoke(app, list(args), obj=state, env=env, catch_exceptions=False)


def test_help_and_version(fakes: FakeAll) -> None:
    res = run(fakes, "--help")
    assert res.exit_code == 0
    for source in SOURCES:
        assert source in res.stdout
    assert run(fakes, "--version").stdout == f"dismal {__version__}\n"
    assert run(fakes, "version", "--short").stdout.strip() == __version__
    assert run(fakes, "version").stdout.startswith(f"dismal {__version__} (python ")
    for source in SOURCES:
        res = run(fakes, source, "--help")
        assert res.exit_code == 0 and f"dismal {source}" in res.stdout
        assert run(fakes, source, "--version").stdout == f"dismal {__version__}\n"
        assert run(fakes, source, "version", "--short").stdout.strip() == __version__


def test_sources_keep_their_commands(fakes: FakeAll, keyed: dict[str, str]) -> None:
    res = run(fakes, "bls", "latest", "LNS14000000", "-f", "json")
    assert res.exit_code == 0 and json.loads(res.stdout)[0]["series_id"] == "LNS14000000"
    res = run(fakes, "bea", "latest", "NIPA", "-t", "T10101", "-F", "Q", "-f", "json")
    assert res.exit_code == 0 and json.loads(res.stdout)[0]["dataset"] == "NIPA"
    res = run(fakes, "fred", "latest", "UNRATE", "-f", "json")
    assert res.exit_code == 0 and json.loads(res.stdout)[0]["series_id"] == "UNRATE"
    # offline discovery through the root
    res = run(fakes, "bls", "search", "core cpi", "--limit", "1", "-f", "json")
    assert res.exit_code == 0 and json.loads(res.stdout)[0]["id"].startswith("CU")
    res = run(fakes, "bea", "search", "real gdp", "--limit", "1", "-f", "json")
    assert res.exit_code == 0 and json.loads(res.stdout)[0]["command"].startswith("dismal bea data")
    res = run(fakes, "fred", "search", "unemployment rate", "--limit", "1", "-f", "json")
    assert res.exit_code == 0 and json.loads(res.stdout)[0]["id"] == "UNRATE"


def test_global_flags_before_or_after_the_source(fakes: FakeAll, keyed: dict[str, str]) -> None:
    noisy = run(fakes, "bls", "data", "LNS14000000", "NOPE1", "--latest", "-f", "json")
    assert noisy.exit_code == 0 and "dismal bls: warning:" in noisy.stderr
    before = run(fakes, "-q", "bls", "data", "LNS14000000", "NOPE1", "--latest", "-f", "json")
    after = run(fakes, "bls", "-q", "data", "LNS14000000", "NOPE1", "--latest", "-f", "json")
    assert before.exit_code == 0 and before.stderr == ""
    assert after.exit_code == 0 and after.stderr == ""
    assert run(fakes, "-v", "fred", "latest", "UNRATE", "-f", "json").exit_code == 0


def test_errors_carry_the_source_prefix_and_exit_codes(fakes: FakeAll) -> None:
    res = run(fakes, "fred", "latest", "UNRATE", "-f", "json")  # no FRED_API_KEY
    assert res.exit_code == 7 and res.stderr.startswith("dismal fred: error: FRED_API_KEY")
    assert "dismal fred: hint:" in res.stderr
    res = run(fakes, "bls", "config", env={"BLS_TIMEOUT": "slow"})
    assert res.exit_code == 2 and "BLS_TIMEOUT" in res.output
    res = run(fakes, "config", env={"BEA_MAX_RETRIES": "many"})
    assert res.exit_code == 2 and "BEA_MAX_RETRIES" in res.output


def test_config_aggregates_every_source(fakes: FakeAll, keyed: dict[str, str]) -> None:
    res = run(fakes, "config")
    assert res.exit_code == 0
    cfg = json.loads(res.stdout)
    assert cfg["version"] == __version__ and set(cfg["sources"]) == set(SOURCES)
    assert cfg["sources"]["bls"]["api_key"] == "***********1234"
    assert cfg["sources"]["bea"]["api_key_env"] == "BEA_API_KEY"
    assert cfg["sources"]["fred"]["base_url"] == "https://api.stlouisfed.org/fred"
    for key in keyed.values():
        assert key not in res.stdout
    # each source's own `config` is the same record
    own = json.loads(run(fakes, "fred", "config").stdout)
    assert own == cfg["sources"]["fred"]


def test_doctor_aggregates_every_source(fakes: FakeAll, keyed: dict[str, str]) -> None:
    res = run(fakes, "doctor")
    assert res.exit_code == 0
    report = json.loads(res.stdout)
    assert report["healthy"] is True and set(report["sources"]) == set(SOURCES)
    assert all(r["healthy"] for r in report["sources"].values())
    fakes.fred.http_status_override = 500
    res = run(fakes, "doctor", env={"FRED_MAX_RETRIES": "0"})
    report = json.loads(res.stdout)
    assert res.exit_code != 0 and report["healthy"] is False
    assert report["sources"]["bls"]["healthy"] and not report["sources"]["fred"]["healthy"]


def test_doctor_without_keys(fakes: FakeAll) -> None:
    res = run(fakes, "doctor")
    report = json.loads(res.stdout)
    assert res.exit_code == 7 and report["healthy"] is False
    assert report["sources"]["bls"]["healthy"] is True  # BLS works without a key
    assert report["sources"]["bea"]["healthy"] is False
    assert report["sources"]["fred"]["healthy"] is False


def test_cache_aggregates_every_source(fakes: FakeAll, cache_dirs: dict[str, Path]) -> None:
    res = run(fakes, "cache", "info", "-f", "json")
    assert res.exit_code == 0 and json.loads(res.stdout) == []
    (cache_dirs["bls"] / "flatfiles").mkdir(parents=True)
    (cache_dirs["bls"] / "flatfiles" / "cu.series").write_text("x")
    cache_dirs["fred"].mkdir(parents=True)
    (cache_dirs["fred"] / "releases.json").write_text("{}")
    res = run(fakes, "cache", "info", "-f", "json")
    rows = json.loads(res.stdout)
    assert [(r["source"], r["file"]) for r in rows] == [
        ("bls", "flatfiles/cu.series"),
        ("fred", "releases.json"),
    ]
    res = run(fakes, "cache", "info", "-f", "csv")
    assert res.stdout.splitlines()[0] == "source,file,bytes"
    res = run(fakes, "cache", "clear")
    assert res.exit_code == 0
    assert "bls: removed 1" in res.stderr and "fred: removed 1" in res.stderr
    assert "bea: removed 0" in res.stderr
    assert not (cache_dirs["bls"] / "flatfiles" / "cu.series").exists()
    assert not (cache_dirs["fred"] / "releases.json").exists()
    res = run(fakes, "-q", "cache", "clear")
    assert res.exit_code == 0 and res.stderr == ""


def test_cache_dirs_default_under_dismal(fakes: FakeAll, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("XDG_CACHE_HOME", "/x")
    for source in SOURCES:
        monkeypatch.delenv(f"{source.upper()}_CACHE_DIR", raising=False)
    cfg = json.loads(run(fakes, "config").stdout)
    for source in SOURCES:
        assert cfg["sources"][source]["cache_dir"] == f"/x/dismal/{source}"


def test_python_m_entry_points() -> None:
    import subprocess
    import sys

    out = subprocess.run(
        [sys.executable, "-m", "dismal", "--version"], capture_output=True, text=True, check=True
    )
    assert out.stdout == f"dismal {__version__}\n"
    out = subprocess.run(
        [sys.executable, "-m", "dismal.bls", "search", "core cpi", "--limit", "1", "-f", "json"],
        capture_output=True,
        text=True,
        check=True,
    )
    assert json.loads(out.stdout)[0]["id"].startswith("CU")
