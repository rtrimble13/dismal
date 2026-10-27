from __future__ import annotations

import csv
import io
import json
from pathlib import Path

import pyarrow.parquet as pq
import pytest
from typer.testing import CliRunner

from dismal.fred.cli import app
from dismal.fred.cli._common import State
from tests.fred.conftest import THIS_YEAR, VALID_KEY, FakeFRED

runner = CliRunner()


def run(fake: FakeFRED, *args: str, env: dict[str, str] | None = None, input: str | None = None):
    state = State(transport=fake.transport)
    return runner.invoke(app, list(args), obj=state, env=env, input=input, catch_exceptions=False)


@pytest.fixture
def keyed(monkeypatch: pytest.MonkeyPatch, cache_dir: Path) -> dict[str, str]:
    monkeypatch.setenv("FRED_API_KEY", VALID_KEY)
    return {"FRED_API_KEY": VALID_KEY}


def test_help_and_version(fake: FakeFRED) -> None:
    assert run(fake, "--help").exit_code == 0
    res = run(fake, "--version")
    assert res.exit_code == 0 and res.stdout.startswith("dismal ")
    res = run(fake, "version", "--short")
    assert res.exit_code == 0 and res.stdout.strip()


def test_data_json_default_when_not_tty(fake: FakeFRED, keyed: dict[str, str]) -> None:
    res = run(fake, "data", "UNRATE", "--start", "2024-01", "--end", "2024-Q1")
    assert res.exit_code == 0, res.output
    rows = json.loads(res.stdout)
    assert [r["date"] for r in rows] == ["2024-01-01", "2024-02-01", "2024-03-01"]
    assert list(rows[0]) == ["series_id", "date", "value"] and rows[0]["series_id"] == "UNRATE"
    assert isinstance(rows[0]["value"], float)
    sent = fake.params[0]
    assert sent["api_key"] == VALID_KEY and sent["file_type"] == "json"
    assert sent["observation_start"] == "2024-01-01" and sent["observation_end"] == "2024-03-31"
    assert fake.requests[0].url.path == "/fred/series/observations"


def test_data_csv_wide_and_output_file(
    fake: FakeFRED, keyed: dict[str, str], tmp_path: Path
) -> None:
    out = tmp_path / "wide.csv"
    res = run(
        fake,
        "data",
        "GDP,GDPC1",
        "--start",
        "2023",
        "--end",
        "2023",
        "--layout",
        "wide",
        "-f",
        "csv",
        "-o",
        str(out),
    )
    assert res.exit_code == 0, res.output
    rows = list(csv.DictReader(io.StringIO(out.read_text())))
    assert list(rows[0]) == ["date", "GDP", "GDPC1"]
    assert [r["date"] for r in rows] == ["2023-01-01", "2023-04-01", "2023-07-01", "2023-10-01"]
    assert "wrote" in res.stderr and len(fake.params) == 2


def test_data_parquet_stdout(fake: FakeFRED, keyed: dict[str, str]) -> None:
    res = run(fake, "data", "UNRATE", "--latest", "-f", "parquet")
    assert res.exit_code == 0
    table = pq.read_table(io.BytesIO(res.stdout_bytes))
    assert table.num_rows == 1 and str(table.schema.field("date").type) == "date32[day]"
    assert table.column("date")[0].as_py().year == THIS_YEAR
    assert fake.params[0]["sort_order"] == "desc" and fake.params[0]["limit"] == "1"


def test_latest_with_meta(fake: FakeFRED, keyed: dict[str, str]) -> None:
    res = run(fake, "latest", "UNRATE", "GDP", "--meta", "-f", "jsonl")
    assert res.exit_code == 0, res.output
    rows = [json.loads(line) for line in res.stdout.splitlines()]
    assert [r["series_id"] for r in rows] == ["UNRATE", "GDP"]
    assert rows[0]["title"] == "Unemployment Rate" and rows[0]["seasonal_adjustment"] == "SA"
    assert rows[1]["frequency"] == "Quarterly" and rows[1]["units"] == "Billions of Dollars"
    assert list(rows[0])[:3] == ["series_id", "date", "value"]
    assert len(fake.params) == 4  # observations + metadata per series


