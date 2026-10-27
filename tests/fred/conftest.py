"""Shared fixtures: a fake FRED API served through ``httpx.MockTransport``."""

from __future__ import annotations

import math
from collections.abc import Callable, Iterator
from dataclasses import dataclass, field
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from typing import Any

import httpx
import pytest

from dismal.fred.client import FREDClient

TODAY = datetime.now(tz=timezone.utc).date()
THIS_YEAR = TODAY.year
LAST_OBS = date(THIS_YEAR, 6, 30)  # the fake's data end here, whatever today is
VALID_KEY = "0123456789abcdef0123456789abcdef"  # 32 lower-case alphanumerics, like a real key
FAR_FUTURE = "9999-12-31"

# Series the fake API knows about.
KNOWN: dict[str, dict[str, Any]] = {
    "UNRATE": {
        "title": "Unemployment Rate",
        "freq": "M",
        "start": date(2010, 1, 1),
        "units": "Percent",
        "sa": "Seasonally Adjusted",
        "sa_short": "SA",
        "popularity": 95,
        "base": 4.0,
        "tags": ["usa", "monthly", "sa", "unemployment", "bls"],
        "release": 50,
        "category": 12,
    },
    "PAYEMS": {
        "title": "All Employees, Total Nonfarm",
        "freq": "M",
        "start": date(2010, 1, 1),
        "units": "Thousands of Persons",
        "sa": "Seasonally Adjusted",
        "sa_short": "SA",
        "popularity": 90,
        "base": 150000.0,
        "tags": ["usa", "monthly", "sa", "employment", "bls"],
        "release": 50,
        "category": 12,
    },
    "GDP": {
        "title": "Gross Domestic Product",
        "freq": "Q",
        "start": date(2010, 1, 1),
        "units": "Billions of Dollars",
        "sa": "Seasonally Adjusted Annual Rate",
        "sa_short": "SAAR",
        "popularity": 92,
        "base": 20000.0,
        "tags": ["usa", "quarterly", "saar", "gdp", "bea"],
        "release": 53,
        "category": 32992,
    },
    "GDPC1": {
        "title": "Real Gross Domestic Product",
        "freq": "Q",
        "start": date(2010, 1, 1),
        "units": "Billions of Chained 2017 Dollars",
        "sa": "Seasonally Adjusted Annual Rate",
        "sa_short": "SAAR",
        "popularity": 88,
        "base": 19000.0,
        "tags": ["usa", "quarterly", "saar", "gdp", "real", "bea"],
        "release": 53,
        "category": 32992,
    },
    "CPIAUCSL": {
        "title": "Consumer Price Index for All Urban Consumers: All Items in U.S. City Average",
        "freq": "M",
        "start": date(2010, 1, 1),
        "units": "Index 1982-1984=100",
        "sa": "Seasonally Adjusted",
        "sa_short": "SA",
        "popularity": 93,
        "base": 250.0,
        "tags": ["usa", "monthly", "sa", "cpi", "inflation", "bls"],
        "release": 10,
        "category": 9,
    },
    "DGS10": {
        "title": "Market Yield on U.S. Treasury Securities at 10-Year Constant Maturity",
        "freq": "D",
        "start": date(2022, 1, 3),
        "units": "Percent",
        "sa": "Not Seasonally Adjusted",
        "sa_short": "NSA",
        "popularity": 85,
        "base": 3.0,
        "tags": ["usa", "daily", "nsa", "treasury", "interest rate", "frb"],
        "release": 18,
        "category": 115,
    },
    "ICSA": {
        "title": "Initial Claims",
        "freq": "W",
        "start": date(2022, 1, 1),
        "units": "Number",
        "sa": "Seasonally Adjusted",
        "sa_short": "SA",
        "popularity": 80,
        "base": 220000.0,
        "tags": ["usa", "weekly", "sa", "claims", "dol"],
        "release": 180,
        "category": 32240,
    },
}
FREQ_NAMES = {"D": "Daily", "W": "Weekly", "M": "Monthly", "Q": "Quarterly", "A": "Annual"}
RELEASES = [
    {
        "id": 10,
        "name": "Consumer Price Index",
        "press_release": True,
        "link": "https://www.bls.gov/cpi/",
    },
    {
        "id": 18,
        "name": "H.15 Selected Interest Rates",
        "press_release": True,
        "link": "https://www.federalreserve.gov/releases/h15/",
    },
    {
        "id": 50,
        "name": "Employment Situation",
        "press_release": True,
        "link": "https://www.bls.gov/ces/",
    },
    {
        "id": 53,
        "name": "Gross Domestic Product",
        "press_release": True,
        "link": "https://www.bea.gov/",
    },
    {
        "id": 180,
        "name": "Unemployment Insurance Weekly Claims Report",
        "press_release": True,
        "link": "https://www.dol.gov/",
    },
]
CATEGORIES = {
    0: [
        {"id": 32991, "name": "Money, Banking, & Finance", "parent_id": 0},
        {"id": 10, "name": "Population, Employment, & Labor Markets", "parent_id": 0},
        {"id": 32992, "name": "National Accounts", "parent_id": 0},
        {"id": 32455, "name": "Prices", "parent_id": 0},
    ],
    10: [{"id": 12, "name": "Current Population Survey (Household Survey)", "parent_id": 10}],
    32455: [{"id": 9, "name": "Consumer Price Indexes (CPI and PCE)", "parent_id": 32455}],
}
SOURCES = [
    {
        "id": 1,
        "name": "Board of Governors of the Federal Reserve System (US)",
        "link": "http://www.federalreserve.gov/",
    },
    {"id": 22, "name": "U.S. Bureau of Labor Statistics", "link": "http://www.bls.gov/"},
]
VINTAGES = ["2024-01-05", "2024-02-02", "2024-03-08", "2024-04-05", "2024-05-03"]


