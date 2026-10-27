from __future__ import annotations

import csv
import io
import json
from pathlib import Path

import pyarrow.parquet as pq
import pytest
from typer.testing import CliRunner

from dismal.bls.cli import app
from dismal.bls.cli._common import State
from tests.bls.conftest import FakeBLS
from tests.bls.test_flatfiles_cache_config import CU_SERIES

runner = CliRunner()


def run(fake: FakeBLS, *args: str, env: dict[str, str] | None = None, input: str | None = None):
    state = State(transport=fake.transport)
    return runner.invoke(app, list(args), obj=state, env=env, input=input, catch_exceptions=False)


@pytest.fixture
def keyed(monkeypatch: pytest.MonkeyPatch, cache_dir: Path) -> dict[str, str]:
    monkeypatch.setenv("BLS_API_KEY", "secret-key-1234")
    return {"BLS_API_KEY": "secret-key-1234"}


def test_help_and_version(fake: FakeBLS) -> None:
    assert run(fake, "--help").exit_code == 0
    res = run(fake, "--version")
    assert res.exit_code == 0 and res.stdout.startswith("dismal ")
    res = run(fake, "version", "--short")
    assert res.exit_code == 0 and res.stdout.strip()


def test_data_json_default_when_not_tty(fake: FakeBLS, keyed: dict[str, str]) -> None:
    res = run(fake, "data", "LNS14000000", "--start", "2024-01", "--end", "2024-03")
    assert res.exit_code == 0, res.output
    rows = json.loads(res.stdout)
    assert [r["period"] for r in rows] == ["M01", "M02", "M03"]
    assert rows[0]["date"] == "2024-01-01" and rows[0]["series_id"] == "LNS14000000"
    assert set(rows[0]) == {
        "series_id",
        "date",
        "year",
        "period",
        "period_name",
        "frequency",
        "value",
        "footnotes",
        "latest",
    }
    assert fake.payloads[0]["startyear"] == "2024" and fake.payloads[0]["endyear"] == "2024"
    assert fake.payloads[0]["registrationkey"] == "secret-key-1234"


def test_data_csv_wide_and_output_file(
    fake: FakeBLS, keyed: dict[str, str], tmp_path: Path
) -> None:
    out = tmp_path / "wide.csv"
    res = run(
        fake,
        "data",
        "CUUR0000SA0,CUSR0000SA0",
        "--years",
        "1",
        "--layout",
        "wide",
        "-f",
        "csv",
        "-o",
        str(out),
    )
    assert res.exit_code == 0, res.output
    rows = list(csv.DictReader(io.StringIO(out.read_text())))
    assert list(rows[0]) == ["date", "year", "period", "period_name", "CUUR0000SA0", "CUSR0000SA0"]
    assert rows[0]["period"] == "M01"
    assert "wrote" in res.stderr


def test_data_parquet_stdout(fake: FakeBLS, keyed: dict[str, str]) -> None:
    res = run(fake, "data", "LNS14000000", "--latest", "-f", "parquet")
    assert res.exit_code == 0
    table = pq.read_table(io.BytesIO(res.stdout_bytes))
    assert table.num_rows == 1 and table.column("latest")[0].as_py() is True


def test_latest_with_catalog_and_calculations(fake: FakeBLS, keyed: dict[str, str]) -> None:
    res = run(
        fake, "latest", "LNS14000000", "CES0000000001", "--catalog", "--calculations", "-f", "jsonl"
    )
    assert res.exit_code == 0, res.output
    rows = [json.loads(line) for line in res.stdout.splitlines()]
    assert [r["series_id"] for r in rows] == ["LNS14000000", "CES0000000001"]
    assert rows[0]["series_title"] == "(Seas) Unemployment Rate"
    assert rows[0]["pct_change_12"] == 6.0
    assert fake.payloads[0]["latest"] == "true"


def test_data_frequency_filter_and_annual_average(fake: FakeBLS, keyed: dict[str, str]) -> None:
    res = run(
        fake,
        "data",
        "LNS14000000",
        "-s",
        "2023",
        "-e",
        "2024",
        "--annual-average",
        "-F",
        "annual",
        "-f",
        "json",
    )
    assert res.exit_code == 0, res.output
    rows = json.loads(res.stdout)
    assert [(r["year"], r["period"]) for r in rows] == [(2023, "M13"), (2024, "M13")]
    assert rows[0]["annual_average"] is True and rows[0]["footnotes"] == "A: Annual average"
    res = run(
        fake, "data", "LNS14000000", "-s", "2023", "-e", "2023", "--annual-average", "-f", "json"
    )
    periods = [r["period"] for r in json.loads(res.stdout)]
    assert periods[-1] == "M13" and len(periods) == 13


def test_data_quarter_bounds_overlap(fake: FakeBLS, keyed: dict[str, str]) -> None:
    res = run(fake, "data", "PRS85006092", "--start", "2024-05", "--end", "2024-Q3", "-f", "csv")
    assert res.exit_code == 0, res.output
    periods = [r["period"] for r in csv.DictReader(io.StringIO(res.stdout))]
    assert periods == ["Q02", "Q03"]