def test_data_units_frequency_aggregation(fake: FakeFRED, keyed: dict[str, str]) -> None:
    res = run(
        fake,
        "data",
        "CPIAUCSL",
        "--units",
        "pc1",
        "--start",
        "2024-01",
        "--end",
        "2024-03",
        "-f",
        "json",
    )
    assert res.exit_code == 0, res.output
    assert fake.params[0]["units"] == "pc1"
    assert all(0 < r["value"] < 5 for r in json.loads(res.stdout))
    res = run(
        fake,
        "data",
        "DGS10",
        "-F",
        "monthly",
        "--aggregation",
        "eop",
        "--start",
        "2024-01",
        "--end",
        "2024-03",
        "-f",
        "json",
    )
    assert res.exit_code == 0, res.output
    assert fake.params[-1]["frequency"] == "m" and fake.params[-1]["aggregation_method"] == "eop"
    assert [r["date"] for r in json.loads(res.stdout)] == ["2024-01-01", "2024-02-01", "2024-03-01"]
    assert run(fake, "data", "DGS10", "--aggregation", "sum").exit_code == 2
    assert run(fake, "data", "DGS10", "-F", "hourly").exit_code == 2
    assert run(fake, "data", "DGS10", "-u", "sqrt").exit_code == 2


def test_data_as_of_vintage(fake: FakeFRED, keyed: dict[str, str]) -> None:
    current = run(fake, "data", "PAYEMS", "--start", "2023-01", "--end", "2023-06", "-f", "json")
    vintage = run(
        fake,
        "data",
        "PAYEMS",
        "--start",
        "2023-01",
        "--end",
        "2023-06",
        "--as-of",
        "2023-09-01",
        "-f",
        "json",
    )
    assert vintage.exit_code == 0, vintage.output
    cur, old = json.loads(current.stdout), json.loads(vintage.stdout)
    assert (
        fake.params[-1]["realtime_start"] == "2023-09-01"
        and fake.params[-1]["realtime_end"] == "2023-09-01"
    )
    assert list(old[0]) == ["series_id", "date", "value", "realtime_start", "realtime_end"]
    assert old[0]["realtime_start"] == "2023-09-01"
    assert old[0]["value"] == pytest.approx(cur[0]["value"] - 0.5)
    assert "realtime_start" not in cur[0]
    assert run(fake, "data", "PAYEMS", "--as-of", "yesterday").exit_code == 2


def test_data_descending_columns_and_raw(fake: FakeFRED, keyed: dict[str, str]) -> None:
    res = run(
        fake, "data", "UNRATE", "-y", "1", "--descending", "--columns", "date,value", "-f", "csv"
    )
    assert res.exit_code == 0, res.output
    lines = res.stdout.splitlines()
    assert lines[0] == "date,value" and lines[1].startswith(f"{THIS_YEAR}-06-01")
    assert fake.params[0]["observation_start"] == f"{THIS_YEAR}-01-01"
    res = run(fake, "data", "UNRATE", "--start", "2024-11", "--end", "2024-12", "--raw")
    assert res.exit_code == 0, res.output
    raw = json.loads(res.stdout)
    assert raw["params"]["observation_start"] == "2024-11-01"
    assert [o["date"] for o in raw["series"][0]["observations"]] == ["2024-11-01", "2024-12-01"]
    assert raw["series"][0]["observations"][0]["value"].replace(".", "").isdigit()
    assert VALID_KEY not in res.stdout
    assert run(fake, "data", "UNRATE", "--raw", "-f", "csv").exit_code == 2


def test_data_series_file_and_stdin(fake: FakeFRED, keyed: dict[str, str], tmp_path: Path) -> None:
    f = tmp_path / "ids.txt"
    f.write_text("# comment\nUNRATE\ngdp # nominal\n\n")
    res = run(fake, "data", "--series-file", str(f), "--latest", "-f", "jsonl")
    assert res.exit_code == 0, res.output
    assert [json.loads(ln)["series_id"] for ln in res.stdout.splitlines()] == ["UNRATE", "GDP"]
    res = run(fake, "data", "-S", "-", "--latest", "-f", "jsonl", input="CPIAUCSL\n")
    assert res.exit_code == 0, res.output
    assert json.loads(res.stdout)["series_id"] == "CPIAUCSL"
    res = run(fake, "data", "-S", str(tmp_path / "missing.txt"), "--latest", "-f", "jsonl")
    assert res.exit_code == 2
    assert "cannot read series file" in res.output


