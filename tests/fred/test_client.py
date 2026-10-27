from __future__ import annotations

from collections.abc import Callable
from datetime import date

import httpx
import pytest

from dismal.fred.client import LIMITS, FREDClient
from dismal.fred.errors import (
    FREDAPIError,
    FREDConfigError,
    FREDHTTPError,
    FREDNetworkError,
    FREDNotFoundError,
    FREDQuotaError,
)
from tests.fred.conftest import THIS_YEAR, TODAY, FakeFRED


def test_limits(make_client: Callable[..., FREDClient]) -> None:
    assert make_client().limits == LIMITS and LIMITS.requests_per_minute == 120


def test_observations_and_pagination(
    fake: FakeFRED, make_client: Callable[..., FREDClient]
) -> None:
    client = make_client()
    rows, meta = client.observations("unrate", start=date(2023, 1, 1), end=date(2023, 12, 31))
    assert len(rows) == 12 and rows[0].date == date(2023, 1, 1) and meta["count"] == 12
    assert fake.params[0]["series_id"] == "UNRATE" and fake.params[0]["limit"] == "100000"
    fake.max_limit = 5  # the server returns at most 5 rows per page
    rows, meta = client.observations("UNRATE", start=date(2023, 1, 1), end=date(2023, 12, 31))
    assert len(rows) == 12 and [p["offset"] for p in fake.params[-3:]] == ["0", "5", "10"]
    rows, _ = client.observations("UNRATE", sort_order="desc", limit=1)
    assert len(rows) == 1 and rows[0].date.year == THIS_YEAR and fake.params[-1]["limit"] == "1"


def test_fetch_merges_and_reports_unknown(
    fake: FakeFRED, make_client: Callable[..., FREDClient]
) -> None:
    seen: list[str] = []
    client = make_client(on_message=seen.append)
    resp = client.fetch(
        ["unrate", "NOPE", "UNRATE", "gdp"],
        start=date(2024, 1, 1),
        end=date(2024, 6, 30),
        meta=True,
    )
    assert [s.series_id for s in resp.series] == ["UNRATE", "GDP"]
    assert resp.request_count == 5  # 3 observation calls + 2 metadata calls
    assert seen == ["series NOPE does not exist (Bad Request.  The series does not exist.)"]
    assert resp.get("UNRATE") is not None and resp.get("UNRATE").title == "Unemployment Rate"
    assert [o.date for o in resp.get("GDP").data] == [date(2024, 1, 1), date(2024, 4, 1)]
    assert resp.params == {"observation_start": "2024-01-01", "observation_end": "2024-06-30"}
    raw = resp.to_api_dict()
    assert (
        raw["series"][0]["count"] == 6 and raw["series"][0]["info"]["title"] == "Unemployment Rate"
    )
    assert "api_key" not in str(raw)


def test_fetch_options(fake: FakeFRED, make_client: Callable[..., FREDClient]) -> None:
    client = make_client()
    resp = client.fetch(
        ["DGS10"],
        frequency="m",
        aggregation="avg",
        units="pch",
        as_of=date(2024, 3, 1),
        latest=True,
    )
    p = fake.params[-1]
    assert p["frequency"] == "m" and p["aggregation_method"] == "avg" and p["units"] == "pch"
    assert p["realtime_start"] == "2024-03-01" and p["sort_order"] == "desc" and p["limit"] == "1"
    obs = resp.series[0].data[0]
    assert obs.realtime_start == date(2024, 3, 1) and obs.date <= date(2024, 2, 1)
    assert resp.params["realtime_end"] == "2024-03-01"


def test_fetch_validation(make_client: Callable[..., FREDClient]) -> None:
    client = make_client()
    with pytest.raises(ValueError):
        client.fetch([])
    with pytest.raises(ValueError, match="precedes"):
        client.fetch(["UNRATE"], start=date(2021, 1, 1), end=date(2020, 1, 1))
    with pytest.raises(ValueError, match="frequency"):
        client.fetch(["UNRATE"], aggregation="sum")


def test_missing_values_and_series_info(
    fake: FakeFRED, make_client: Callable[..., FREDClient]
) -> None:
    client = make_client()
    rows, _ = client.observations("DGS10", start=date(2024, 1, 1), end=date(2024, 1, 5))
    assert rows[0].date == date(2024, 1, 1) and rows[0].value is None and rows[0].raw_value == "."
    assert rows[1].value is not None
    info = client.series_info("gdp")
    assert info.id == "GDP" and info.frequency_short == "Q" and info.popularity == 92
    assert info.observation_end == date(THIS_YEAR, 4, 1) and info.to_record()["units"].startswith(
        "Billions"
    )
    with pytest.raises(FREDNotFoundError):
        client.series_info("NOPE")


