from __future__ import annotations

import csv
import io
import json
from pathlib import Path

import pyarrow.parquet as pq
import pytest
from typer.testing import CliRunner

from dismal.bea.cli import app
from dismal.bea.cli._common import State
from tests.bea.conftest import LAST_MONTH, LAST_QUARTER, THIS_YEAR, VALID_KEY, FakeBEA

runner = CliRunner()


def run(fake: FakeBEA, *args: str, env: dict[str, str] | None = None, input: str | None = None):
    state = State(transport=fake.transport)
    return runner.invoke(app, list(args), obj=state, env=env, input=input, catch_exceptions=False)


@pytest.fixture
def keyed(monkeypatch: pytest.MonkeyPatch, cache_dir: Path) -> dict[str, str]:
    monkeypatch.setenv("BEA_API_KEY", VALID_KEY)
    return {"BEA_API_KEY": VALID_KEY}


def test_help_and_version(fake: FakeBEA) -> None:
    assert run(fake, "--help").exit_code == 0
    res = run(fake, "--version")
    assert res.exit_code == 0 and res.stdout.startswith("dismal ")
    res = run(fake, "version", "--short")
    assert res.exit_code == 0 and res.stdout.strip()


def test_data_json_default_when_not_tty(fake: FakeBEA, keyed: dict[str, str]) -> None:
    res = run(
        fake, "data", "NIPA", "-t", "T10101", "-F", "Q", "--start", "2024-01", "--end", "2024-Q3"
    )
    assert res.exit_code == 0, res.output
    rows = json.loads(res.stdout)
    gdp = [r for r in rows if r["series_id"] == "A191RL"]
    assert [r["period"] for r in gdp] == ["2024Q1", "2024Q2", "2024Q3"]
    assert gdp[0]["date"] == "2024-01-01" and gdp[0]["frequency"] == "quarterly"
    assert list(gdp[0]) == [
        "dataset",
        "series_id",
        "series_title",
        "date",
        "year",
        "period",
        "frequency",
        "value",
        "unit",
        "unit_mult",
        "note_ref",
        "table_name",
        "line_number",
        "metric_name",
    ]
    assert gdp[0]["series_title"] == "Gross domestic product" and gdp[0]["line_number"] == 1
    assert gdp[0]["unit"] == "Percent change, annual rate" and gdp[0]["unit_mult"] == 0
    sent = fake.params[0]
    assert sent["UserID"] == VALID_KEY and sent["method"] == "GetData"
    assert sent["datasetname"] == "NIPA" and sent["TableName"] == "T10101"
    assert sent["Frequency"] == "Q" and sent["Year"] == "2024"


def test_data_csv_wide_and_output_file(
    fake: FakeBEA, keyed: dict[str, str], tmp_path: Path
) -> None:
    out = tmp_path / "wide.csv"
    res = run(
        fake,
        "data",
        "nipa",
        "TableName=T10105",
        "-F",
        "A",
        "--start",
        "2020",
        "--end",
        "2022",
        "--layout",
        "wide",
        "-f",
        "csv",
        "-o",
        str(out),
    )
    assert res.exit_code == 0, res.output
    rows = list(csv.DictReader(io.StringIO(out.read_text())))
    assert list(rows[0]) == ["date", "year", "period", "A191RC", "DPCERC"]
    assert [r["period"] for r in rows] == ["2020", "2021", "2022"]
    assert "," not in rows[0]["A191RC"] and float(rows[0]["A191RC"]) > 0  # "27,720,709" parsed
    assert "wrote" in res.stderr
    assert fake.params[0]["datasetname"] == "NIPA" and fake.params[0]["Year"] == "2020,2021,2022"