def test_data_usage_errors(fake: FakeFRED, keyed: dict[str, str]) -> None:
    assert run(fake, "data").exit_code == 2
    assert run(fake, "data", "X", "--years", "2", "--start", "2020").exit_code == 2
    assert run(fake, "data", "X", "--start", "2021", "--end", "2020").exit_code == 2
    assert run(fake, "data", "X", "--start", "20x1").exit_code == 2
    assert run(fake, "data", "X", "--latest", "--years", "1").exit_code == 2
    assert run(fake, "data", "X", "--years", "0").exit_code == 2
    assert run(fake, "data", "X", "--layout", "diagonal").exit_code == 2
    res = run(fake, "data", "UNRATE", "--latest", "--columns", "nope")
    assert res.exit_code == 2 and "unknown column" in res.output


def test_data_strict_and_warnings(fake: FakeFRED, keyed: dict[str, str]) -> None:
    res = run(fake, "data", "UNRATE", "NOPE1", "--latest", "-f", "json")
    assert res.exit_code == 0 and [r["series_id"] for r in json.loads(res.stdout)] == ["UNRATE"]
    assert "series NOPE1 does not exist" in res.stderr
    res = run(fake, "data", "UNRATE", "NOPE1", "--latest", "--strict", "-f", "json")
    assert res.exit_code == 6 and "NOPE1" in res.stderr
    res = run(fake, "-q", "data", "UNRATE", "NOPE1", "--latest", "-f", "json")
    assert res.exit_code == 0 and res.stderr == ""
    res = run(fake, "data", "UNRATE", "--start", "2001", "--end", "2001", "--strict", "-f", "json")
    assert res.exit_code == 6 and "no observations returned for UNRATE" in res.stderr


def test_exit_codes_from_api(fake: FakeFRED, keyed: dict[str, str]) -> None:
    fake.http_status_override = 429
    res = run(fake, "data", "UNRATE", "--latest", env={"FRED_MAX_RETRIES": "0"})
    assert res.exit_code == 4 and "dismal fred: error:" in res.stderr and "hint" in res.stderr
    fake.http_status_override = 400
    assert run(fake, "data", "UNRATE", "--latest").exit_code == 3
    fake.http_status_override = 503
    assert run(fake, "data", "UNRATE", "--latest", env={"FRED_MAX_RETRIES": "0"}).exit_code == 3
    fake.http_status_override = None
    res = run(fake, "data", "DGS10", "-F", "d", "--latest")  # daily -> daily is fine
    assert res.exit_code == 0
    res = run(fake, "data", "GDP", "-F", "m", "--latest")  # cannot raise the frequency
    assert res.exit_code == 3 and "frequency" in res.stderr


def test_key_handling(fake: FakeFRED, cache_dir: Path) -> None:
    res = run(fake, "latest", "UNRATE", "-f", "json")
    assert res.exit_code == 7 and "FRED_API_KEY is not set" in res.stderr and fake.requests == []
    res = run(fake, "latest", "UNRATE", "-f", "json", env={"FRED_API_KEY": "bogus"})
    assert res.exit_code == 7 and "rejected the key" in res.stderr and "FRED_API_KEY" in res.stderr


def test_fred_format_env(fake: FakeFRED, keyed: dict[str, str]) -> None:
    res = run(fake, "latest", "UNRATE", env={"FRED_FORMAT": "csv"})
    assert res.exit_code == 0 and res.stdout.startswith("series_id,date,value")
    res = run(fake, "latest", "UNRATE", env={"FRED_FORMAT": "xml"})
    assert res.exit_code == 2


def test_table_format(fake: FakeFRED, keyed: dict[str, str]) -> None:
    res = run(fake, "latest", "UNRATE", "-f", "table")
    assert res.exit_code == 0 and "UNRATE" in res.stdout and "series_id" in res.stdout


