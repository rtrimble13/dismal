"""HTTP client for the BLS Public Data API v2.

Highlights
----------
* Transparent **chunking**: requests for more series or more years than the API
  accepts in a single call are split into several calls and merged.
* **Retries** with exponential back-off for transport errors, HTTP 429 and 5xx.
* Normalised **error handling**: API-level failures (``status`` other than
  ``REQUEST_SUCCEEDED``) raise :class:`~dismal.bls.errors.BLSAPIError`; quota problems
  raise :class:`~dismal.bls.errors.BLSQuotaError`.
* Works with or without a registration key (``BLS_API_KEY``), applying the
  corresponding request limits automatically.

Only the ``/timeseries/data`` (POST), ``/timeseries/popular``, ``/surveys`` and
``/surveys/{abbr}`` endpoints exist in v2; this client covers all of them.
"""

from __future__ import annotations

import json
import logging
import random
import time
from collections.abc import Callable, Iterable, Iterator, Sequence
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any

import httpx

from dismal.bls.config import DEFAULT_BASE_URL, DEFAULT_MAX_RETRIES, DEFAULT_TIMEOUT, Settings
from dismal.bls.errors import BLSAPIError, BLSHTTPError, BLSNetworkError, BLSQuotaError
from dismal.bls.models import DataResponse, Series, Survey
from dismal.bls.periods import sort_key

log = logging.getLogger("dismal.bls.client")

STATUS_OK = "REQUEST_SUCCEEDED"
_RETRY_STATUSES = {429, 500, 502, 503, 504}


@dataclass(frozen=True)
class Limits:
    """Per-request and per-day limits published by BLS for API v2."""

    series_per_request: int
    years_per_request: int
    daily_requests: int


REGISTERED_LIMITS = Limits(series_per_request=50, years_per_request=20, daily_requests=500)
UNREGISTERED_LIMITS = Limits(series_per_request=25, years_per_request=10, daily_requests=25)


def chunked(items: Sequence[str], size: int) -> Iterator[list[str]]:
    for i in range(0, len(items), size):
        yield list(items[i : i + size])


def year_windows(start_year: int, end_year: int, size: int) -> Iterator[tuple[int, int]]:
    """Split an inclusive year range into windows of at most ``size`` years."""
    if end_year < start_year:
        raise ValueError(f"end year {end_year} precedes start year {start_year}")
    year = start_year
    while year <= end_year:
        stop = min(year + size - 1, end_year)
        yield year, stop
        year = stop + 1


def _is_quota_message(messages: Iterable[str]) -> bool:
    needles = ("threshold", "too many requests", "rate limit", "exceeded")
    return any(any(n in m.lower() for n in needles) for m in messages)