def test_data_parquet_stdout(fake: FakeBEA, keyed: dict[str, str]) -> None:
    res = run(fake, "data", "NIPA", "-t", "T10101", "-F", "A", "--latest", "-f", "parquet")
    assert res.exit_code == 0
    table = pq.read_table(io.BytesIO(res.stdout_bytes))
    assert table.num_rows == 3  # one row per line
    assert str(table.schema.field("date").type) == "date32[day]"
    assert table.column("year")[0].as_py() == THIS_YEAR - 1


def test_latest_with_notes(fake: FakeBEA, keyed: dict[str, str]) -> None:
    res = run(fake, "latest", "NIPA", "-t", "T10101", "-F", "Q", "--notes", "-f", "jsonl")
    assert res.exit_code == 0, res.output
    rows = [json.loads(line) for line in res.stdout.splitlines()]
    assert [r["series_id"] for r in rows] == ["A191RL", "DPCERL", "DGDSRL"]
    assert all(r["period"] == f"{THIS_YEAR}Q{LAST_QUARTER}" for r in rows)
    assert rows[0]["note_ref"] == "T10101" and "LastRevised" in rows[0]["notes"]
    assert list(rows[0])[:12][-1] == "notes"  # notes sits right after note_ref
    assert fake.params[0]["Year"] == ",".join(str(y) for y in range(THIS_YEAR - 2, THIS_YEAR + 1))


def test_data_frequency_filter_mixed(fake: FakeBEA, keyed: dict[str, str]) -> None:
    res = run(
        fake,
        "data",
        "NIPA",
        "-t",
        "T10101",
        "-F",
        "annual",
        "-F",
        "quarterly",
        "-s",
        "2023",
        "-e",
        "2023",
        "-f",
        "json",
    )
    assert res.exit_code == 0, res.output
    rows = [r for r in json.loads(res.stdout) if r["series_id"] == "A191RL"]
    assert [r["period"] for r in rows] == ["2023Q1", "2023Q2", "2023Q3", "2023Q4", "2023"]
    assert fake.params[0]["Frequency"] == "A,Q"
    res = run(
        fake,
        "data",
        "NIPA",
        "-t",
        "T20600",
        "-F",
        "M",
        "-s",
        "2024-11",
        "-e",
        "2025-01",
        "-f",
        "csv",
    )
    periods = [
        r["period"] for r in csv.DictReader(io.StringIO(res.stdout)) if r["series_id"] == "A065RC"
    ]
    assert periods == ["2024M11", "2024M12", "2025M01"]


def test_data_quarter_bounds_overlap(fake: FakeBEA, keyed: dict[str, str]) -> None:
    res = run(
        fake,
        "data",
        "NIPA",
        "-t",
        "T10101",
        "-F",
        "Q",
        "--start",
        "2024-05",
        "--end",
        "2024Q3",
        "-f",
        "csv",
    )
    assert res.exit_code == 0, res.output
    periods = [
        r["period"] for r in csv.DictReader(io.StringIO(res.stdout)) if r["series_id"] == "A191RL"
    ]
    assert periods == ["2024Q2", "2024Q3"]


