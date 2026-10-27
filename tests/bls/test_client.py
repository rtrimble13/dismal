from __future__ import annotations

import json
from collections.abc import Callable

import httpx
import pytest

from dismal.bls.client import (
    REGISTERED_LIMITS,
    UNREGISTERED_LIMITS,
    BLSClient,
    chunked,
    year_windows,
)
from dismal.bls.errors import BLSAPIError, BLSHTTPError, BLSNetworkError, BLSQuotaError
from tests.bls.conftest import FakeBLS


def test_limits_depend_on_key(make_client: Callable[..., BLSClient]) -> None:
    assert make_client("k").limits == REGISTERED_LIMITS
    assert make_client(None).limits == UNREGISTERED_LIMITS
    assert make_client("").limits == UNREGISTERED_LIMITS


def test_year_windows_and_chunking() -> None:
    assert list(year_windows(2000, 2024, 20)) == [(2000, 2019), (2020, 2024)]
    assert list(year_windows(2020, 2020, 20)) == [(2020, 2020)]
    assert list(chunked(["a", "b", "c"], 2)) == [["a", "b"], ["c"]]
    with pytest.raises(ValueError, match="precedes"):
        list(year_windows(2024, 2020, 20))


def test_fetch_single_series_sorted_ascending(
    fake: FakeBLS, make_client: Callable[..., BLSClient]
) -> None:
    client = make_client()
    resp = client.fetch(["LNS14000000"], start_year=2023, end_year=2024)
    assert resp.request_count == 1
    s = resp.series[0]
    assert s.series_id == "LNS14000000"
    assert [(o.year, o.period) for o in s.data[:2]] == [(2023, "M01"), (2023, "M02")]
    assert s.data[-1].period == "M12" and s.data[-1].year == 2024
    assert len(s.data) == 24
    payload = fake.payloads[0]
    assert payload["registrationkey"] == "test-key"
    assert payload["startyear"] == "2023" and payload["endyear"] == "2024"
    assert fake.requests[0].headers["content-type"] == "application/json"


def test_fetch_splits_series_and_year_windows(
    fake: FakeBLS, make_client: Callable[..., BLSClient]
) -> None:
    client = make_client()
    ids = [f"FAKE{i:03d}" for i in range(60)] + ["LNS14000000"]
    resp = client.fetch(ids, start_year=1990, end_year=2024)
    # 61 ids -> 2 chunks; 35 years -> 2 windows => 4 requests
    assert resp.request_count == 4
    assert len(fake.payloads) == 4
    series = resp.get("LNS14000000")
    assert series is not None
    assert series.data[0].year == 1990 and series.data[-1].year == 2024
    assert len(series.data) == 35 * 12
    assert len({(o.year, o.period) for o in series.data}) == len(series.data)
    assert any("does not exist" in m for m in resp.messages)


def test_fetch_unregistered_uses_smaller_windows(
    fake: FakeBLS, make_client: Callable[..., BLSClient]
) -> None:
    client = make_client(None)
    client.fetch(["LNS14000000"], start_year=2000, end_year=2024)
    assert [(p["startyear"], p["endyear"]) for p in fake.payloads] == [
        ("2000", "2009"),
        ("2010", "2019"),
        ("2020", "2024"),
    ]
    assert "registrationkey" not in fake.payloads[0]


def test_fetch_flags(fake: FakeBLS, make_client: Callable[..., BLSClient]) -> None:
    client = make_client()
    resp = client.fetch(
        ["LNS14000000"], latest=True, catalog=True, calculations=True, annual_average=True
    )
    payload = fake.payloads[0]
    assert payload["latest"] == "true"
    assert payload["catalog"] == "true"
    assert payload["calculations"] == "true"
    assert payload["annualaverage"] == "true"
    assert "startyear" not in payload
    s = resp.series[0]
    assert len(s.data) == 1 and s.data[0].latest
    assert s.title == "(Seas) Unemployment Rate"
    assert s.data[0].calculations is not None


