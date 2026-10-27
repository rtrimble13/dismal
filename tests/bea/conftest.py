"""Shared fixtures: a fake BEA API served through ``httpx.MockTransport``."""

from __future__ import annotations

from collections.abc import Callable, Iterator
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import httpx
import pytest

from dismal.bea.client import BEAClient

THIS_YEAR = datetime.now(tz=timezone.utc).year
FIRST_YEAR = 2015
LAST_QUARTER = 2  # the current year has data through Q2 / M06
LAST_MONTH = 6
VALID_KEY = "ABCDEFGH-1234-5678-9ABC-DEF012345678"  # 36 characters, like a real UserID
ROMAN = {1: "I", 2: "II", 3: "III", 4: "IV"}

DATASETS = [
    {"DatasetName": "NIPA", "DatasetDescription": "Standard NIPA tables"},
    {"DatasetName": "Regional", "DatasetDescription": "Regional data sets"},
    {"DatasetName": "GDPbyIndustry", "DatasetDescription": "GDP by Industry"},
    {"DatasetName": "ITA", "DatasetDescription": "International Transactions Accounts"},
]


def _param(
    name: str, desc: str, *, required: bool = True, multiple: bool = False, all_value: str = ""
) -> dict[str, str]:
    return {
        "ParameterName": name,
        "ParameterDataType": "string",
        "ParameterDescription": desc,
        "ParameterIsRequiredFlag": "1" if required else "0",
        "ParameterDefaultValue": "",
        "MultipleAcceptedFlag": "1" if multiple else "0",
        "AllValue": all_value,
    }


PARAMETERS: dict[str, list[dict[str, str]]] = {
    "NIPA": [
        _param("TableName", "The new NIPA table identifier"),
        _param("Frequency", "A - Annual, Q-Quarterly, M-Monthly", multiple=True),
        _param(
            "Year", "List of year(s) of data to retrieve (X for All)", multiple=True, all_value="X"
        ),
        _param(
            "ShowMillions",
            "A flag indicating that million-dollar data should be returned",
            required=False,
        ),
    ],
    "Regional": [
        _param("TableName", "Published table name"),
        _param("LineCode", "Line code in table"),
        _param("GeoFips", "Comma-delimited list of 5-character geographic codes", multiple=True),
        _param(
            "Year", "Comma-delimited list of years", required=False, multiple=True, all_value="ALL"
        ),
    ],
    "GDPbyIndustry": [
        _param(
            "TableID", "The unique GDP by Industry table identifier", multiple=True, all_value="ALL"
        ),
        _param("Frequency", "A - Annual, Q-Quarterly", multiple=True),
        _param("Industry", "List of industries", multiple=True, all_value="ALL"),
        _param("Year", "List of year(s)", multiple=True, all_value="ALL"),
    ],
    "ITA": [
        _param("Indicator", "The indicator code", required=False, multiple=True, all_value="ALL"),
        _param(
            "AreaOrCountry", "The area or country", required=False, multiple=True, all_value="ALL"
        ),
        _param(
            "Frequency", "A - Annual, QSA, QNSA", required=False, multiple=True, all_value="ALL"
        ),
        _param("Year", "Year", required=False, multiple=True, all_value="ALL"),
    ],
}

# NIPA tables known to the fake: lines -> (series code, description) and their frequencies.
NIPA_TABLES: dict[str, dict[str, Any]] = {
    "T10101": {
        "title": "Table 1.1.1. Percent Change From Preceding Period in Real Gross Domestic Product",
        "freqs": "AQ",
        "unit": "Percent change, annual rate",
        "mult": "0",
        "metric": "Fisher Quantity Index",
        "lines": [
            ("A191RL", "Gross domestic product"),
            ("DPCERL", "Personal consumption expenditures"),
            ("DGDSRL", "Goods"),
        ],
    },
    "T10105": {
        "title": "Table 1.1.5. Gross Domestic Product",
        "freqs": "AQ",
        "unit": "Level",
        "mult": "6",
        "metric": "Current Dollars",
        "lines": [
            ("A191RC", "Gross domestic product"),
            ("DPCERC", "Personal consumption expenditures"),
        ],
    },
    "T20600": {
        "title": "Table 2.6. Personal Income and Its Disposition, Monthly",
        "freqs": "M",
        "unit": "Level",
        "mult": "9",
        "metric": "Current Dollars",
        "lines": [("A065RC", "Personal income"), ("A067RC", "Equals: Disposable personal income")],
    },
}
REGIONAL_TABLES: dict[str, dict[str, Any]] = {
    "SAINC1": {
        "freq": "A",
        "lines": {
            "1": ("Personal income (thousands of dollars)", "Thousands of dollars", "3"),
            "2": ("Population (persons)", "Number of persons", "0"),
            "3": ("Per capita personal income (dollars)", "Dollars", "0"),
        },
    },
    "SQINC1": {
        "freq": "Q",
        "lines": {"1": ("Personal income (millions of dollars, SAAR)", "Millions of dollars", "6")},
    },
}
GEOS = {
    "STATE": [("01000", "Alabama"), ("06000", "California"), ("48000", "Texas")],
    "COUNTY": [("01001", "Autauga, AL"), ("06037", "Los Angeles, CA")],
}
GEO_NAMES = {fips: name for geos in GEOS.values() for fips, name in geos} | {
    "00000": "United States"
}
INDUSTRIES = [("11", "Agriculture, forestry, fishing, and hunting"), ("21", "Mining")]
ITA_INDICATORS = {"BalGds": "Balance on goods", "BalServ": "Balance on services"}