def test_data_descending_columns_and_raw(fake: FakeBEA, keyed: dict[str, str]) -> None:
    res = run(
        fake,
        "data",
        "NIPA",
        "-t",
        "T10101",
        "-F",
        "Q",
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
    assert lines[0] == "period,value" and lines[1].startswith(f"{THIS_YEAR}Q{LAST_QUARTER}")
    res = run(
        fake,
        "data",
        "NIPA",
        "-t",
        "T10101",
        "-F",
        "Q",
        "--start",
        "2024-Q3",
        "--end",
        "2024-Q4",
        "--raw",
    )
    assert res.exit_code == 0, res.output
    raw = json.loads(res.stdout)
    results = raw["BEAAPI"]["Results"]
    assert results["Statistic"] == "NIPA Table" and results["Notes"][0]["NoteRef"] == "T10101"
    assert [d["TimePeriod"] for d in results["Data"] if d["SeriesCode"] == "A191RL"] == [
        "2024Q3",
        "2024Q4",
    ]
    assert VALID_KEY not in res.stdout
    res = run(fake, "data", "NIPA", "-t", "T10101", "-F", "Q", "--raw", "-f", "csv")
    assert res.exit_code == 2


def test_data_multiple_tables_merged(fake: FakeBEA, keyed: dict[str, str]) -> None:
    res = run(
        fake, "data", "NIPA", "-t", "T10101", "-t", "T10105", "-F", "A", "-y", "2", "-f", "json"
    )
    assert res.exit_code == 0, res.output
    rows = json.loads(res.stdout)
    assert {r["table_name"] for r in rows} == {"T10101", "T10105"}
    assert len(fake.params) == 2 and [p["TableName"] for p in fake.params] == ["T10101", "T10105"]
    assert "one request per table" in res.stderr
    res = run(fake, "data", "NIPA", "TableName=T10101,T10105", "-F", "A", "-y", "2", "-f", "json")
    assert res.exit_code == 0 and len(fake.params) == 4


def test_data_regional_and_gdp_by_industry(fake: FakeBEA, keyed: dict[str, str]) -> None:
    res = run(
        fake,
        "data",
        "Regional",
        "-t",
        "SAINC1",
        "--line",
        "1",
        "--geo",
        "STATE",
        "-y",
        "2",
        "-f",
        "json",
    )
    assert res.exit_code == 0, res.output
    rows = json.loads(res.stdout)
    assert rows[0]["series_id"] == "SAINC1-1:01000" and rows[0]["series_title"] == "Alabama"
    assert rows[0]["code"] == "SAINC1-1" and rows[0]["geo_fips"] == "01000"
    assert rows[0]["unit_mult"] == 3 and rows[0]["frequency"] == "annual"
    assert fake.params[0]["GeoFips"] == "STATE" and fake.params[0]["LineCode"] == "1"
    res = run(
        fake,
        "data",
        "gdpbyindustry",
        "-t",
        "1",
        "-F",
        "Q",
        "-s",
        "2024-Q4",
        "-e",
        "2024",
        "-f",
        "json",
    )
    assert res.exit_code == 0, res.output
    rows = json.loads(res.stdout)
    assert [r["series_id"] for r in rows] == ["1:11", "1:21"]
    assert rows[0]["period"] == "2024Q4" and rows[0]["frequency_code"] == "Q"
    assert rows[0]["series_title"].startswith("Agriculture") and rows[0]["industry"] == "11"
    assert fake.params[-1]["Industry"] == "ALL"  # default injected
    res = run(
        fake,
        "data",
        "ITA",
        "Indicator=BalGds",
        "AreaOrCountry=AllCountries",
        "-F",
        "QSA",
        "-y",
        "1",
        "-f",
        "json",
    )
    assert res.exit_code == 0, res.output
    rows = json.loads(res.stdout)
    assert rows[0]["series_id"] == "BalGds_AllCountries_QSA" and rows[0]["frequency"] == "quarterly"
    assert rows[0]["frequency_code"] == "QSA" and "year" in rows[0] and "api_year" not in rows[0]


def test_data_regional_multiple_tables_strict(fake: FakeBEA, keyed: dict[str, str]) -> None:
    # Regional rows carry no TableName column; emptiness must be judged per request, not per row.
    res = run(
        fake,
        "data",
        "Regional",
        "-t",
        "SAINC1",
        "-t",
        "SQINC1",
        "-l",
        "1",
        "-g",
        "06000",
        "-y",
        "2",
        "--strict",
        "-f",
        "json",
    )
    assert res.exit_code == 0, res.output
    assert "no observations" not in res.stderr
    rows = json.loads(res.stdout)
    assert {r["series_id"] for r in rows} == {"SAINC1-1:06000", "SQINC1-1:06000"}
    # a quarterly-only bound empties the annual table but not the quarterly one
    res = run(
        fake,
        "data",
        "Regional",
        "-t",
        "SAINC1",
        "-t",
        "SQINC1",
        "-l",
        "1",
        "-g",
        "06000",
        "-s",
        f"{THIS_YEAR}-Q1",
        "--strict",
        "-f",
        "json",
    )
    assert res.exit_code == 6 and "SAINC1" in res.stderr and "SQINC1" not in res.stderr


def test_data_year_passthrough(fake: FakeBEA, keyed: dict[str, str]) -> None:
    res = run(fake, "data", "NIPA", "-t", "T10101", "-F", "A", "Year=all", "-f", "json")
    assert res.exit_code == 0, res.output
    assert fake.params[0]["Year"] == "X"
    res = run(
        fake,
        "data",
        "Regional",
        "-t",
        "SAINC1",
        "-l",
        "2",
        "-g",
        "06000",
        "Year=LAST5",
        "-f",
        "json",
    )
    assert res.exit_code == 0, res.output
    assert (
        fake.params[-1]["Year"] == "LAST5" and len(json.loads(res.stdout)) == 4
    )  # no annual value yet this year
    res = run(fake, "data", "NIPA", "-t", "T10101", "-F", "A", "Year=2020", "--years", "1")
    assert res.exit_code == 2


def test_data_usage_errors(fake: FakeBEA, keyed: dict[str, str]) -> None:
    assert run(fake, "data").exit_code == 2
    res = run(fake, "data", "NIPA", "-t", "T10101")
    assert res.exit_code == 2 and "Frequency" in res.output
    assert run(fake, "data", "NIPA", "-F", "Q").exit_code == 2
    assert (
        run(
            fake, "data", "NIPA", "-t", "T10101", "-F", "Q", "--years", "2", "--start", "2020"
        ).exit_code
        == 2
    )
    assert (
        run(
            fake, "data", "NIPA", "-t", "T10101", "-F", "Q", "--start", "2021", "--end", "2020"
        ).exit_code
        == 2
    )
    assert run(fake, "data", "NIPA", "-t", "T10101", "-F", "Q", "--start", "20x1").exit_code == 2
    assert (
        run(fake, "data", "NIPA", "-t", "T10101", "-F", "Q", "--latest", "--years", "1").exit_code
        == 2
    )
    assert (
        run(fake, "data", "NIPA", "-t", "T10101", "-F", "Q", "--layout", "diagonal").exit_code == 2
    )
    assert run(fake, "data", "NIPA", "T10101").exit_code == 2  # not NAME=VALUE
    assert run(fake, "data", "NIPA", "-t", "T10101", "TableName=T10105", "-F", "Q").exit_code == 2
    assert run(fake, "data", "ITA", "-t", "T10101").exit_code == 2  # no tables in ITA
    res = run(fake, "data", "NIPA", "-t", "T10101", "-F", "Q", "--latest", "--columns", "nope")
    assert res.exit_code == 2 and "unknown column" in res.output
    assert fake.params == [] or all(p["method"] != "GetData" for p in fake.params[:-1])


def test_data_strict_and_warnings(fake: FakeBEA, keyed: dict[str, str]) -> None:
    res = run(
        fake, "data", "NIPA", "-t", "T20600", "-F", "Q", "-y", "1", "-f", "json"
    )  # table has no quarterly data
    assert res.exit_code == 0 and json.loads(res.stdout) == []
    assert "no observations returned for NIPA table T20600" in res.stderr
    res = run(fake, "data", "NIPA", "-t", "T20600", "-F", "Q", "-y", "1", "--strict", "-f", "json")
    assert res.exit_code == 6 and "T20600" in res.stderr
    res = run(fake, "-q", "data", "NIPA", "-t", "T20600", "-F", "Q", "-y", "1", "-f", "json")
    assert res.exit_code == 0 and res.stderr == ""
    res = run(
        fake,
        "data",
        "ITA",
        "Indicator=BalGds",
        "-F",
        "A",
        "--start",
        str(THIS_YEAR),
        "--strict",
        "-f",
        "json",
    )
    assert res.exit_code == 6 and "no observations returned for ITA" in res.stderr


def test_exit_codes_from_api(fake: FakeBEA, keyed: dict[str, str]) -> None:
    fake.error_override = {
        "APIErrorCode": "1",
        "APIErrorDescription": "The UserId has exceeded the limit of 100 requests per minute",
    }
    res = run(fake, "data", "NIPA", "-t", "T10101", "-F", "Q", "--latest")
    assert res.exit_code == 4 and "dismal bea: error:" in res.stderr and "hint" in res.stderr
    fake.error_override = {"APIErrorCode": "40", "APIErrorDescription": "Invalid parameter"}
    assert run(fake, "data", "NIPA", "-t", "T10101", "-F", "Q", "--latest").exit_code == 3
    fake.error_override = None
    assert run(fake, "data", "NIPA", "-t", "NOPE", "-F", "Q", "--latest").exit_code == 3
    fake.http_status_override = 503
    res = run(
        fake, "data", "NIPA", "-t", "T10101", "-F", "Q", "--latest", env={"BEA_MAX_RETRIES": "0"}
    )
    assert res.exit_code == 3
    fake.http_status_override = 429
    res = run(
        fake, "data", "NIPA", "-t", "T10101", "-F", "Q", "--latest", env={"BEA_MAX_RETRIES": "0"}
    )
    assert res.exit_code == 4


def test_key_handling(fake: FakeBEA, cache_dir: Path) -> None:
    res = run(fake, "latest", "NIPA", "-t", "T10101", "-F", "Q", "-f", "json")
    assert res.exit_code == 7 and "BEA_API_KEY is not set" in res.stderr and fake.requests == []
    res = run(
        fake,
        "latest",
        "NIPA",
        "-t",
        "T10101",
        "-F",
        "Q",
        "-f",
        "json",
        env={"BEA_API_KEY": "bogus"},
    )
    assert res.exit_code == 7 and "UserId" in res.stderr and "BEA_API_KEY" in res.stderr


def test_bea_format_env(fake: FakeBEA, keyed: dict[str, str]) -> None:
    res = run(fake, "latest", "NIPA", "-t", "T10101", "-F", "Q", env={"BEA_FORMAT": "csv"})
    assert res.exit_code == 0 and res.stdout.startswith("dataset,series_id,")
    res = run(fake, "latest", "NIPA", "-t", "T10101", "-F", "Q", env={"BEA_FORMAT": "xml"})
    assert res.exit_code == 2


def test_table_format(fake: FakeBEA, keyed: dict[str, str]) -> None:
    res = run(fake, "latest", "NIPA", "-t", "T10101", "-F", "Q", "-f", "table")
    assert res.exit_code == 0 and "A191RL" in res.stdout and "series_id" in res.stdout


def test_search_commands(fake: FakeBEA, cache_dir: Path) -> None:
    res = run(fake, "search", "real", "gdp", "-n", "2", "-f", "json")
    assert res.exit_code == 0
    hits = json.loads(res.stdout)
    assert (
        len(hits) == 2
        and hits[0]["id"] == "T10101"
        and hits[0]["command"].startswith("dismal bea data NIPA")
    )
    res = run(fake, "search", "regional", "-k", "all", "-f", "json")
    kinds = {h["kind"] for h in json.loads(res.stdout)}
    assert kinds == {"table", "dataset"}
    res = run(fake, "search", "personal income", "-d", "Regional", "-f", "json")
    assert {h["dataset"] for h in json.loads(res.stdout)} == {"Regional"}
    res = run(fake, "search", "qqqqzzzz", "-f", "json")
    assert res.exit_code == 0 and json.loads(res.stdout) == [] and "no matches" in res.stderr
    assert run(fake, "search", "x", "-k", "bogus").exit_code == 2
    assert fake.requests == []  # fully offline


def test_datasets_offline_refresh_and_show(
    fake: FakeBEA, keyed: dict[str, str], cache_dir: Path
) -> None:
    res = run(fake, "datasets", "-f", "json")
    assert res.exit_code == 0 and len(json.loads(res.stdout)) == 13 and fake.requests == []
    res = run(fake, "datasets", "--refresh", "-f", "json")
    assert res.exit_code == 0
    assert [d["dataset"] for d in json.loads(res.stdout)] == [
        "NIPA",
        "Regional",
        "GDPbyIndustry",
        "ITA",
    ]
    assert (cache_dir / "datasets.json").is_file()
    res = run(fake, "datasets", "-f", "json")  # now served from the cache
    assert [d["dataset"] for d in json.loads(res.stdout)] == [
        "NIPA",
        "Regional",
        "GDPbyIndustry",
        "ITA",
    ]
    res = run(fake, "datasets", "-q", "industry", "-f", "json")
    assert json.loads(res.stdout)[0]["dataset"] == "GDPbyIndustry"
    res = run(fake, "datasets", "show", "nipa", "-f", "json")
    assert res.exit_code == 0, res.output
    params = json.loads(res.stdout)
    assert [p["parameter"] for p in params] == ["TableName", "Frequency", "Year", "ShowMillions"]
    assert (
        params[1]["required"] is True
        and params[1]["multiple"] is True
        and params[3]["required"] is False
    )
    n = len(fake.requests)
    assert (
        run(fake, "datasets", "show", "NIPA", "-f", "json").exit_code == 0
        and len(fake.requests) == n
    )
    assert run(fake, "datasets", "show", "ZZ").exit_code == 3


def test_tables_list_and_show(fake: FakeBEA, keyed: dict[str, str], cache_dir: Path) -> None:
    res = run(fake, "tables", "list", "NIPA", "-f", "json")
    assert res.exit_code == 0, res.output
    rows = json.loads(res.stdout)
    assert [r["table"] for r in rows] == ["T10101", "T10105", "T20600"]
    assert rows[0]["title"].startswith("Table 1.1.1")
    res = run(
        fake, "tables", "list", "nipa", "-q", "monthly", "-f", "json", "--columns", "table,score"
    )
    rows = json.loads(res.stdout)
    assert rows == [{"table": "T20600", "score": rows[0]["score"]}]
    n = len(fake.requests)
    run(fake, "tables", "list", "NIPA", "-f", "json")
    assert len(fake.requests) == n  # cached
    run(fake, "tables", "list", "NIPA", "--refresh", "-f", "json")
    assert len(fake.requests) == n + 1
    assert run(fake, "tables", "list", "ITA").exit_code == 2
    res = run(fake, "tables", "show", "NIPA", "T10101", "-f", "json")
    assert res.exit_code == 0, res.output
    rows = json.loads(res.stdout)
    assert [r["series_id"] for r in rows] == ["A191RL", "DPCERL", "DGDSRL"]
    assert (
        rows[0]["frequencies"] == "A,Q"
        and rows[0]["latest_period"] == f"{THIS_YEAR}Q{LAST_QUARTER}"
    )
    assert rows[0]["line_number"] == 1 and rows[0]["latest_value"] is not None
    assert fake.params[-1]["Frequency"] == "A,Q,M"
    res = run(fake, "tables", "show", "Regional", "SAINC1", "-f", "json")
    assert res.exit_code == 0, res.output
    assert [r["line_code"] for r in json.loads(res.stdout)] == ["1", "2", "3"]
    assert (
        fake.params[-1]["method"] == "GetParameterValuesFiltered"
        and fake.params[-1]["TableName"] == "SAINC1"
    )
    assert run(fake, "tables", "show", "ITA", "X").exit_code == 2
    res = run(fake, "tables", "show", "GDPbyIndustry", "1", "-f", "json")
    assert res.exit_code == 0 and [r["series_id"] for r in json.loads(res.stdout)] == [
        "1:11",
        "1:21",
    ]


def test_values(fake: FakeBEA, keyed: dict[str, str], cache_dir: Path) -> None:
    res = run(fake, "values", "Regional", "GeoFips", "-f", "json")
    assert res.exit_code == 0, res.output
    rows = json.loads(res.stdout)
    assert rows[0] == {"key": "00000", "description": "United States"}
    res = run(fake, "values", "regional", "geofips", "-q", "californa", "-f", "json")
    assert [r["key"] for r in json.loads(res.stdout)] == ["06000"]
    res = run(fake, "values", "Regional", "LineCode", "--filter", "TableName=SQINC1", "-f", "json")
    assert res.exit_code == 0, res.output
    assert json.loads(res.stdout) == [
        {"key": "1", "description": "[SQINC1] Personal income (millions of dollars, SAAR)"}
    ]
    res = run(fake, "values", "NIPA", "Year", "-F", "TableName=T10101", "-f", "json")
    assert json.loads(res.stdout)[0]["FirstAnnualYear"] == "2015"
    assert run(fake, "values", "NIPA", "Nope").exit_code == 3
    assert run(fake, "values", "NIPA", "Year", "--filter", "bad").exit_code == 2
    res = run(fake, "values", "NIPA", "TableName", "-q", "zzzz", "-f", "json")
    assert json.loads(res.stdout) == [] and "no values matched" in res.stderr


def test_config_doctor_cache(fake: FakeBEA, keyed: dict[str, str], cache_dir: Path) -> None:
    res = run(fake, "config")
    assert res.exit_code == 0
    cfg = json.loads(res.stdout)
    assert cfg["api_key"].endswith("5678") and cfg["api_key"].startswith("****")
    assert VALID_KEY not in res.stdout and cfg["limits"]["requests_per_minute"] == 100
    res = run(fake, "doctor")
    assert res.exit_code == 0, res.output
    report = json.loads(res.stdout)
    assert report["healthy"] is True and report["checks"][1]["detail"] == "4 datasets listed"
    fake.http_status_override = 500
    res = run(fake, "doctor", env={"BEA_MAX_RETRIES": "0"})
    assert res.exit_code == 3 and json.loads(res.stdout)["healthy"] is False
    fake.http_status_override = None
    res = run(fake, "doctor", env={"BEA_API_KEY": "short"})
    assert res.exit_code == 7 and "36" in json.loads(res.stdout)["checks"][0]["detail"]
    (cache_dir / "values").mkdir(parents=True)
    (cache_dir / "values" / "NIPA.TableName.json").write_text("[]")
    res = run(fake, "cache", "info", "-f", "json")
    assert json.loads(res.stdout)[0]["file"] == "values/NIPA.TableName.json"
    res = run(fake, "cache", "clear")
    assert res.exit_code == 0 and "removed 1" in res.stderr
    assert not (cache_dir / "values" / "NIPA.TableName.json").exists()


def test_doctor_without_key(fake: FakeBEA, cache_dir: Path) -> None:
    res = run(fake, "doctor")
    assert res.exit_code == 7
    report = json.loads(res.stdout)
    assert report["healthy"] is False and report["checks"][0]["ok"] is False
    assert fake.requests == []


def test_bad_env_value_is_usage_error(fake: FakeBEA) -> None:
    res = run(fake, "config", env={"BEA_TIMEOUT": "slow"})
    assert res.exit_code == 2


def test_latest_monthly(fake: FakeBEA, keyed: dict[str, str]) -> None:
    res = run(fake, "latest", "NIPA", "-t", "T20600", "-F", "M", "-f", "json")
    rows = json.loads(res.stdout)
    assert (
        rows[0]["period"] == f"{THIS_YEAR}M{LAST_MONTH:02d}" and rows[0]["frequency"] == "monthly"
    )
