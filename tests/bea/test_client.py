from __future__ import annotations

from collections.abc import Callable

import httpx
import pytest

from dismal.bea.client import LIMITS, BEAClient, _as_list
from dismal.bea.errors import (
    BEAAPIError,
    BEAConfigError,
    BEAHTTPError,
    BEANetworkError,
    BEAQuotaError,
)
from tests.bea.conftest import THIS_YEAR, FakeBEA


def test_limits_are_static(make_client: Callable[..., BEAClient]) -> None:
    assert make_client("k").limits == LIMITS
    assert LIMITS.requests_per_minute == 100 and LIMITS.block_minutes == 60


def test_as_list_handles_single_objects() -> None:
    assert _as_list(None) == [] and _as_list("") == []
    assert _as_list({"a": 1}) == [{"a": 1}]
    assert _as_list([1, 2]) == [1, 2]


def test_get_data_single_table_sorted_ascending(
    fake: FakeBEA, make_client: Callable[..., BEAClient]
) -> None:
    client = make_client()
    resp = client.get_data("nipa", {"TableName": "T10101", "Frequency": "Q,A", "Year": "2023,2024"})
    assert resp.request_count == 1 and resp.dataset == "NIPA"
    s = resp.series[0]
    assert s.series_id == "A191RL" and s.title == "Gross domestic product"
    assert [o.period for o in s.data] == [
        "2023Q1",
        "2023Q2",
        "2023Q3",
        "2023Q4",
        "2023",
        "2024Q1",
        "2024Q2",
        "2024Q3",
        "2024Q4",
        "2024",
    ]
    assert s.attributes == {
        "table_name": "T10101",
        "line_number": 1,
        "metric_name": "Fisher Quantity Index",
    }
    assert s.data[0].value == pytest.approx(float(s.data[0].raw_value))
    assert resp.notes[0].ref == "T10101" and "LastRevised" in resp.note_text("T10101")
    sent = fake.params[0]
    assert sent["UserID"] == "test-key" and sent["ResultFormat"] == "JSON"
    assert sent["datasetname"] == "NIPA" and sent["method"] == "GetData"
    assert fake.requests[0].method == "GET" and fake.requests[0].url.path == "/api/data"


def test_fetch_merges_tables(fake: FakeBEA, make_client: Callable[..., BEAClient]) -> None:
    client = make_client()
    resp = client.fetch(
        "NIPA",
        {"Frequency": "A", "Year": "2022"},
        table_param="TableName",
        tables=["T10101", "T10105", "T10101"],
    )
    assert resp.request_count == 2 and len(fake.params) == 2
    assert [s.series_id for s in resp.series] == ["A191RL", "DPCERL", "DGDSRL", "A191RC", "DPCERC"]
    assert {n.ref for n in resp.notes} == {"T10101", "T10105"}
    assert resp.params["TableName"] == "T10101,T10105"
    assert resp.series_tables["A191RL"] == {"T10101"} and resp.series_tables["DPCERC"] == {"T10105"}
    raw = resp.to_api_dict()
    assert "UserID" not in str(raw["BEAAPI"]["Request"])
    assert len(raw["BEAAPI"]["Results"]["Data"]) == 5
    with pytest.raises(ValueError, match="table_param"):
        client.fetch("NIPA", {}, tables=["T10101"])


def test_fetch_without_tables(fake: FakeBEA, make_client: Callable[..., BEAClient]) -> None:
    resp = make_client().fetch("ITA", {"Indicator": "BalGds", "Frequency": "A", "Year": "2022"})
    assert resp.request_count == 1 and resp.series[0].series_id == "BalGds_AllCountries_A"


def test_api_errors(fake: FakeBEA, make_client: Callable[..., BEAClient]) -> None:
    client = make_client()
    with pytest.raises(BEAAPIError) as exc:
        client.get_data("NIPA", {"TableName": "T10101"})
    assert exc.value.exit_code == 3 and exc.value.code == "40" and "frequency" in str(exc.value)
    fake.error_override = {
        "APIErrorCode": "1",
        "APIErrorDescription": "Request throttled: too many requests",
    }
    with pytest.raises(BEAQuotaError) as qexc:
        client.datasets()
    assert qexc.value.exit_code == 4
    fake.error_override = {
        "APIErrorCode": "3",
        "APIErrorDescription": "The UserId provided is not valid",
        "ErrorDetail": {"Description": "unregistered"},
    }
    with pytest.raises(BEAConfigError) as cexc:
        client.datasets()
    assert cexc.value.exit_code == 7 and "unregistered" in cexc.value.message


def test_invalid_key_is_config_error(fake: FakeBEA, make_client: Callable[..., BEAClient]) -> None:
    with pytest.raises(BEAConfigError):
        make_client("wrong").datasets()