def _value(key: str, year: int, idx: int) -> float:
    base = sum(ord(c) for c in key) % 97
    return round(base + (year - 2000) * 1.5 + idx * 0.1, 1)


def _fmt(value: float, *, level: bool) -> str:
    if level:
        return f"{int(value * 1000):,}"
    return f"{value:.1f}"


def _years(raw: str | None, all_token: str) -> list[int]:
    if raw is None or raw.strip().upper() in {all_token.upper(), "ALL", "X"}:
        return list(range(FIRST_YEAR, THIS_YEAR + 1))
    text = raw.strip().upper()
    if text.startswith("LAST"):
        n = int(text[4:])
        return list(range(THIS_YEAR - n + 1, THIS_YEAR + 1))
    return [int(y) for y in text.split(",") if y.strip()]


def _periods(freq: str, year: int) -> list[tuple[str, int]]:
    """Time periods of one year for a frequency, as (code, index)."""
    if freq == "A":
        return [(str(year), 0)] if year < THIS_YEAR else []
    if freq == "Q":
        n = LAST_QUARTER if year == THIS_YEAR else 4
        return [(f"{year}Q{q}", q) for q in range(1, n + 1)]
    n = LAST_MONTH if year == THIS_YEAR else 12
    return [(f"{year}M{m:02d}", m) for m in range(1, n + 1)]