def test_data_descending_columns_and_raw(fake: FakeBLS, keyed: dict[str, str]) -> None:
    res = run(
        fake,
        "data",
        "LNS14000000",
        "-y",
        "1",
        "--descending",
        "--columns",
        "period,value",
        "-f",
        "csv",
    )
    assert res.exit_code == 0, res.output
    lines = res.stdout.splitlines()
    assert lines[0] == "period,value" and lines[1].startswith("M09")
    res = run(fake, "data", "LNS14000000", "--start", "2024-11", "--end", "2024-12", "--raw")
    assert res.exit_code == 0, res.output
    raw = json.loads(res.stdout)
    assert raw["status"] == "REQUEST_SUCCEEDED"
    assert [d["period"] for d in raw["Results"]["series"][0]["data"]] == ["M11", "M12"]
    res = run(fake, "data", "LNS14000000", "--raw", "-f", "csv")
    assert res.exit_code == 2


def test_data_series_file_and_stdin(fake: FakeBLS, keyed: dict[str, str], tmp_path: Path) -> None:
    f = tmp_path / "ids.txt"
    f.write_text("# comment\nLNS14000000\nCUUR0000SA0 # cpi\n\n")
    res = run(fake, "data", "--series-file", str(f), "--latest", "-f", "jsonl")
    assert res.exit_code == 0, res.output
    assert [json.loads(ln)["series_id"] for ln in res.stdout.splitlines()] == [
        "LNS14000000",
        "CUUR0000SA0",
    ]
    res = run(fake, "data", "-S", "-", "--latest", "-f", "jsonl", input="CES0000000001\n")
    assert res.exit_code == 0, res.output
    assert json.loads(res.stdout)["series_id"] == "CES0000000001"


def test_data_usage_errors(fake: FakeBLS, keyed: dict[str, str]) -> None:
    assert run(fake, "data").exit_code == 2
    assert run(fake, "data", "X", "--years", "2", "--start", "2020").exit_code == 2
    assert run(fake, "data", "X", "--start", "2021", "--end", "2020").exit_code == 2
    assert run(fake, "data", "X", "--start", "20x1").exit_code == 2
    assert run(fake, "data", "X", "--latest", "--years", "1").exit_code == 2
    assert run(fake, "data", "X", "--layout", "diagonal").exit_code == 2
    res = run(fake, "data", "LNS14000000", "--latest", "--columns", "nope")
    assert res.exit_code == 2 and "unknown column" in res.output


def test_data_strict_and_warnings(fake: FakeBLS, keyed: dict[str, str]) -> None:
    res = run(fake, "data", "LNS14000000", "NOPE1", "--latest", "-f", "json")
    assert res.exit_code == 0
    assert (
        "Series does not exist" in res.stderr and "no observations returned for NOPE1" in res.stderr
    )
    res = run(fake, "data", "LNS14000000", "NOPE1", "--latest", "--strict", "-f", "json")
    assert res.exit_code == 6 and "NOPE1" in res.stderr
    res = run(fake, "-q", "data", "LNS14000000", "NOPE1", "--latest", "-f", "json")
    assert res.exit_code == 0 and res.stderr == ""


def test_exit_codes_from_api(fake: FakeBLS, keyed: dict[str, str]) -> None:
    fake.status_override = "REQUEST_NOT_PROCESSED"
    fake.messages_override = ["daily threshold exceeded"]
    res = run(fake, "data", "LNS14000000", "--latest")
    assert res.exit_code == 4 and "dismal bls: error:" in res.stderr and "hint" in res.stderr
    fake.status_override = "REQUEST_FAILED_INVALID_PARAMETERS"
    fake.messages_override = ["bad"]
    assert run(fake, "data", "LNS14000000", "--latest").exit_code == 3
    fake.status_override = None
    fake.http_status_override = 503
    res = run(fake, "data", "LNS14000000", "--latest", env={"BLS_MAX_RETRIES": "0"})
    assert res.exit_code == 3


def test_no_key_warns_for_catalog(fake: FakeBLS, cache_dir: Path) -> None:
    res = run(fake, "latest", "LNS14000000", "--catalog", "-f", "json")
    assert res.exit_code == 0
    assert "registration key" in res.stderr
    assert "registrationkey" not in fake.payloads[0]


def test_bls_format_env(fake: FakeBLS, keyed: dict[str, str]) -> None:
    res = run(fake, "latest", "LNS14000000", env={"BLS_FORMAT": "csv"})
    assert res.exit_code == 0 and res.stdout.startswith("series_id,")
    res = run(fake, "latest", "LNS14000000", env={"BLS_FORMAT": "xml"})
    assert res.exit_code == 2


def test_table_format(fake: FakeBLS, keyed: dict[str, str]) -> None:
    res = run(fake, "latest", "LNS14000000", "-f", "table")
    assert res.exit_code == 0 and "LNS14000000" in res.stdout and "series_id" in res.stdout


