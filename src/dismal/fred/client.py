"""HTTP client for the FRED API (Federal Reserve Bank of St. Louis).

Highlights
----------
* One method per endpoint the CLI uses: series metadata, observations (with
  transparent **pagination**), full-text search, vintage dates, recent
  updates, releases and release dates, categories and sources.
* **Retries** with exponential back-off for transport errors, HTTP 429 and 5xx.
* Normalised **error handling**: the API's ``error_message`` becomes
  :class:`~dismal.fred.errors.FREDAPIError` (``FREDNotFoundError`` for unknown ids),
  a rejected key :class:`~dismal.fred.errors.FREDConfigError`, and HTTP 429
  :class:`~dismal.fred.errors.FREDQuotaError`.
* :meth:`FREDClient.fetch` requests several series (one call each), applies
  the same window, frequency, units and vintage to all of them and reports
  unknown series as messages instead of failing the whole call.

Every request needs an API key (``api_key``); FRED allows 120 requests per
minute per key and returns at most 100,000 observations per request.
"""

from __future__ import annotations

import contextlib
import datetime as _dt
import json
import logging
import random
import time
from collections.abc import Callable, Iterable, Mapping, Sequence
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any

import httpx

from dismal.fred.config import (
    DEFAULT_BASE_URL,
    DEFAULT_MAX_RETRIES,
    DEFAULT_TIMEOUT,
    SIGNUP_URL,
    Settings,
)
from dismal.fred.errors import (
    FREDAPIError,
    FREDConfigError,
    FREDHTTPError,
    FREDNetworkError,
    FREDNotFoundError,
    FREDQuotaError,
)
from dismal.fred.models import (
    Category,
    DataResponse,
    Observation,
    Release,
    ReleaseDate,
    Series,
    SeriesInfo,
    Source,
)

log = logging.getLogger("dismal.fred.client")

_RETRY_STATUSES = {429, 500, 502, 503, 504}
_NOT_FOUND_NEEDLES = ("does not exist", "not found", "no such")


@dataclass(frozen=True)
class Limits:
    """Limits published by FRED for the API."""

    requests_per_minute: int = 120
    observations_per_request: int = 100_000
    search_results_per_request: int = 1_000


LIMITS = Limits()


def _iso(d: _dt.date | None) -> str | None:
    return d.isoformat() if d else None