def _dates(freq: str, start: date, end: date) -> list[date]:
    out: list[date] = []
    d = start
    if freq == "D":
        while d <= end:
            if d.weekday() < 5:
                out.append(d)
            d += timedelta(days=1)
    elif freq == "W":
        while d.weekday() != 5:  # Saturdays
            d += timedelta(days=1)
        while d <= end:
            out.append(d)
            d += timedelta(days=7)
    elif freq == "M":
        d = date(start.year, start.month, 1)
        while d <= end:
            out.append(d)
            d = date(d.year + (d.month == 12), d.month % 12 + 1, 1)
    elif freq == "Q":
        d = date(start.year, ((start.month - 1) // 3) * 3 + 1, 1)
        while d <= end:
            out.append(d)
            d = date(d.year + (d.month >= 10), (d.month + 2) % 12 + 1, 1)
    else:  # A
        d = date(start.year, 1, 1)
        while d <= end:
            out.append(d)
            d = date(d.year + 1, 1, 1)
    return out


def _value(sid: str, d: date) -> float | None:
    meta = KNOWN[sid]
    if meta["freq"] == "D" and (d.month, d.day) in {(1, 1), (12, 25)}:
        return None  # holidays: FRED reports "."
    days = (d - meta["start"]).days
    return round(meta["base"] + days / 365.0 * 1.5 + (d.toordinal() % 7) * 0.01, 3)


def _period_key(freq: str, d: date) -> tuple[int, ...]:
    if freq == "a":
        return (d.year,)
    if freq == "q":
        return (d.year, (d.month - 1) // 3)
    if freq == "m":
        return (d.year, d.month)
    if freq == "w":
        iso = d.isocalendar()
        return (iso[0], iso[1])
    return (d.toordinal(),)


def _period_start(freq: str, d: date) -> date:
    if freq == "a":
        return date(d.year, 1, 1)
    if freq == "q":
        return date(d.year, ((d.month - 1) // 3) * 3 + 1, 1)
    if freq == "m":
        return date(d.year, d.month, 1)
    if freq == "w":
        return d - timedelta(days=d.weekday())
    return d


_RANK = {"d": 0, "w": 1, "bw": 2, "m": 3, "q": 4, "sa": 5, "a": 6}


def _aggregate(
    rows: list[tuple[date, float | None]], freq: str, method: str
) -> list[tuple[date, float | None]]:
    groups: dict[tuple[int, ...], list[tuple[date, float | None]]] = {}
    for d, v in rows:
        groups.setdefault(_period_key(freq, d), []).append((d, v))
    out: list[tuple[date, float | None]] = []
    for key in sorted(groups):
        members = groups[key]
        values = [v for _, v in members if v is not None]
        if method == "eop":
            agg = members[-1][1]
        elif method == "sum":
            agg = round(sum(values), 3) if values else None
        else:
            agg = round(sum(values) / len(values), 4) if values else None
        out.append((_period_start(freq, members[0][0]), agg))
    return out


def _year_ago(freq: str, i: int) -> int | None:
    back = {"M": 12, "Q": 4, "A": 1}.get(freq)
    return i - back if back is not None and i - back >= 0 else None


def _transform(
    rows: list[tuple[date, float | None]], units: str, freq: str
) -> list[tuple[date, float | None]]:
    if units == "lin":
        return rows
    out: list[tuple[date, float | None]] = []
    for i, (d, v) in enumerate(rows):
        prev = rows[i - 1][1] if i > 0 else None
        j = _year_ago(freq, i)
        ago = rows[j][1] if j is not None else None
        new: float | None
        if v is None:
            new = None
        elif units == "chg":
            new = None if prev is None else round(v - prev, 4)
        elif units == "pch":
            new = None if not prev else round((v / prev - 1) * 100, 4)
        elif units == "ch1":
            new = None if ago is None else round(v - ago, 4)
        elif units == "pc1":
            new = None if not ago else round((v / ago - 1) * 100, 4)
        elif units == "log":
            new = round(math.log(v), 6) if v > 0 else None
        else:  # pca, cch, cca: good enough for tests
            new = None if not prev else round((v / prev - 1) * 100, 4)
        out.append((d, new))
    return out


@dataclass
class FakeFRED:
    """Configurable fake of api.stlouisfed.org/fred. Records every request it receives."""

    requests: list[httpx.Request] = field(default_factory=list)
    params: list[dict[str, str]] = field(default_factory=list)
    fail_times: int = 0  # respond 500 this many times before succeeding
    http_status_override: int | None = None
    require_key: bool = True
    valid_keys: tuple[str, ...] = (VALID_KEY, "test-key")
    max_limit: int = 100_000  # the fake's page size cap (lower it to test pagination)

    # -- plumbing ---------------------------------------------------------------
    def handler(self, request: httpx.Request) -> httpx.Response:
        self.requests.append(request)
        params = dict(request.url.params.items())
        self.params.append(params)
        if self.fail_times > 0:
            self.fail_times -= 1
            return httpx.Response(500, text="server error")
        if self.http_status_override:
            return httpx.Response(
                self.http_status_override,
                json={"error_code": self.http_status_override, "error_message": "forced"},
            )
        key = params.get("api_key")
        if self.require_key:
            if not key:
                return self._error(
                    400,
                    "Bad Request.  Variable api_key is not set.  Read "
                    "https://fred.stlouisfed.org/docs/api/api_key.html for more information.",
                )
            if key not in self.valid_keys:
                return self._error(
                    400,
                    "Bad Request.  The value for variable api_key is not a 32 character "
                    "alpha-numeric lower-case string.  Read "
                    "https://fred.stlouisfed.org/docs/api/api_key.html for more information.",
                )
        path = request.url.path.removeprefix("/fred").strip("/")
        handlers: dict[str, Callable[[dict[str, str]], httpx.Response]] = {
            "series": self._series,
            "series/observations": self._observations,
            "series/search": self._search,
            "series/vintagedates": self._vintagedates,
            "series/updates": self._updates,
            "releases": self._releases,
            "release": self._release,
            "release/series": self._release_series,
            "releases/dates": self._release_dates,
            "category": self._category,
            "category/children": self._category_children,
            "category/series": self._category_series,
            "sources": self._sources,
        }
        handler = handlers.get(path)
        if handler is None:
            return httpx.Response(404, json={"error_code": 404, "error_message": "Not Found"})
        return handler(params)

    @staticmethod
    def _error(status: int, message: str) -> httpx.Response:
        return httpx.Response(status, json={"error_code": status, "error_message": message})

    @staticmethod
    def _info(sid: str) -> dict[str, Any]:
        meta = KNOWN[sid]
        last = _dates(meta["freq"], meta["start"], LAST_OBS)[-1]
        return {
            "id": sid,
            "realtime_start": TODAY.isoformat(),
            "realtime_end": TODAY.isoformat(),
            "title": meta["title"],
            "observation_start": meta["start"].isoformat(),
            "observation_end": last.isoformat(),
            "frequency": FREQ_NAMES[meta["freq"]],
            "frequency_short": meta["freq"],
            "units": meta["units"],
            "units_short": meta["units"][:12],
            "seasonal_adjustment": meta["sa"],
            "seasonal_adjustment_short": meta["sa_short"],
            "last_updated": f"{THIS_YEAR}-07-05 07:46:02-05",
            "popularity": meta["popularity"],
            "group_popularity": meta["popularity"],
            "notes": f"Notes for {sid}.",
        }

    # -- endpoints --------------------------------------------------------------
    def _series(self, p: dict[str, str]) -> httpx.Response:
        sid = p.get("series_id", "").upper()
        if sid not in KNOWN:
            return self._error(400, "Bad Request.  The series does not exist.")
        return httpx.Response(
            200,
            json={
                "realtime_start": TODAY.isoformat(),
                "realtime_end": TODAY.isoformat(),
                "seriess": [self._info(sid)],
            },
        )

    def _observations(self, p: dict[str, str]) -> httpx.Response:
        sid = p.get("series_id", "").upper()
        if sid not in KNOWN:
            return self._error(400, "Bad Request.  The series does not exist.")
        meta = KNOWN[sid]
        rows = [(d, _value(sid, d)) for d in _dates(meta["freq"], meta["start"], LAST_OBS)]
        realtime_start = p.get("realtime_start", TODAY.isoformat())
        realtime_end = p.get("realtime_end", TODAY.isoformat())
        vintage = date.fromisoformat(realtime_start)
        if vintage < TODAY:  # an older vintage: fewer observations, pre-revision values
            cutoff = vintage - timedelta(days=30)
            rows = [(d, None if v is None else round(v - 0.5, 3)) for d, v in rows if d <= cutoff]
        freq = p.get("frequency")
        native = meta["freq"].lower()
        if freq:
            if _RANK.get(freq, 0) < _RANK[native]:
                return self._error(
                    400,
                    "Bad Request.  Value of frequency is lower than the series' native frequency.",
                )
            if freq != native:
                rows = _aggregate(rows, freq, p.get("aggregation_method", "avg"))
        rows = _transform(rows, p.get("units", "lin"), meta["freq"] if not freq else freq.upper())
        start = date.fromisoformat(p.get("observation_start", "1776-07-04"))
        end = date.fromisoformat(p.get("observation_end", FAR_FUTURE))
        rows = [(d, v) for d, v in rows if start <= d <= end]
        if p.get("sort_order", "asc") == "desc":
            rows.reverse()
        count = len(rows)
        limit = min(int(p.get("limit", 100000)), self.max_limit)
        offset = int(p.get("offset", 0))
        page = rows[offset : offset + limit]
        rt_end = FAR_FUTURE if vintage >= TODAY else realtime_end
        return httpx.Response(
            200,
            json={
                "realtime_start": realtime_start,
                "realtime_end": realtime_end,
                "observation_start": start.isoformat(),
                "observation_end": end.isoformat(),
                "units": p.get("units", "lin"),
                "output_type": 1,
                "file_type": "json",
                "order_by": "observation_date",
                "sort_order": p.get("sort_order", "asc"),
                "count": count,
                "offset": offset,
                "limit": limit,
                "observations": [
                    {
                        "realtime_start": realtime_start,
                        "realtime_end": rt_end,
                        "date": d.isoformat(),
                        "value": "." if v is None else repr(v),
                    }
                    for d, v in page
                ],
            },
        )

    def _search(self, p: dict[str, str]) -> httpx.Response:
        text = p.get("search_text", "").lower()
        words = text.split()
        if p.get("search_type") == "series_id":
            ids = [sid for sid in KNOWN if sid.lower().startswith(text)]
        else:
            ids = [sid for sid, m in KNOWN.items() if all(w in m["title"].lower() for w in words)]
        fv, fval = p.get("filter_variable"), p.get("filter_value")
        if fv == "frequency":
            ids = [s for s in ids if FREQ_NAMES[KNOWN[s]["freq"]] == fval]
        elif fv == "seasonal_adjustment":
            ids = [s for s in ids if KNOWN[s]["sa"] == fval]
        for tag in filter(None, p.get("tag_names", "").split(";")):
            ids = [s for s in ids if tag in KNOWN[s]["tags"]]
        for tag in filter(None, p.get("exclude_tag_names", "").split(";")):
            ids = [s for s in ids if tag not in KNOWN[s]["tags"]]
        order = p.get("order_by", "search_rank")
        reverse = (
            p.get("sort_order", "desc" if order in {"search_rank", "popularity"} else "asc")
            == "desc"
        )
        keyfn = (
            (lambda s: KNOWN[s]["popularity"])
            if order in {"search_rank", "popularity"}
            else (lambda s: s if order == "series_id" else KNOWN[s]["title"])
        )
        ids.sort(key=keyfn, reverse=reverse)
        count = len(ids)
        offset, limit = int(p.get("offset", 0)), int(p.get("limit", 1000))
        return httpx.Response(
            200,
            json={
                "realtime_start": TODAY.isoformat(),
                "realtime_end": TODAY.isoformat(),
                "order_by": order,
                "sort_order": "desc" if reverse else "asc",
                "count": count,
                "offset": offset,
                "limit": limit,
                "seriess": [self._info(s) for s in ids[offset : offset + limit]],
            },
        )

    def _vintagedates(self, p: dict[str, str]) -> httpx.Response:
        sid = p.get("series_id", "").upper()
        if sid not in KNOWN:
            return self._error(400, "Bad Request.  The series does not exist.")
        return httpx.Response(
            200,
            json={
                "realtime_start": "1776-07-04",
                "realtime_end": FAR_FUTURE,
                "order_by": "vintage_date",
                "sort_order": "asc",
                "count": len(VINTAGES),
                "offset": 0,
                "limit": 10000,
                "vintage_dates": VINTAGES,
            },
        )

    def _updates(self, p: dict[str, str]) -> httpx.Response:
        ids = sorted(KNOWN, key=lambda s: KNOWN[s]["popularity"], reverse=True)[
            : int(p.get("limit", 100))
        ]
        return httpx.Response(
            200,
            json={
                "count": len(KNOWN),
                "offset": 0,
                "limit": int(p.get("limit", 100)),
                "seriess": [self._info(s) for s in ids],
            },
        )

    def _releases(self, p: dict[str, str]) -> httpx.Response:
        offset, limit = int(p.get("offset", 0)), int(p.get("limit", 1000))
        return httpx.Response(
            200,
            json={
                "count": len(RELEASES),
                "offset": offset,
                "limit": limit,
                "releases": RELEASES[offset : offset + limit],
            },
        )

    def _release(self, p: dict[str, str]) -> httpx.Response:
        rid = int(p.get("release_id", "0"))
        match = [r for r in RELEASES if r["id"] == rid]
        if not match:
            return self._error(400, "Bad Request.  The release does not exist.")
        return httpx.Response(
            200, json={"releases": [{**match[0], "notes": f"Notes for release {rid}."}]}
        )

    def _release_series(self, p: dict[str, str]) -> httpx.Response:
        rid = int(p.get("release_id", "0"))
        ids = [s for s, m in KNOWN.items() if m["release"] == rid]
        limit = int(p.get("limit", 1000))
        return httpx.Response(
            200,
            json={
                "count": len(ids),
                "offset": 0,
                "limit": limit,
                "seriess": [self._info(s) for s in ids[:limit]],
            },
        )

    def _release_dates(self, p: dict[str, str]) -> httpx.Response:
        start = date.fromisoformat(p.get("realtime_start", TODAY.isoformat()))
        end = date.fromisoformat(p.get("realtime_end", TODAY.isoformat()))
        dates = []
        for i, r in enumerate(RELEASES):
            d = start + timedelta(days=i * 3)
            if start <= d <= end:
                dates.append(
                    {"release_id": r["id"], "release_name": r["name"], "date": d.isoformat()}
                )
        return httpx.Response(
            200, json={"count": len(dates), "offset": 0, "limit": 1000, "release_dates": dates}
        )

    def _category(self, p: dict[str, str]) -> httpx.Response:
        cid = int(p.get("category_id", "0"))
        if cid == 0:
            return httpx.Response(
                200, json={"categories": [{"id": 0, "name": "Categories", "parent_id": None}]}
            )
        for children in CATEGORIES.values():
            for c in children:
                if c["id"] == cid:
                    return httpx.Response(200, json={"categories": [c]})
        return self._error(400, "Bad Request.  The category does not exist.")

    def _category_children(self, p: dict[str, str]) -> httpx.Response:
        cid = int(p.get("category_id", "0"))
        return httpx.Response(200, json={"categories": CATEGORIES.get(cid, [])})

    def _category_series(self, p: dict[str, str]) -> httpx.Response:
        cid = int(p.get("category_id", "0"))
        ids = [s for s, m in KNOWN.items() if m["category"] == cid]
        limit = int(p.get("limit", 1000))
        return httpx.Response(
            200,
            json={
                "count": len(ids),
                "offset": 0,
                "limit": limit,
                "seriess": [self._info(s) for s in ids[:limit]],
            },
        )

    def _sources(self, p: dict[str, str]) -> httpx.Response:
        return httpx.Response(
            200, json={"count": len(SOURCES), "offset": 0, "limit": 1000, "sources": SOURCES}
        )

    @property
    def transport(self) -> httpx.MockTransport:
        return httpx.MockTransport(self.handler)


@pytest.fixture
def fake() -> FakeFRED:
    return FakeFRED()


@pytest.fixture
def make_client(fake: FakeFRED) -> Iterator[Callable[..., FREDClient]]:
    clients: list[FREDClient] = []

    def _make(api_key: str | None = "test-key", **kwargs: Any) -> FREDClient:
        kwargs.setdefault("sleep", lambda _s: None)
        client = FREDClient(api_key, transport=fake.transport, **kwargs)
        clients.append(client)
        return client

    yield _make
    for c in clients:
        c.close()


@pytest.fixture
def cache_dir(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    d = tmp_path / "cache"
    monkeypatch.setenv("FRED_CACHE_DIR", str(d))
    return d


@pytest.fixture(autouse=True)
def _clean_env(monkeypatch: pytest.MonkeyPatch) -> None:
    for var in (
        "FRED_API_KEY",
        "FRED_FORMAT",
        "FRED_API_BASE_URL",
        "FRED_TIMEOUT",
        "FRED_MAX_RETRIES",
        "FRED_USER_AGENT",
        "NO_COLOR",
    ):
        monkeypatch.delenv(var, raising=False)
