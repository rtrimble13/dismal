"""Shared fixtures: a fake BLS API served through ``httpx.MockTransport``."""

from __future__ import annotations

import json
from collections.abc import Callable, Iterator
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import httpx
import pytest

from dismal.bls.client import BLSClient

MONTHS = [
    "January",
    "February",
    "March",
    "April",
    "May",
    "June",
    "July",
    "August",
    "September",
    "October",
    "November",
    "December",
]

SURVEYS = [
    {"survey_abbreviation": "CU", "survey_name": "Consumer Price Index - All Urban Consumers"},
    {
        "survey_abbreviation": "LN",
        "survey_name": "Labor Force Statistics from the Current Population Survey",
    },
    {"survey_abbreviation": "CE", "survey_name": "Employment, Hours, and Earnings - National"},
]

POPULAR = {
    None: ["LNS14000000", "CUUR0000SA0", "CES0000000001"],
    "CU": ["CUUR0000SA0", "CUSR0000SA0"],
}

THIS_YEAR = datetime.now(tz=timezone.utc).year
_ORD = {1: "st", 2: "nd", 3: "rd", 4: "th"}

# Series the fake API knows about -> (frequency, first year, last year, latest period index)
KNOWN_SERIES: dict[str, dict[str, Any]] = {
    "LNS14000000": {
        "freq": "M",
        "first": 1948,
        "last": THIS_YEAR,
        "last_period": 9,
        "title": "(Seas) Unemployment Rate",
        "survey": "LN",
    },
    "CUUR0000SA0": {
        "freq": "M",
        "first": 1913,
        "last": THIS_YEAR,
        "last_period": 9,
        "title": "All items in U.S. city average, all urban consumers, not seasonally adjusted",
        "survey": "CU",
    },
    "CUSR0000SA0": {
        "freq": "M",
        "first": 1947,
        "last": THIS_YEAR,
        "last_period": 9,
        "title": "All items in U.S. city average, all urban consumers, seasonally adjusted",
        "survey": "CU",
    },
    "CES0000000001": {
        "freq": "M",
        "first": 1939,
        "last": THIS_YEAR,
        "last_period": 9,
        "title": "All employees, thousands, total nonfarm, seasonally adjusted",
        "survey": "CE",
    },
    "PRS85006092": {
        "freq": "Q",
        "first": 1947,
        "last": THIS_YEAR,
        "last_period": 2,
        "title": "Nonfarm Business Sector: Labor Productivity",
        "survey": "PR",
    },
    "CIU1010000000000A": {
        "freq": "Q",
        "first": 2001,
        "last": THIS_YEAR,
        "last_period": 2,
        "title": "ECI total compensation",
        "survey": "CI",
    },
    "ANNUAL0001": {
        "freq": "A",
        "first": 2000,
        "last": THIS_YEAR - 1,
        "last_period": 1,
        "title": "Annual thing",
        "survey": "ZZ",
    },
}


def _value(series_id: str, year: int, idx: int) -> str:
    base = sum(ord(c) for c in series_id) % 97
    return f"{base + (year - 2000) * 1.5 + idx * 0.1:.1f}"


def _observations(
    series_id: str, start: int, end: int, *, latest: bool, annual_average: bool, calculations: bool
) -> list[dict[str, Any]]:
    meta = KNOWN_SERIES[series_id]
    freq = meta["freq"]
    rows: list[dict[str, Any]] = []
    years = range(max(start, meta["first"]), min(end, meta["last"]) + 1)
    for year in sorted(years, reverse=True):  # BLS returns newest first
        if freq == "M":
            n = meta["last_period"] if year == meta["last"] else 12
            periods = [(f"M{i:02d}", MONTHS[i - 1], i) for i in range(n, 0, -1)]
            if annual_average and year != meta["last"]:
                periods.insert(0, ("M13", "Annual", 13))
        elif freq == "Q":
            n = meta["last_period"] if year == meta["last"] else 4
            periods = [
                (
                    f"Q{i:02d}",
                    f"{i}{_ORD[i]} Quarter",
                    i,
                )
                for i in range(n, 0, -1)
            ]
            if annual_average and year != meta["last"]:
                periods.insert(0, ("Q05", "Annual", 5))
        else:
            periods = [("A01", "Annual", 1)]
        for code, name, idx in periods:
            row: dict[str, Any] = {
                "year": str(year),
                "period": code,
                "periodName": name,
                "value": _value(series_id, year, idx),
                "footnotes": [{}],
            }
            if year == meta["last"] and idx == meta["last_period"]:
                row["latest"] = "true"
            if code == "M13":
                row["footnotes"] = [{"code": "A", "text": "Annual average"}]
            if calculations:
                row["calculations"] = {
                    "net_changes": {"1": "0.1", "3": "0.3", "6": "0.6", "12": "1.2"},
                    "pct_changes": {"1": "0.5", "3": "1.5", "6": "3.0", "12": "6.0"},
                }
            rows.append(row)
    if latest:
        rows = [r for r in rows if r.get("latest") == "true"]
    return rows