@dataclass
class FakeBEA:
    """Configurable fake of apps.bea.gov/api/data. Records every request it receives."""

    requests: list[httpx.Request] = field(default_factory=list)
    params: list[dict[str, str]] = field(default_factory=list)
    fail_times: int = 0  # respond 500 this many times before succeeding
    http_status_override: int | None = None
    error_override: dict[str, str] | None = None  # force an API Error object
    require_key: bool = True
    valid_keys: tuple[str, ...] = (VALID_KEY, "test-key")

    # -- plumbing ---------------------------------------------------------------
    def handler(self, request: httpx.Request) -> httpx.Response:
        self.requests.append(request)
        params = dict(request.url.params.items())
        self.params.append(params)
        if self.fail_times > 0:
            self.fail_times -= 1
            return httpx.Response(500, text="server error")
        if self.http_status_override:
            return httpx.Response(self.http_status_override, text="forced")
        p = {k.lower(): v for k, v in params.items()}
        if self.error_override:
            return self._error_response(p, self.error_override)
        key = p.get("userid")
        if self.require_key and key not in self.valid_keys:
            return self._error(
                p,
                "3",
                "The UserId provided is invalid or not registered. Please register at https://apps.bea.gov/API/signup/",
            )
        method = p.get("method", "").lower()
        dataset = p.get("datasetname", "")
        try:
            if method == "getdatasetlist":
                return self._ok(p, {"Dataset": DATASETS})
            if method == "getparameterlist":
                return self._parameter_list(p, dataset)
            if method == "getparametervalues":
                return self._parameter_values(p, dataset, p.get("parametername", ""))
            if method == "getparametervaluesfiltered":
                return self._parameter_values(
                    p, dataset, p.get("targetparameter", ""), filtered=True
                )
            if method == "getdata":
                return self._data(p, dataset)
        except _ApiError as exc:
            return self._error(p, exc.code, exc.description)
        return self._error(p, "2", "The Request Method parameter is missing or invalid")

    def _ok(self, p: dict[str, str], results: dict[str, Any]) -> httpx.Response:
        return httpx.Response(
            200, json={"BEAAPI": {"Request": self._request_echo(p), "Results": results}}
        )

    def _error(self, p: dict[str, str], code: str, description: str) -> httpx.Response:
        return self._error_response(p, {"APIErrorCode": code, "APIErrorDescription": description})

    def _error_response(self, p: dict[str, str], error: dict[str, str]) -> httpx.Response:
        return httpx.Response(
            200, json={"BEAAPI": {"Request": self._request_echo(p), "Error": error}}
        )

    @staticmethod
    def _request_echo(p: dict[str, str]) -> dict[str, Any]:
        return {
            "RequestParam": [
                {"ParameterName": k.upper(), "ParameterValue": v} for k, v in p.items()
            ]
        }

    # -- methods ----------------------------------------------------------------
    def _parameter_list(self, p: dict[str, str], dataset: str) -> httpx.Response:
        params = PARAMETERS.get(_canon(dataset))
        if params is None:
            raise _ApiError("40", f"The dataset '{dataset}' does not exist")
        return self._ok(p, {"Parameter": params})

    def _parameter_values(
        self, p: dict[str, str], dataset: str, name: str, *, filtered: bool = False
    ) -> httpx.Response:
        ds, pn = _canon(dataset), name.lower()
        values: list[dict[str, str]]
        if ds == "NIPA" and pn == "tablename":
            values = [
                {"TableName": t, "Description": f"{m['title']} ({') ('.join(m['freqs'])})"}
                for t, m in NIPA_TABLES.items()
            ]
        elif ds == "NIPA" and pn == "frequency":
            values = [
                {"FrequencyID": "A", "Description": "Annual"},
                {"FrequencyID": "Q", "Description": "Quarterly"},
                {"FrequencyID": "M", "Description": "Monthly"},
            ]
        elif ds == "NIPA" and pn == "year":
            table = p.get("tablename")
            if filtered and table not in NIPA_TABLES:
                raise _ApiError("40", f"Invalid TableName {table}")
            values = [
                {
                    "TableName": table or "ALL",
                    "FirstAnnualYear": str(FIRST_YEAR),
                    "LastAnnualYear": str(THIS_YEAR - 1),
                }
            ]
        elif ds == "Regional" and pn == "linecode":
            if filtered:
                table = p.get("tablename", "")
                if table not in REGIONAL_TABLES:
                    raise _ApiError("40", f"Invalid TableName {table}")
                values = [
                    {"Key": k, "Desc": f"[{table}] {v[0]}"}
                    for k, v in REGIONAL_TABLES[table]["lines"].items()
                ]
            else:
                values = [
                    {"Key": k, "Desc": f"[{t}] {v[0]}"}
                    for t, m in REGIONAL_TABLES.items()
                    for k, v in m["lines"].items()
                ]
        elif ds == "Regional" and pn == "geofips":
            values = [{"Key": "00000", "Desc": "United States"}] + [
                {"Key": f, "Desc": n} for geos in GEOS.values() for f, n in geos
            ]
        elif ds == "Regional" and pn == "tablename":
            values = [{"Key": t, "Desc": f"{t} description"} for t in REGIONAL_TABLES]
        elif ds == "GDPbyIndustry" and pn == "tableid":
            values = [
                {"Key": "1", "Desc": "Value Added by Industry (A,Q)"},
                {"Key": "5", "Desc": "Value Added by Industry as a Percentage of GDP (A,Q)"},
            ]
        elif ds == "ITA" and pn == "indicator":
            values = [{"Key": k, "Desc": v} for k, v in ITA_INDICATORS.items()]
        else:
            raise _ApiError("40", f"The parameter '{name}' is not valid for dataset {dataset}")
        if len(values) == 1:  # BEA's XML->JSON quirk: single elements are objects, not lists
            return self._ok(p, {"ParamValue": values[0]})
        return self._ok(p, {"ParamValue": values})

    def _data(self, p: dict[str, str], dataset: str) -> httpx.Response:
        ds = _canon(dataset)
        if ds == "NIPA":
            return self._nipa(p)
        if ds == "Regional":
            return self._regional(p)
        if ds == "GDPbyIndustry":
            return self._gdp_by_industry(p)
        if ds == "ITA":
            return self._ita(p)
        raise _ApiError("40", f"The dataset '{dataset}' does not exist")

    def _nipa(self, p: dict[str, str]) -> httpx.Response:
        for req in ("tablename", "frequency", "year"):
            if req not in p:
                raise _ApiError(
                    "40", f"The dataset requested requires parameters that were not supplied: {req}"
                )
        table = p["tablename"]
        meta = NIPA_TABLES.get(table)
        if meta is None:
            raise _ApiError("204", f"The TableName {table} is not valid")
        freqs = [f.strip().upper() for f in p["frequency"].split(",")]
        years = _years(p["year"], "X")
        rows: list[dict[str, Any]] = []
        for line_no, (code, desc) in enumerate(meta["lines"], start=1):
            for freq in freqs:
                if freq not in meta["freqs"]:
                    continue
                for year in years:
                    for period, idx in _periods(freq, year):
                        value = _value(code, year, idx)
                        rows.append(
                            {
                                "TableName": table,
                                "SeriesCode": code,
                                "LineNumber": str(line_no),
                                "LineDescription": desc,
                                "TimePeriod": period,
                                "METRIC_NAME": meta["metric"],
                                "CL_UNIT": meta["unit"],
                                "UNIT_MULT": meta["mult"],
                                "DataValue": _fmt(value, level=meta["unit"] == "Level"),
                                "NoteRef": table,
                            }
                        )
        if rows and years and years[-1] == FIRST_YEAR and "A191RL" in [c for c, _ in meta["lines"]]:
            rows[0]["DataValue"] = "(NA)"  # exercise the null parser
        results = {
            "Statistic": "NIPA Table",
            "UTCProductionTime": "2026-10-25T00:00:00.000",
            "Dimensions": [
                {"Ordinal": "1", "Name": "TableName", "DataType": "string", "IsValue": "0"},
                {"Ordinal": "2", "Name": "SeriesCode", "DataType": "string", "IsValue": "0"},
                {"Ordinal": "3", "Name": "LineNumber", "DataType": "numeric", "IsValue": "0"},
                {"Ordinal": "4", "Name": "LineDescription", "DataType": "string", "IsValue": "0"},
                {"Ordinal": "5", "Name": "TimePeriod", "DataType": "string", "IsValue": "0"},
                {"Ordinal": "6", "Name": "CL_UNIT", "DataType": "string", "IsValue": "0"},
                {"Ordinal": "7", "Name": "UNIT_MULT", "DataType": "numeric", "IsValue": "0"},
                {"Ordinal": "8", "Name": "DataValue", "DataType": "numeric", "IsValue": "1"},
                {"Ordinal": "9", "Name": "NoteRef", "DataType": "string", "IsValue": "0"},
            ],
            "Data": rows,
            "Notes": [
                {"NoteRef": table, "NoteText": f"{meta['title']} - LastRevised: October 24, 2026"}
            ],
        }
        return self._ok(p, results)

    def _regional(self, p: dict[str, str]) -> httpx.Response:
        for req in ("tablename", "linecode", "geofips"):
            if req not in p:
                raise _ApiError(
                    "40", f"The dataset requested requires parameters that were not supplied: {req}"
                )
        table, line = p["tablename"], p["linecode"]
        meta = REGIONAL_TABLES.get(table)
        if meta is None or line not in meta["lines"]:
            raise _ApiError("40", f"Invalid TableName/LineCode: {table}/{line}")
        desc, unit, mult = meta["lines"][line]
        geo = p["geofips"].upper()
        geos = GEOS.get(geo) or [(f, GEO_NAMES.get(f, f)) for f in geo.split(",")]
        years = _years(p.get("year"), "ALL")
        rows = []
        for fips, name in geos:
            for year in years:
                for period, idx in _periods(meta["freq"], year):
                    rows.append(
                        {
                            "Code": f"{table}-{line}",
                            "GeoFips": fips,
                            "GeoName": name,
                            "TimePeriod": period,
                            "CL_UNIT": unit,
                            "UNIT_MULT": mult,
                            "DataValue": _fmt(_value(fips + line, year, idx), level=True),
                            "NoteRef": " ",
                        }
                    )
        results = {
            "Statistic": desc,
            "UnitOfMeasure": unit,
            "Dimensions": [{"Ordinal": "1", "Name": "Code", "DataType": "string", "IsValue": "0"}],
            "Data": rows,
            "Notes": [{"NoteRef": " ", "NoteText": f"{table}: {desc}"}],
        }
        return self._ok(p, results)

    def _gdp_by_industry(self, p: dict[str, str]) -> httpx.Response:
        for req in ("tableid", "frequency", "industry", "year"):
            if req not in p:
                raise _ApiError(
                    "40", f"The dataset requested requires parameters that were not supplied: {req}"
                )
        table_id = p["tableid"]
        if table_id not in {"1", "5"}:
            raise _ApiError("40", f"Invalid TableID {table_id}")
        freqs = [f.strip().upper() for f in p["frequency"].split(",")]
        wanted = p["industry"].upper()
        industries = (
            INDUSTRIES if wanted == "ALL" else [i for i in INDUSTRIES if i[0] in wanted.split(",")]
        )
        years = _years(p["year"], "ALL")
        rows: list[dict[str, Any]] = []
        for code, desc in industries:
            for freq in freqs:
                for year in years:
                    for _period, idx in _periods(freq, year):
                        rows.append(
                            {
                                "TableID": int(table_id),
                                "Frequency": freq,
                                "Year": str(year),
                                "Quarter": str(year) if freq == "A" else ROMAN[idx],
                                "Industry": code,
                                "IndustrYDescription": desc,
                                "DataValue": f"{_value(code, year, idx):.1f}",
                                "NoteRef": "1",
                            }
                        )
        return self._ok(
            p,
            {
                "Statistic": "GDP by Industry",
                "Dimensions": [],
                "Data": rows,
                "Notes": [{"NoteRef": "1", "NoteText": "Value Added by Industry"}],
            },
        )

    def _ita(self, p: dict[str, str]) -> httpx.Response:
        indicators = list(p.get("indicator", "ALL").split(","))
        if indicators == ["ALL"]:
            indicators = list(ITA_INDICATORS)
        area = p.get("areaorcountry", "AllCountries")
        freqs = [f.strip().upper() for f in p.get("frequency", "A").split(",")]
        years = _years(p.get("year"), "ALL")
        rows = []
        for ind in indicators:
            if ind not in ITA_INDICATORS:
                raise _ApiError("40", f"Invalid Indicator {ind}")
            for freq in freqs:
                for year in years:
                    for period, idx in _periods("Q" if freq.startswith("Q") else "A", year):
                        rows.append(
                            {
                                "Indicator": ind,
                                "AreaOrCountry": area,
                                "Frequency": freq,
                                "Year": str(year),
                                "TimeSeriesId": f"{ind}_{area}_{freq}",
                                "TimeSeriesDescription": ITA_INDICATORS[ind],
                                "TimePeriod": period,
                                "CL_UNIT": "USD",
                                "UNIT_MULT": "6",
                                "DataValue": _fmt(_value(ind, year, idx), level=True),
                                "NoteRef": "",
                            }
                        )
        return self._ok(p, {"Statistic": "ITA", "Dimensions": [], "Data": rows, "Notes": []})

    @property
    def transport(self) -> httpx.MockTransport:
        return httpx.MockTransport(self.handler)