class FREDClient:
    """Thin, synchronous client for the FRED API.

    Parameters
    ----------
    api_key:
        The 32-character key from https://fred.stlouisfed.org/docs/api/api_key.html.
        Required by the API for every call.
    transport:
        Optional :class:`httpx.BaseTransport` (e.g. ``httpx.MockTransport``) used
        for testing.
    on_message:
        Callback invoked with each informational message produced while
        fetching (e.g. *"series NOPE does not exist"*).
    """

    def __init__(
        self,
        api_key: str | None = None,
        *,
        base_url: str = DEFAULT_BASE_URL,
        timeout: float = DEFAULT_TIMEOUT,
        max_retries: int = DEFAULT_MAX_RETRIES,
        user_agent: str | None = None,
        transport: httpx.BaseTransport | None = None,
        on_message: Callable[[str], None] | None = None,
        sleep: Callable[[float], None] = time.sleep,
    ) -> None:
        self.api_key = api_key or None
        self.base_url = base_url.rstrip("/")
        self.max_retries = max(0, max_retries)
        self.on_message = on_message
        self._sleep = sleep
        headers = {"Accept": "application/json"}
        if user_agent:
            headers["User-Agent"] = user_agent
        self._http = httpx.Client(timeout=timeout, headers=headers, transport=transport)
        self.request_count = 0

    @classmethod
    def from_settings(
        cls,
        settings: Settings,
        *,
        transport: httpx.BaseTransport | None = None,
        on_message: Callable[[str], None] | None = None,
    ) -> FREDClient:
        return cls(
            settings.api_key,
            base_url=settings.base_url,
            timeout=settings.timeout,
            max_retries=settings.max_retries,
            user_agent=settings.user_agent,
            transport=transport,
            on_message=on_message,
        )

    # -- lifecycle -----------------------------------------------------------
    def close(self) -> None:
        self._http.close()

    def __enter__(self) -> FREDClient:
        return self

    def __exit__(self, *exc: object) -> None:
        self.close()

    # -- limits ---------------------------------------------------------------
    @property
    def limits(self) -> Limits:
        return LIMITS

    # -- low level ------------------------------------------------------------
    def _request(self, path: str, params: Mapping[str, Any] | None = None) -> dict[str, Any]:
        """Perform one GET with retries and return the decoded JSON body."""
        query: dict[str, Any] = {"file_type": "json"}
        if self.api_key:
            query["api_key"] = self.api_key
        for k, v in (params or {}).items():
            if v is not None and v != "":
                query[k] = v
        url = f"{self.base_url}/{path.lstrip('/')}"
        shown = {k: v for k, v in query.items() if k != "api_key"}
        attempt = 0
        while True:
            attempt += 1
            self.request_count += 1
            log.debug("GET %s attempt=%d params=%s", url, attempt, shown)
            try:
                response = self._http.get(url, params=query)
            except httpx.TimeoutException as exc:
                if attempt <= self.max_retries:
                    self._backoff(attempt, None)
                    continue
                raise FREDNetworkError(
                    f"request to {url} timed out", hint="increase FRED_TIMEOUT or retry later"
                ) from exc
            except httpx.HTTPError as exc:
                if attempt <= self.max_retries:
                    self._backoff(attempt, None)
                    continue
                raise FREDNetworkError(
                    f"could not reach {url}: {exc}",
                    hint="check network connectivity and proxy settings",
                ) from exc

            if response.status_code in _RETRY_STATUSES and attempt <= self.max_retries:
                self._backoff(attempt, response.headers.get("Retry-After"))
                continue
            if response.status_code == 429:
                raise FREDQuotaError(
                    "rate limited by api.stlouisfed.org (HTTP 429)",
                    hint="FRED allows 120 requests per minute per key; wait a minute and retry",
                )
            if response.status_code in (400, 404):
                self._raise_api_error(response)
            if response.status_code >= 400:
                snippet = response.text.strip()[:300]
                raise FREDHTTPError(
                    response.status_code, f"HTTP {response.status_code} from {url}: {snippet}"
                )
            try:
                body = response.json()
            except (json.JSONDecodeError, ValueError) as exc:
                raise FREDHTTPError(
                    response.status_code, f"non-JSON response from {url}: {response.text[:200]!r}"
                ) from exc
            if not isinstance(body, dict):
                raise FREDHTTPError(response.status_code, "unexpected JSON payload (not an object)")
            return body

    def _backoff(self, attempt: int, retry_after: str | None) -> None:
        delay: float
        if retry_after and retry_after.strip().isdigit():
            delay = float(retry_after.strip())
        else:
            delay = min(30.0, 0.5 * (2 ** (attempt - 1))) + random.uniform(0, 0.25)
        log.debug("retrying in %.2fs", delay)
        self._sleep(delay)

    @staticmethod
    def _raise_api_error(response: httpx.Response) -> None:
        message = ""
        try:
            body = response.json()
            if isinstance(body, dict):
                message = str(body.get("error_message", "") or "")
        except (json.JSONDecodeError, ValueError):
            message = response.text.strip()[:300]
        low = message.lower()
        if "api_key" in low or "api key" in low:
            raise FREDConfigError(
                f"FRED API rejected the key: {message}",
                hint=f"check FRED_API_KEY (32 lower-case characters); get one at {SIGNUP_URL}",
            )
        if response.status_code == 404 or any(n in low for n in _NOT_FOUND_NEEDLES):
            raise FREDNotFoundError(response.status_code, message or "not found")
        raise FREDAPIError(response.status_code, message)

    # -- series ---------------------------------------------------------------
    def series_info(self, series_id: str) -> SeriesInfo:
        """Metadata for one series (``/series``)."""
        body = self._request("series", {"series_id": series_id.strip().upper()})
        items = body.get("seriess") or []
        if not items:
            raise FREDNotFoundError(404, f"series {series_id.upper()} does not exist")
        return SeriesInfo.from_api(items[0])

    def observations(
        self,
        series_id: str,
        *,
        start: _dt.date | None = None,
        end: _dt.date | None = None,
        units: str | None = None,
        frequency: str | None = None,
        aggregation: str | None = None,
        realtime_start: _dt.date | None = None,
        realtime_end: _dt.date | None = None,
        sort_order: str = "asc",
        limit: int | None = None,
        output_type: int | None = None,
    ) -> tuple[list[Observation], dict[str, Any]]:
        """Observations of one series (``/series/observations``), paginated as needed.

        Returns the observations and the response's own metadata (``count``,
        ``units``, ``realtime_start``, ...). ``limit`` caps the total; ``None``
        fetches everything in pages of 100,000.
        """
        page_size = LIMITS.observations_per_request
        if limit is not None:
            page_size = min(page_size, max(1, limit))
        params: dict[str, Any] = {
            "series_id": series_id.strip().upper(),
            "observation_start": _iso(start),
            "observation_end": _iso(end),
            "units": units,
            "frequency": frequency,
            "aggregation_method": aggregation,
            "realtime_start": _iso(realtime_start),
            "realtime_end": _iso(realtime_end),
            "sort_order": sort_order,
            "output_type": output_type,
            "limit": page_size,
        }
        rows: list[Observation] = []
        meta: dict[str, Any] = {}
        offset = 0
        while True:
            body = self._request("series/observations", {**params, "offset": offset})
            if not meta:
                meta = {k: v for k, v in body.items() if k != "observations"}
            page = body.get("observations") or []
            for raw in page:
                obs = Observation.from_api(raw)
                if obs is not None:
                    rows.append(obs)
            count = int(body.get("count") or 0)
            offset += len(page)
            if not page or offset >= count or (limit is not None and len(rows) >= limit):
                break
        if limit is not None:
            rows = rows[:limit]
        return rows, meta

    def fetch(
        self,
        series_ids: Sequence[str],
        *,
        start: _dt.date | None = None,
        end: _dt.date | None = None,
        units: str | None = None,
        frequency: str | None = None,
        aggregation: str | None = None,
        as_of: _dt.date | None = None,
        latest: bool = False,
        meta: bool = False,
    ) -> DataResponse:
        """Fetch observations for one or more series (one request per series).

        Unknown series do not raise: they are reported through ``messages`` /
        ``on_message`` and omitted. With ``latest`` only the newest observation
        of each series is requested. ``as_of`` fetches the values as they were
        known on that date (ALFRED).
        """
        ids = _dedupe([s.strip().upper() for s in series_ids if s and s.strip()])
        if not ids:
            raise ValueError("at least one series id is required")
        if start and end and end < start:
            raise ValueError(f"end date {end} precedes start date {start}")
        if aggregation and not frequency:
            raise ValueError("aggregation requires a frequency")
        result = DataResponse(
            params={
                k: v
                for k, v in {
                    "observation_start": _iso(start),
                    "observation_end": _iso(end),
                    "units": units,
                    "frequency": frequency,
                    "aggregation_method": aggregation,
                    "realtime_start": _iso(as_of),
                    "realtime_end": _iso(as_of),
                }.items()
                if v
            }
        )
        for sid in ids:
            series = Series(series_id=sid)
            try:
                rows, _ = self.observations(
                    sid,
                    start=start,
                    end=end,
                    units=units,
                    frequency=frequency,
                    aggregation=aggregation,
                    realtime_start=as_of,
                    realtime_end=as_of,
                    sort_order="desc" if latest else "asc",
                    limit=1 if latest else None,
                )
                result.request_count += 1
            except FREDNotFoundError as exc:
                result.request_count += 1
                self._message(result, f"series {sid} does not exist ({exc.detail})")
                continue
            series.data = rows
            series.sort()
            if meta:
                with contextlib.suppress(FREDNotFoundError):
                    series.info = self.series_info(sid)
                result.request_count += 1
            result.series.append(series)
        return result

    def _message(self, result: DataResponse, text: str) -> None:
        result.messages.append(text)
        if self.on_message:
            self.on_message(text)

    def search(
        self,
        text: str,
        *,
        search_type: str = "full_text",
        limit: int = 20,
        offset: int = 0,
        order_by: str | None = None,
        sort_order: str | None = None,
        filter_variable: str | None = None,
        filter_value: str | None = None,
        tag_names: Sequence[str] | None = None,
        exclude_tag_names: Sequence[str] | None = None,
    ) -> tuple[list[SeriesInfo], int]:
        """Full-text (or id) search (``/series/search``); returns the hits and the total count."""
        body = self._request(
            "series/search",
            {
                "search_text": text,
                "search_type": search_type,
                "limit": min(max(1, limit), LIMITS.search_results_per_request),
                "offset": offset,
                "order_by": order_by,
                "sort_order": sort_order,
                "filter_variable": filter_variable,
                "filter_value": filter_value,
                "tag_names": ";".join(tag_names) if tag_names else None,
                "exclude_tag_names": ";".join(exclude_tag_names) if exclude_tag_names else None,
            },
        )
        hits = [SeriesInfo.from_api(s) for s in body.get("seriess") or []]
        return hits, int(body.get("count") or len(hits))

    def vintage_dates(self, series_id: str) -> list[_dt.date]:
        """Every date on which the series was revised or released (``/series/vintagedates``)."""
        dates: list[_dt.date] = []
        offset = 0
        while True:
            body = self._request(
                "series/vintagedates",
                {"series_id": series_id.strip().upper(), "limit": 10000, "offset": offset},
            )
            page = body.get("vintage_dates") or []
            for raw in page:
                d = _dt.date.fromisoformat(str(raw))
                dates.append(d)
            count = int(body.get("count") or 0)
            offset += len(page)
            if not page or offset >= count:
                break
        return dates

    def updates(self, *, limit: int = 100, offset: int = 0) -> list[SeriesInfo]:
        """Series sorted by when they were last updated (``/series/updates``)."""
        body = self._request(
            "series/updates", {"limit": min(max(1, limit), 1000), "offset": offset}
        )
        return [SeriesInfo.from_api(s) for s in body.get("seriess") or []]

    # -- releases -------------------------------------------------------------
    def releases(self) -> list[Release]:
        """All releases (``/releases``), paginated."""
        out: list[Release] = []
        offset = 0
        while True:
            body = self._request("releases", {"limit": 1000, "offset": offset})
            page = body.get("releases") or []
            out.extend(Release.from_api(r) for r in page)
            count = int(body.get("count") or 0)
            offset += len(page)
            if not page or offset >= count:
                break
        return out

    def release(self, release_id: int) -> Release:
        body = self._request("release", {"release_id": release_id})
        items = body.get("releases") or []
        if not items:
            raise FREDNotFoundError(404, f"release {release_id} does not exist")
        return Release.from_api(items[0])

    def release_series(
        self, release_id: int, *, limit: int = 1000, offset: int = 0
    ) -> tuple[list[SeriesInfo], int]:
        body = self._request(
            "release/series",
            {"release_id": release_id, "limit": min(max(1, limit), 1000), "offset": offset},
        )
        hits = [SeriesInfo.from_api(s) for s in body.get("seriess") or []]
        return hits, int(body.get("count") or len(hits))

    def release_dates(
        self, start: _dt.date, end: _dt.date, *, include_no_data: bool = True
    ) -> list[ReleaseDate]:
        """Release dates between ``start`` and ``end`` inclusive (``/releases/dates``)."""
        out: list[ReleaseDate] = []
        offset = 0
        while True:
            body = self._request(
                "releases/dates",
                {
                    "realtime_start": _iso(start),
                    "realtime_end": _iso(end),
                    "include_release_dates_with_no_data": "true" if include_no_data else "false",
                    "order_by": "release_date",
                    "sort_order": "asc",
                    "limit": 1000,
                    "offset": offset,
                },
            )
            page = body.get("release_dates") or []
            for raw in page:
                rd = ReleaseDate.from_api(raw)
                if rd is not None:
                    out.append(rd)
            count = int(body.get("count") or 0)
            offset += len(page)
            if not page or offset >= count:
                break
        return out

    # -- categories and sources ------------------------------------------------
    def category(self, category_id: int) -> Category:
        body = self._request("category", {"category_id": category_id})
        items = body.get("categories") or []
        if not items:
            raise FREDNotFoundError(404, f"category {category_id} does not exist")
        return Category.from_api(items[0])

    def category_children(self, category_id: int = 0) -> list[Category]:
        body = self._request("category/children", {"category_id": category_id})
        return [Category.from_api(c) for c in body.get("categories") or []]

    def category_series(
        self, category_id: int, *, limit: int = 1000, offset: int = 0
    ) -> tuple[list[SeriesInfo], int]:
        body = self._request(
            "category/series",
            {"category_id": category_id, "limit": min(max(1, limit), 1000), "offset": offset},
        )
        hits = [SeriesInfo.from_api(s) for s in body.get("seriess") or []]
        return hits, int(body.get("count") or len(hits))

    def sources(self) -> list[Source]:
        body = self._request("sources", {"limit": 1000})
        return [Source.from_api(s) for s in body.get("sources") or []]


def _dedupe(items: Iterable[str]) -> list[str]:
    seen: set[str] = set()
    out: list[str] = []
    for item in items:
        if item not in seen:
            seen.add(item)
            out.append(item)
    return out


def current_year() -> int:
    return datetime.now(tz=timezone.utc).year


def today() -> _dt.date:
    return datetime.now(tz=timezone.utc).date()