def test_search_commands(fake: FakeBLS, cache_dir: Path) -> None:
    res = run(fake, "search", "core", "cpi", "-n", "2", "-f", "json")
    assert res.exit_code == 0
    hits = json.loads(res.stdout)
    assert len(hits) == 2 and hits[0]["id"].endswith("SA0L1E")
    res = run(fake, "search", "jolts", "-k", "all", "-f", "json")
    kinds = {h["kind"] for h in json.loads(res.stdout)}
    assert kinds == {"series", "survey"}
    res = run(fake, "search", "qqqqzzzz", "-f", "json")
    assert res.exit_code == 0 and json.loads(res.stdout) == [] and "no matches" in res.stderr
    assert run(fake, "search", "x", "-k", "bogus").exit_code == 2
    assert fake.requests == []  # fully offline


def test_surveys_offline_refresh_and_show(
    fake: FakeBLS, keyed: dict[str, str], cache_dir: Path
) -> None:
    res = run(fake, "surveys", "-f", "json")
    assert res.exit_code == 0 and len(json.loads(res.stdout)) > 20 and fake.requests == []
    res = run(fake, "surveys", "--refresh", "-f", "json")
    assert res.exit_code == 0
    assert [s["abbreviation"] for s in json.loads(res.stdout)] == ["CU", "LN", "CE"]
    assert (cache_dir / "surveys.json").is_file()
    res = run(fake, "surveys", "-f", "json")  # now served from the cache
    assert [s["abbreviation"] for s in json.loads(res.stdout)] == ["CU", "LN", "CE"]
    res = run(fake, "surveys", "-q", "labor", "-f", "json")
    assert json.loads(res.stdout)[0]["abbreviation"] == "LN"
    res = run(fake, "surveys", "show", "cu")
    assert res.exit_code == 0 and json.loads(res.stdout)["survey_abbreviation"] == "CU"
    assert run(fake, "surveys", "show", "zz").exit_code == 3


def test_popular(fake: FakeBLS, keyed: dict[str, str]) -> None:
    res = run(fake, "popular", "-f", "json")
    assert res.exit_code == 0
    rows = json.loads(res.stdout)
    assert [r["series_id"] for r in rows] == ["LNS14000000", "CUUR0000SA0", "CES0000000001"]
    assert rows[0]["survey"] == "LN" and "survey_name" in rows[0]
    res = run(fake, "popular", "--survey", "cu", "--catalog", "-f", "json")
    rows = json.loads(res.stdout)
    assert rows[0]["title"].startswith("All items")


def test_series_list_and_info(fake: FakeBLS, keyed: dict[str, str], cache_dir: Path) -> None:
    fake.flatfiles["cu.series"] = CU_SERIES
    res = run(fake, "series", "list", "--survey", "cu", "-f", "json")
    assert res.exit_code == 0, res.output
    rows = json.loads(res.stdout)
    assert [r["series_id"] for r in rows] == ["CUUR0000SA0", "CUUR0000SETB01"]
    assert rows[0]["title"].startswith("All items") and rows[0]["area_code"] == "0000"
    res = run(
        fake,
        "series",
        "list",
        "-u",
        "cu",
        "-q",
        "gasoline",
        "-f",
        "json",
        "--columns",
        "series_id,score",
    )
    rows = json.loads(res.stdout)
    assert rows == [{"series_id": "CUUR0000SETB01", "score": rows[0]["score"]}]
    res = run(fake, "series", "info", "LNS14000000", "-f", "json")
    assert res.exit_code == 0, res.output
    info = json.loads(res.stdout)[0]
    assert info["series_title"] == "(Seas) Unemployment Rate" and info["latest_period"] == "M09"


def test_config_doctor_cache(fake: FakeBLS, keyed: dict[str, str], cache_dir: Path) -> None:
    res = run(fake, "config")
    assert res.exit_code == 0
    cfg = json.loads(res.stdout)
    assert cfg["api_key"] == "***********1234" and cfg["limits"]["series_per_request"] == 50
    assert "secret-key-1234" not in res.stdout
    res = run(fake, "doctor")
    assert res.exit_code == 0 and json.loads(res.stdout)["healthy"] is True
    fake.http_status_override = 500
    res = run(fake, "doctor", env={"BLS_MAX_RETRIES": "0"})
    assert res.exit_code == 5 and json.loads(res.stdout)["healthy"] is False
    fake.http_status_override = None
    (cache_dir / "flatfiles").mkdir(parents=True)
    (cache_dir / "flatfiles" / "cu.series").write_text("x")
    res = run(fake, "cache", "info", "-f", "json")
    assert json.loads(res.stdout)[0]["file"] == "flatfiles/cu.series"
    res = run(fake, "cache", "clear")
    assert res.exit_code == 0 and "removed 1" in res.stderr
    assert not (cache_dir / "flatfiles" / "cu.series").exists()


def test_bad_env_value_is_usage_error(fake: FakeBLS) -> None:
    res = run(fake, "config", env={"BLS_TIMEOUT": "slow"})
    assert res.exit_code == 2