def test_search_offline(fake: FakeFRED, cache_dir: Path) -> None:
    res = run(fake, "search", "unemployment", "rate", "-n", "2", "-f", "json")
    assert res.exit_code == 0
    hits = json.loads(res.stdout)
    assert len(hits) == 2 and hits[0]["id"] == "UNRATE" and hits[0]["score"] == 100.0
    assert set(hits[0]) == {
        "kind",
        "id",
        "title",
        "score",
        "frequency",
        "seasonal",
        "units",
        "source",
    }
    res = run(fake, "search", "jobs report", "-n", "1", "-f", "json")
    assert json.loads(res.stdout)[0]["id"] == "PAYEMS"
    res = run(fake, "search", "qqqqzzzz", "-f", "json")
    assert (
        res.exit_code == 0 and json.loads(res.stdout) == [] and "fred series search" in res.stderr
    )
    assert fake.requests == []  # fully offline


def test_series_info_search_vintages_updates(fake: FakeFRED, keyed: dict[str, str]) -> None:
    res = run(fake, "series", "info", "unrate", "NOPE", "-f", "json")
    assert res.exit_code == 0, res.output
    rows = json.loads(res.stdout)
    assert rows == [rows[0]] and rows[0]["id"] == "UNRATE" and rows[0]["frequency"] == "Monthly"
    assert rows[0]["observation_start"] == "2010-01-01" and "notes" not in rows[0]
    assert "series NOPE does not exist" in res.stderr
    res = run(fake, "series", "info", "GDP", "--notes", "-f", "json")
    assert json.loads(res.stdout)[0]["notes"] == "Notes for GDP."
    res = run(fake, "series", "search", "gross domestic product", "-f", "json")
    assert res.exit_code == 0, res.output
    assert [r["id"] for r in json.loads(res.stdout)] == ["GDP", "GDPC1"]
    assert fake.params[-1]["search_text"] == "gross domestic product"
    res = run(fake, "series", "search", "a", "--frequency", "m", "--seasonal", "sa")
    assert res.exit_code == 2
    res = run(fake, "series", "search", "price", "-F", "monthly", "-n", "1", "-f", "json")
    assert (
        json.loads(res.stdout)[0]["id"] == "CPIAUCSL"
        and fake.params[-1]["filter_value"] == "Monthly"
    )
    assert "1 series match" not in res.stderr
    res = run(
        fake,
        "series",
        "search",
        "g",
        "--id",
        "--order-by",
        "series_id",
        "--sort",
        "asc",
        "-f",
        "json",
    )
    assert [r["id"] for r in json.loads(res.stdout)] == ["GDP", "GDPC1"]
    assert fake.params[-1]["search_type"] == "series_id"
    res = run(
        fake,
        "series",
        "search",
        "treasury",
        "--tag",
        "treasury",
        "--exclude-tag",
        "bls",
        "-f",
        "json",
    )
    assert [r["id"] for r in json.loads(res.stdout)] == ["DGS10"]
    assert fake.params[-1]["tag_names"] == "treasury"
    res = run(fake, "series", "search", "e", "-n", "1", "-f", "json")
    assert "series match; showing 1" in res.stderr
    assert run(fake, "series", "search", "x", "--order-by", "bogus").exit_code == 2
    res = run(fake, "series", "vintages", "payems", "-f", "json")
    assert [r["vintage_date"] for r in json.loads(res.stdout)][:2] == ["2024-01-05", "2024-02-02"]
    res = run(fake, "series", "updates", "-n", "3", "-f", "json")
    assert [r["id"] for r in json.loads(res.stdout)] == ["UNRATE", "CPIAUCSL", "GDP"]