def test_api_errors(fake: FakeFRED, make_client: Callable[..., FREDClient]) -> None:
    with pytest.raises(FREDConfigError) as cexc:
        make_client("wrong").sources()
    assert cexc.value.exit_code == 7 and "FRED_API_KEY" in (cexc.value.hint or "")
    fake.require_key = True
    with pytest.raises(FREDConfigError):
        make_client(None).sources()
    client = make_client()
    with pytest.raises(FREDNotFoundError) as nexc:
        client.observations("NOPE")
    assert nexc.value.exit_code == 3 and nexc.value.status_code == 400
    with pytest.raises(FREDAPIError, match="frequency"):
        client.observations("GDP", frequency="d")
    fake.http_status_override = 429
    with pytest.raises(FREDQuotaError) as qexc:
        make_client(max_retries=0).sources()
    assert qexc.value.exit_code == 4


def test_retries(fake: FakeFRED, make_client: Callable[..., FREDClient]) -> None:
    fake.fail_times = 2
    client = make_client(max_retries=3)
    assert len(client.sources()) == 2 and client.request_count == 3
    fake.fail_times = 5
    with pytest.raises(FREDHTTPError) as exc:
        make_client(max_retries=1).sources()
    assert exc.value.status_code == 500


def test_network_and_payload_errors() -> None:
    def boom(_request: httpx.Request) -> httpx.Response:
        raise httpx.ConnectError("refused")

    client = FREDClient(
        "k", transport=httpx.MockTransport(boom), max_retries=1, sleep=lambda _s: None
    )
    with pytest.raises(FREDNetworkError) as exc:
        client.sources()
    assert exc.value.exit_code == 5 and client.request_count == 2

    def slow(_request: httpx.Request) -> httpx.Response:
        raise httpx.ReadTimeout("slow")

    with pytest.raises(FREDNetworkError, match="timed out"):
        FREDClient("k", transport=httpx.MockTransport(slow), max_retries=0).sources()
    client = FREDClient(
        "k", transport=httpx.MockTransport(lambda _r: httpx.Response(200, text="<html>"))
    )
    with pytest.raises(FREDHTTPError, match="non-JSON"):
        client.sources()
    client = FREDClient(
        "k", transport=httpx.MockTransport(lambda _r: httpx.Response(200, json=[1]))
    )
    with pytest.raises(FREDHTTPError, match="not an object"):
        client.sources()
    client = FREDClient(
        "k", transport=httpx.MockTransport(lambda _r: httpx.Response(400, text="nope"))
    )
    with pytest.raises(FREDAPIError, match="nope"):
        client.sources()
    client = FREDClient(
        "k",
        transport=httpx.MockTransport(lambda _r: httpx.Response(404, json={"error_message": "x"})),
    )
    with pytest.raises(FREDNotFoundError):
        client.sources()
    client = FREDClient(
        "k", transport=httpx.MockTransport(lambda _r: httpx.Response(418, text="teapot"))
    )
    with pytest.raises(FREDHTTPError, match="418"):
        client.sources()


def test_search_vintages_updates(fake: FakeFRED, make_client: Callable[..., FREDClient]) -> None:
    client = make_client()
    hits, count = client.search("gross domestic product", limit=1)
    assert count == 2 and [h.id for h in hits] == ["GDP"]
    hits, _ = client.search("g", search_type="series_id", order_by="series_id", sort_order="asc")
    assert [h.id for h in hits] == ["GDP", "GDPC1"]
    hits, _ = client.search(
        "treasury",
        filter_variable="frequency",
        filter_value="Daily",
        tag_names=["treasury"],
        exclude_tag_names=["bls"],
    )
    assert [h.id for h in hits] == ["DGS10"] and fake.params[-1]["exclude_tag_names"] == "bls"
    assert client.vintage_dates("PAYEMS")[0] == date(2024, 1, 5)
    assert [s.id for s in client.updates(limit=2)] == ["UNRATE", "CPIAUCSL"]


def test_releases_categories_sources(
    fake: FakeFRED, make_client: Callable[..., FREDClient]
) -> None:
    client = make_client()
    rels = client.releases()
    assert [r.id for r in rels] == [10, 18, 50, 53, 180] and rels[0].press_release
    assert client.release(53).name == "Gross Domestic Product"
    with pytest.raises(FREDNotFoundError):
        client.release(999)
    hits, count = client.release_series(50)
    assert count == 2 and [h.id for h in hits] == ["UNRATE", "PAYEMS"]
    dates = client.release_dates(TODAY, TODAY)
    assert len(dates) == 1 and dates[0].release_id == 10 and dates[0].date == TODAY
    assert client.category(10).name.startswith("Population")
    with pytest.raises(FREDNotFoundError):
        client.category(424242)
    assert [c.id for c in client.category_children(0)] == [32991, 10, 32992, 32455]
    hits, count = client.category_series(12)
    assert [h.id for h in hits] == ["UNRATE", "PAYEMS"] and count == 2
    assert [s.id for s in client.sources()] == [1, 22]


def test_no_key_is_not_sent(fake: FakeFRED, make_client: Callable[..., FREDClient]) -> None:
    fake.require_key = False
    make_client(None).sources()
    assert "api_key" not in fake.params[0] and fake.params[0]["file_type"] == "json"