class BLSClient:
    """Thin, synchronous client for the BLS Public Data API.

    Parameters
    ----------
    api_key:
        Registration key. ``None`` uses the API unauthenticated with the lower
        limits BLS imposes on unregistered users.
    transport:
        Optional :class:`httpx.BaseTransport` (e.g. ``httpx.MockTransport``) used
        for testing.
    on_message:
        Callback invoked with each informational message the API returns on a
        successful request (e.g. *"No Data Available for Series X Year: 2026"*).
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
        self._http = httpx.Client(
            base_url=self.base_url, timeout=timeout, headers=headers, transport=transport
        )
        self.request_count = 0

    @classmethod
    def from_settings(
        cls,
        settings: Settings,
        *,
        transport: httpx.BaseTransport | None = None,
        on_message: Callable[[str], None] | None = None,
    ) -> BLSClient:
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

    def __enter__(self) -> BLSClient:
        return self

    def __exit__(self, *exc: object) -> None:
        self.close()

    # -- limits ---------------------------------------------------------------
    @property
    def limits(self) -> Limits:
        return REGISTERED_LIMITS if self.api_key else UNREGISTERED_LIMITS

    # -- low level ------------------------------------------------------------
    def _request(self, method: str, path: str, **kwargs: Any) -> dict[str, Any]:
        """Perform one HTTP request with retries and return the decoded JSON body."""
        attempt = 0
        while True:
            attempt += 1
            self.request_count += 1
            log.debug("%s %s attempt=%d params=%s", method, path, attempt, kwargs.get("params"))
            try:
                response = self._http.request(method, path, **kwargs)
            except httpx.TimeoutException as exc:
                if attempt <= self.max_retries:
                    self._backoff(attempt, None)
                    continue
                raise BLSNetworkError(
                    f"request to {self.base_url}{path} timed out",
                    hint="increase BLS_TIMEOUT or retry later",
                ) from exc
            except httpx.HTTPError as exc:
                if attempt <= self.max_retries:
                    self._backoff(attempt, None)
                    continue
                raise BLSNetworkError(
                    f"could not reach {self.base_url}{path}: {exc}",
                    hint="check network connectivity and proxy settings",
                ) from exc

            if response.status_code in _RETRY_STATUSES and attempt <= self.max_retries:
                self._backoff(attempt, response.headers.get("Retry-After"))
                continue
            if response.status_code == 429:
                raise BLSQuotaError(
                    "HTTP 429",
                    ["rate limited by api.bls.gov"],
                    hint="wait and retry; registered keys allow 500 requests per day",
                )
            if response.status_code >= 400:
                snippet = response.text.strip()[:300]
                raise BLSHTTPError(
                    response.status_code,
                    f"HTTP {response.status_code} from {self.base_url}{path}: {snippet}",
                )
            try:
                body = response.json()
            except (json.JSONDecodeError, ValueError) as exc:
                raise BLSHTTPError(
                    response.status_code,
                    f"non-JSON response from {self.base_url}{path}: {response.text[:200]!r}",
                ) from exc
            if not isinstance(body, dict):
                raise BLSHTTPError(response.status_code, "unexpected JSON payload (not an object)")
            return body

    def _backoff(self, attempt: int, retry_after: str | None) -> None:
        delay: float
        if retry_after and retry_after.strip().isdigit():
            delay = float(retry_after.strip())
        else:
            delay = min(30.0, 0.5 * (2 ** (attempt - 1))) + random.uniform(0, 0.25)
        log.debug("retrying in %.2fs", delay)
        self._sleep(delay)

    def _check_status(self, body: dict[str, Any]) -> list[str]:
        status = str(body.get("status", ""))
        messages = [str(m) for m in body.get("message") or []]
        if status != STATUS_OK:
            if _is_quota_message(messages) or status == "REQUEST_NOT_PROCESSED":
                raise BLSQuotaError(
                    status,
                    messages,
                    hint="the daily request threshold may be exhausted; "
                    "set BLS_API_KEY for 500 requests/day",
                )
            raise BLSAPIError(status, messages)
        return messages

    # -- endpoints ------------------------------------------------------------
    def fetch(
        self,
        series_ids: Sequence[str],
        *,
        start_year: int | None = None,
        end_year: int | None = None,
        latest: bool = False,
        catalog: bool = False,
        calculations: bool = False,
        annual_average: bool = False,
        aspects: bool = False,
    ) -> DataResponse:
        """Fetch observations for one or more series.

        Requests exceeding the per-call limits are split by series and by year
        window and the results merged. The API itself fills in a default range
        (the three most recent years) when neither year is given.
        """
        ids = _dedupe([s.strip().upper() for s in series_ids if s and s.strip()])
        if not ids:
            raise ValueError("at least one series id is required")
        if (start_year is None) != (end_year is None):
            raise ValueError("start_year and end_year must be given together")
        if start_year is not None and end_year is not None and end_year < start_year:
            raise ValueError(f"end year {end_year} precedes start year {start_year}")
        if catalog and not self.api_key:
            log.debug("catalog metadata requires a registration key; the API will ignore it")

        windows: list[tuple[int, int] | None]
        if start_year is None or end_year is None or latest:
            windows = [None]
        else:
            windows = list(year_windows(start_year, end_year, self.limits.years_per_request))

        result = DataResponse()
        by_id: dict[str, Series] = {}
        for id_chunk in chunked(ids, self.limits.series_per_request):
            for window in windows:
                payload: dict[str, Any] = {"seriesid": id_chunk}
                if window is not None:
                    payload["startyear"] = str(window[0])
                    payload["endyear"] = str(window[1])
                if latest:
                    payload["latest"] = "true"
                if catalog:
                    payload["catalog"] = "true"
                if calculations:
                    payload["calculations"] = "true"
                if annual_average:
                    payload["annualaverage"] = "true"
                if aspects:
                    payload["aspects"] = "true"
                if self.api_key:
                    payload["registrationkey"] = self.api_key
                body = self._request(
                    "POST",
                    "/timeseries/data/",
                    json=payload,
                    headers={"Content-Type": "application/json"},
                )
                messages = self._check_status(body)
                for m in messages:
                    result.messages.append(m)
                    if self.on_message:
                        self.on_message(m)
                result.request_count += 1
                rt = body.get("responseTime")
                if isinstance(rt, int):
                    result.response_time_ms += rt
                for raw in (body.get("Results") or {}).get("series") or []:
                    series = Series.from_api(raw)
                    if series.series_id in by_id:
                        by_id[series.series_id].merge(series)
                    else:
                        by_id[series.series_id] = series
        # Preserve the caller's ordering; append any unexpected extras.
        result.series = [by_id[i] for i in ids if i in by_id] + [
            s for i, s in by_id.items() if i not in ids
        ]
        for s in result.series:
            s.data.sort(key=lambda o: sort_key(o.year, o.period))
        return result

    def surveys(self) -> list[Survey]:
        """List all surveys (data sets) exposed by the API."""
        body = self._request("GET", "/surveys", params=self._key_params())
        self._check_status(body)
        raw = (body.get("Results") or {}).get("survey") or []
        return [Survey.from_api(s) for s in raw]

    def survey(self, abbreviation: str) -> dict[str, Any]:
        """Return the raw metadata object for one survey."""
        abbr = abbreviation.strip().upper()
        body = self._request("GET", f"/surveys/{abbr}", params=self._key_params())
        self._check_status(body)
        results = body.get("Results") or {}
        survey = results.get("survey")
        if isinstance(survey, list):
            return dict(survey[0]) if survey else {}
        return dict(survey or results)

    def popular(self, survey: str | None = None) -> list[str]:
        """Return the series ids BLS currently lists as popular (optionally per survey)."""
        params = self._key_params()
        if survey:
            params["survey"] = survey.strip().upper()
        body = self._request("GET", "/timeseries/popular", params=params)
        self._check_status(body)
        raw = (body.get("Results") or {}).get("series") or []
        return [str(s.get("seriesID")) for s in raw if s.get("seriesID")]

    def _key_params(self) -> dict[str, str]:
        return {"registrationkey": self.api_key} if self.api_key else {}


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