def test_releases(fake: FakeFRED, keyed: dict[str, str], cache_dir: Path) -> None:
    res = run(fake, "releases", "-f", "json")
    assert res.exit_code == 0, res.output
    assert [r["id"] for r in json.loads(res.stdout)] == [10, 18, 50, 53, 180]
    assert (cache_dir / "releases.json").is_file()
    n = len(fake.requests)
    res = run(fake, "releases", "-q", "employment", "-f", "json")
    assert json.loads(res.stdout)[0]["id"] == 50 and len(fake.requests) == n  # cached
    run(fake, "releases", "--refresh", "-f", "json")
    assert len(fake.requests) == n + 1
    res = run(fake, "releases", "show", "53")
    assert res.exit_code == 0 and json.loads(res.stdout)["name"] == "Gross Domestic Product"
    assert run(fake, "releases", "show", "999").exit_code == 3
    res = run(fake, "releases", "series", "53", "-f", "json")
    assert [r["id"] for r in json.loads(res.stdout)] == ["GDP", "GDPC1"]
    res = run(fake, "releases", "dates", "--days", "7", "-f", "json")
    assert res.exit_code == 0, res.output
    rows = json.loads(res.stdout)
    assert rows[0]["release_id"] == 10 and len(rows) == 3
    assert fake.params[-1]["include_release_dates_with_no_data"] == "true"
    res = run(fake, "releases", "dates", "--days", "-7", "-f", "json")
    assert res.exit_code == 0


def test_categories(fake: FakeFRED, keyed: dict[str, str], cache_dir: Path) -> None:
    res = run(fake, "categories", "-f", "json")
    assert res.exit_code == 0, res.output
    assert [c["id"] for c in json.loads(res.stdout)] == [32991, 10, 32992, 32455]
    assert (cache_dir / "categories" / "0.json").is_file()
    res = run(fake, "categories", "-q", "prices", "-f", "json")
    assert json.loads(res.stdout)[0]["id"] == 32455
    res = run(fake, "categories", "children", "10", "-f", "json")
    assert json.loads(res.stdout) == [
        {"id": 12, "name": "Current Population Survey (Household Survey)", "parent_id": 10}
    ]
    res = run(fake, "categories", "children", "12", "-f", "json")
    assert json.loads(res.stdout) == [] and "no children" in res.stderr
    res = run(fake, "categories", "series", "32992", "-f", "json")
    assert [r["id"] for r in json.loads(res.stdout)] == ["GDP", "GDPC1"]


def test_config_doctor_cache(fake: FakeFRED, keyed: dict[str, str], cache_dir: Path) -> None:
    res = run(fake, "config")
    assert res.exit_code == 0
    cfg = json.loads(res.stdout)
    assert cfg["api_key"].endswith("cdef") and cfg["api_key"].startswith("****")
    assert VALID_KEY not in res.stdout and cfg["limits"]["requests_per_minute"] == 120
    res = run(fake, "doctor")
    assert res.exit_code == 0, res.output
    report = json.loads(res.stdout)
    assert report["healthy"] is True and report["checks"][1]["detail"] == "2 sources listed"
    fake.http_status_override = 500
    res = run(fake, "doctor", env={"FRED_MAX_RETRIES": "0"})
    assert res.exit_code == 3 and json.loads(res.stdout)["healthy"] is False
    fake.http_status_override = None
    res = run(fake, "doctor", env={"FRED_API_KEY": "SHORT"})
    assert res.exit_code == 7 and "32" in json.loads(res.stdout)["checks"][0]["detail"]
    (cache_dir / "categories").mkdir(parents=True)
    (cache_dir / "categories" / "0.json").write_text("[]")
    res = run(fake, "cache", "info", "-f", "json")
    assert json.loads(res.stdout)[0]["file"] == "categories/0.json"
    res = run(fake, "cache", "clear")
    assert res.exit_code == 0 and "removed 1" in res.stderr


def test_doctor_without_key(fake: FakeFRED, cache_dir: Path) -> None:
    res = run(fake, "doctor")
    assert res.exit_code == 7 and json.loads(res.stdout)["healthy"] is False and fake.requests == []


def test_bad_env_value_is_usage_error(fake: FakeFRED) -> None:
    assert run(fake, "config", env={"FRED_TIMEOUT": "slow"}).exit_code == 2


def test_many_series_warns_about_rate_limit(fake: FakeFRED, keyed: dict[str, str]) -> None:
    ids = [f"X{i}" for i in range(50)]
    res = run(fake, "latest", *ids, "-f", "json")
    assert res.exit_code == 0 and "120 per minute" in res.stderr