def test_retries_then_succeeds(fake: FakeBEA, make_client: Callable[..., BEAClient]) -> None:
    fake.fail_times = 2
    client = make_client(max_retries=3)
    assert len(client.datasets()) == 4 and client.request_count == 3


def test_retries_exhausted_raise_http_error(
    fake: FakeBEA, make_client: Callable[..., BEAClient]
) -> None:
    fake.fail_times = 5
    client = make_client(max_retries=1)
    with pytest.raises(BEAHTTPError) as exc:
        client.datasets()
    assert exc.value.status_code == 500


def test_http_429_is_quota(fake: FakeBEA, make_client: Callable[..., BEAClient]) -> None:
    fake.http_status_override = 429
    with pytest.raises(BEAQuotaError):
        make_client(max_retries=0).datasets()


def test_network_error() -> None:
    def boom(_request: httpx.Request) -> httpx.Response:
        raise httpx.ConnectError("refused")

    client = BEAClient(
        "k", transport=httpx.MockTransport(boom), max_retries=1, sleep=lambda _s: None
    )
    with pytest.raises(BEANetworkError) as exc:
        client.datasets()
    assert exc.value.exit_code == 5 and client.request_count == 2


def test_timeout_error() -> None:
    def slow(_request: httpx.Request) -> httpx.Response:
        raise httpx.ReadTimeout("slow")

    client = BEAClient("k", transport=httpx.MockTransport(slow), max_retries=0)
    with pytest.raises(BEANetworkError, match="timed out"):
        client.datasets()


def test_non_json_and_odd_payloads() -> None:
    client = BEAClient(
        "k", transport=httpx.MockTransport(lambda _r: httpx.Response(200, text="<html>"))
    )
    with pytest.raises(BEAHTTPError, match="non-JSON"):
        client.datasets()
    client = BEAClient("k", transport=httpx.MockTransport(lambda _r: httpx.Response(200, json=[1])))
    with pytest.raises(BEAHTTPError, match="not an object"):
        client.datasets()
    listed = {
        "BEAAPI": {
            "Results": [{"Error": {"APIErrorCode": "9", "APIErrorDescription": "listed error"}}]
        }
    }
    client = BEAClient(
        "k", transport=httpx.MockTransport(lambda _r: httpx.Response(200, json=listed))
    )
    with pytest.raises(BEAAPIError, match="listed error"):
        client.datasets()
    nested = {
        "BEAAPI": {"Results": {"Error": {"APIErrorCode": "8", "APIErrorDescription": "nested"}}}
    }
    client = BEAClient(
        "k", transport=httpx.MockTransport(lambda _r: httpx.Response(200, json=nested))
    )
    with pytest.raises(BEAAPIError, match="nested"):
        client.datasets()
    bare = {"Results": {"Dataset": {"DatasetName": "X", "DatasetDescription": "only one"}}}
    client = BEAClient(
        "k", transport=httpx.MockTransport(lambda _r: httpx.Response(200, json=bare))
    )
    assert [d.name for d in client.datasets()] == ["X"]


def test_datasets_parameters_values(fake: FakeBEA, make_client: Callable[..., BEAClient]) -> None:
    client = make_client()
    assert [d.name for d in client.datasets()] == ["NIPA", "Regional", "GDPbyIndustry", "ITA"]
    params = client.parameters("regional")
    assert [p.name for p in params] == ["TableName", "LineCode", "GeoFips", "Year"]
    assert params[2].multiple and not params[3].required and params[3].all_value == "ALL"
    assert fake.params[-1]["datasetname"] == "Regional"
    values = client.parameter_values("NIPA", "Frequency")
    assert values[0] == {"FrequencyID": "A", "Description": "Annual"}
    single = client.parameter_values_filtered("Regional", "LineCode", {"TableName": "SQINC1"})
    assert single == [{"Key": "1", "Desc": "[SQINC1] Personal income (millions of dollars, SAAR)"}]
    assert fake.params[-1]["TargetParameter"] == "LineCode"
    with pytest.raises(BEAAPIError):
        client.parameters("ZZ")


def test_no_key_is_not_sent(fake: FakeBEA, make_client: Callable[..., BEAClient]) -> None:
    fake.require_key = False
    make_client(None).datasets()
    assert "UserID" not in fake.params[0]


def test_current_year_rows_present(fake: FakeBEA, make_client: Callable[..., BEAClient]) -> None:
    resp = make_client().get_data(
        "NIPA", {"TableName": "T10101", "Frequency": "Q", "Year": str(THIS_YEAR)}
    )
    assert resp.series[0].latest is not None and resp.series[0].latest.year == THIS_YEAR