@dataclass
class FakeBLS:
    """Configurable fake of api.bls.gov. Records every request it receives."""

    requests: list[httpx.Request] = field(default_factory=list)
    payloads: list[dict[str, Any]] = field(default_factory=list)
    fail_times: int = 0  # respond 500 this many times before succeeding
    status_override: str | None = None  # force an API status
    messages_override: list[str] | None = None
    http_status_override: int | None = None
    require_key: bool = False
    flatfiles: dict[str, str] = field(default_factory=dict)
    flatfile_status: int = 200
    default_years: int = 3
    current_year: int = THIS_YEAR

    def handler(self, request: httpx.Request) -> httpx.Response:
        self.requests.append(request)
        if self.fail_times > 0:
            self.fail_times -= 1
            return httpx.Response(500, text="server error")
        if self.http_status_override:
            return httpx.Response(self.http_status_override, text="forced")
        path = request.url.path
        if request.url.host == "download.bls.gov":
            return self._flatfile(path)
        if self.status_override:
            return self._json(
                {
                    "status": self.status_override,
                    "responseTime": 1,
                    "message": self.messages_override or ["forced failure"],
                    "Results": {},
                }
            )
        if path.endswith("/surveys"):
            return self._ok({"survey": SURVEYS})
        if "/surveys/" in path:
            abbr = path.rsplit("/", 1)[-1].upper()
            match = [s for s in SURVEYS if s["survey_abbreviation"] == abbr]
            if not match:
                return self._json(
                    {
                        "status": "REQUEST_FAILED_INVALID_PARAMETERS",
                        "responseTime": 1,
                        "message": [f"Survey {abbr} does not exist"],
                        "Results": {},
                    }
                )
            return self._ok({"survey": match})
        if path.endswith("/timeseries/popular"):
            survey = request.url.params.get("survey")
            ids = POPULAR.get(survey.upper() if survey else None, [])
            return self._ok({"series": [{"seriesID": s} for s in ids]})
        if path.endswith("/timeseries/data/"):
            return self._data(request)
        return httpx.Response(404, text="not found")

    def _flatfile(self, path: str) -> httpx.Response:
        if self.flatfile_status != 200:
            return httpx.Response(self.flatfile_status, text="nope")
        name = path.rsplit("/", 1)[-1]
        if name not in self.flatfiles:
            return httpx.Response(404, text="missing")
        return httpx.Response(200, text=self.flatfiles[name])

    def _data(self, request: httpx.Request) -> httpx.Response:
        payload = json.loads(request.content.decode())
        self.payloads.append(payload)
        if self.require_key and not payload.get("registrationkey"):
            return self._json(
                {
                    "status": "REQUEST_NOT_PROCESSED",
                    "responseTime": 1,
                    "message": ["Registration key required"],
                    "Results": {},
                }
            )
        ids = payload["seriesid"]
        latest = str(payload.get("latest", "")).lower() == "true"
        end = int(payload.get("endyear", self.current_year))
        start = int(payload.get("startyear", end - self.default_years + 1))
        if end - start + 1 > (20 if payload.get("registrationkey") else 10):
            return self._json(
                {
                    "status": "REQUEST_FAILED_INVALID_PARAMETERS",
                    "responseTime": 1,
                    "message": ["Year range exceeds limit"],
                    "Results": {},
                }
            )
        catalog = str(payload.get("catalog", "")).lower() == "true" and bool(
            payload.get("registrationkey")
        )
        messages: list[str] = []
        series_out = []
        for sid in ids:
            if sid not in KNOWN_SERIES:
                messages.append(f"Series does not exist for Series {sid}")
                continue
            obs = _observations(
                sid,
                start,
                end,
                latest=latest,
                annual_average=str(payload.get("annualaverage", "")).lower() == "true",
                calculations=str(payload.get("calculations", "")).lower() == "true",
            )
            if not obs:
                messages.append(f"No Data Available for Series {sid} Year: {start}")
            entry: dict[str, Any] = {"seriesID": sid, "data": obs}
            if catalog:
                meta = KNOWN_SERIES[sid]
                entry["catalog"] = {
                    "series_id": sid,
                    "series_title": meta["title"],
                    "survey_abbreviation": meta["survey"],
                    "survey_name": "Survey " + meta["survey"],
                    "seasonality": "Seasonally Adjusted",
                }
            series_out.append(entry)
        return self._json(
            {
                "status": "REQUEST_SUCCEEDED",
                "responseTime": 42,
                "message": messages,
                "Results": {"series": series_out},
            }
        )

    def _ok(self, results: dict[str, Any]) -> httpx.Response:
        return self._json(
            {"status": "REQUEST_SUCCEEDED", "responseTime": 5, "message": [], "Results": results}
        )

    @staticmethod
    def _json(body: dict[str, Any]) -> httpx.Response:
        return httpx.Response(200, json=body)

    @property
    def transport(self) -> httpx.MockTransport:
        return httpx.MockTransport(self.handler)


@pytest.fixture
def fake() -> FakeBLS:
    return FakeBLS()


@pytest.fixture
def make_client(fake: FakeBLS) -> Iterator[Callable[..., BLSClient]]:
    clients: list[BLSClient] = []

    def _make(api_key: str | None = "test-key", **kwargs: Any) -> BLSClient:
        kwargs.setdefault("sleep", lambda _s: None)
        client = BLSClient(api_key, transport=fake.transport, **kwargs)
        clients.append(client)
        return client

    yield _make
    for c in clients:
        c.close()


@pytest.fixture
def cache_dir(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    d = tmp_path / "cache"
    monkeypatch.setenv("BLS_CACHE_DIR", str(d))
    return d


@pytest.fixture(autouse=True)
def _clean_env(monkeypatch: pytest.MonkeyPatch) -> None:
    for var in (
        "BLS_API_KEY",
        "BLS_FORMAT",
        "BLS_API_BASE_URL",
        "BLS_TIMEOUT",
        "BLS_MAX_RETRIES",
        "BLS_USER_AGENT",
        "NO_COLOR",
    ):
        monkeypatch.delenv(var, raising=False)