def test_fetch_messages_callback(fake: FakeBLS, make_client: Callable[..., BLSClient]) -> None:
    seen: list[str] = []
    client = make_client(on_message=seen.append)
    client.fetch(["NOPE123"])
    assert seen == ["Series does not exist for Series NOPE123"]


def test_fetch_validation(make_client: Callable[..., BLSClient]) -> None:
    client = make_client()
    with pytest.raises(ValueError):
        client.fetch([])
    with pytest.raises(ValueError):
        client.fetch(["X"], start_year=2020)
    with pytest.raises(ValueError):
        client.fetch(["X"], start_year=2021, end_year=2020)


def test_api_error_statuses(fake: FakeBLS, make_client: Callable[..., BLSClient]) -> None:
    client = make_client()
    fake.status_override = "REQUEST_FAILED_INVALID_PARAMETERS"
    fake.messages_override = ["Bad series"]
    with pytest.raises(BLSAPIError) as exc:
        client.fetch(["LNS14000000"])
    assert exc.value.exit_code == 3 and "Bad series" in str(exc.value)

    fake.status_override = "REQUEST_NOT_PROCESSED"
    fake.messages_override = ["daily threshold of 500 requests has been exceeded"]
    with pytest.raises(BLSQuotaError) as qexc:
        client.fetch(["LNS14000000"])
    assert qexc.value.exit_code == 4


def test_retries_then_succeeds(fake: FakeBLS, make_client: Callable[..., BLSClient]) -> None:
    fake.fail_times = 2
    client = make_client(max_retries=3)
    resp = client.fetch(["LNS14000000"], latest=True)
    assert resp.series and client.request_count == 3


def test_retries_exhausted_raise_http_error(
    fake: FakeBLS, make_client: Callable[..., BLSClient]
) -> None:
    fake.fail_times = 5
    client = make_client(max_retries=1)
    with pytest.raises(BLSHTTPError) as exc:
        client.fetch(["LNS14000000"], latest=True)
    assert exc.value.status_code == 500


def test_http_429_is_quota(fake: FakeBLS, make_client: Callable[..., BLSClient]) -> None:
    fake.http_status_override = 429
    client = make_client(max_retries=0)
    with pytest.raises(BLSQuotaError):
        client.fetch(["LNS14000000"], latest=True)


def test_network_error() -> None:
    def boom(_request: httpx.Request) -> httpx.Response:
        raise httpx.ConnectError("refused")

    client = BLSClient(
        "k", transport=httpx.MockTransport(boom), max_retries=1, sleep=lambda _s: None
    )
    with pytest.raises(BLSNetworkError) as exc:
        client.fetch(["LNS14000000"], latest=True)
    assert exc.value.exit_code == 5
    assert client.request_count == 2


def test_non_json_response(make_client: Callable[..., BLSClient]) -> None:
    client = BLSClient(
        "k", transport=httpx.MockTransport(lambda _r: httpx.Response(200, text="<html>"))
    )
    with pytest.raises(BLSHTTPError, match="non-JSON"):
        client.surveys()


def test_surveys_survey_popular(fake: FakeBLS, make_client: Callable[..., BLSClient]) -> None:
    client = make_client()
    surveys = client.surveys()
    assert [s.abbreviation for s in surveys] == ["CU", "LN", "CE"]
    assert fake.requests[-1].url.params["registrationkey"] == "test-key"
    detail = client.survey("cu")
    assert detail["survey_abbreviation"] == "CU"
    assert client.popular() == ["LNS14000000", "CUUR0000SA0", "CES0000000001"]
    assert client.popular("cu") == ["CUUR0000SA0", "CUSR0000SA0"]
    assert fake.requests[-1].url.params["survey"] == "CU"
    with pytest.raises(BLSAPIError):
        client.survey("ZZ")


def test_payload_is_valid_json_body(fake: FakeBLS, make_client: Callable[..., BLSClient]) -> None:
    make_client().fetch(["lns14000000", "LNS14000000"], latest=True)
    body = json.loads(fake.requests[0].content)
    assert body["seriesid"] == ["LNS14000000"]  # normalised and de-duplicated