class _ApiError(Exception):
    def __init__(self, code: str, description: str) -> None:
        super().__init__(description)
        self.code = code
        self.description = description


def _canon(name: str) -> str:
    for ds in ("NIPA", "Regional", "GDPbyIndustry", "ITA"):
        if ds.lower() == name.lower():
            return ds
    return name


@pytest.fixture
def fake() -> FakeBEA:
    return FakeBEA()


@pytest.fixture
def make_client(fake: FakeBEA) -> Iterator[Callable[..., BEAClient]]:
    clients: list[BEAClient] = []

    def _make(api_key: str | None = "test-key", **kwargs: Any) -> BEAClient:
        kwargs.setdefault("sleep", lambda _s: None)
        client = BEAClient(api_key, transport=fake.transport, **kwargs)
        clients.append(client)
        return client

    yield _make
    for c in clients:
        c.close()


@pytest.fixture
def cache_dir(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    d = tmp_path / "cache"
    monkeypatch.setenv("BEA_CACHE_DIR", str(d))
    return d


@pytest.fixture(autouse=True)
def _clean_env(monkeypatch: pytest.MonkeyPatch) -> None:
    for var in (
        "BEA_API_KEY",
        "BEA_FORMAT",
        "BEA_API_BASE_URL",
        "BEA_TIMEOUT",
        "BEA_MAX_RETRIES",
        "BEA_USER_AGENT",
        "NO_COLOR",
    ):
        monkeypatch.delenv(var, raising=False)
