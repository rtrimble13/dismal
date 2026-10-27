"""HTTP client for the BEA Data API.

Highlights
----------
* One method per API method: ``GetDataSetList``, ``GetParameterList``,
  ``GetParameterValues``, ``GetParameterValuesFiltered`` and ``GetData``.
* **Retries** with exponential back-off for transport errors, HTTP 429 and 5xx.
* Normalised **error handling**: the API's ``Error`` object raises
  :class:`~dismal.bea.errors.BEAAPIError`; rate-limit problems raise
  :class:`~dismal.bea.errors.BEAQuotaError`; a rejected key raises
  :class:`~dismal.bea.errors.BEAConfigError`.
* :meth:`BEAClient.fetch` issues one ``GetData`` request per table and merges
  the results into typed :class:`~dismal.bea.models.Series`.

Every call needs a registered key (``BEA_API_KEY``); BEA has no anonymous
access. Limits: 100 requests, 100 MB and 30 errors per minute per key; a key
that exceeds them is blocked for one hour.
"""

from __future__ import annotations

import json
import logging
import random
import time
from collections.abc import Callable, Iterable, Mapping, Sequence
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any

import httpx

from dismal.bea.config import (
    DEFAULT_BASE_URL,
    DEFAULT_MAX_RETRIES,
    DEFAULT_TIMEOUT,
    SIGNUP_URL,
    Settings,
)
from dismal.bea.datasets import canonical_name
from dismal.bea.errors import (
    BEAAPIError,
    BEAConfigError,
    BEAHTTPError,
    BEANetworkError,
    BEAQuotaError,
)
from dismal.bea.models import DataResponse, Dataset, Note, Parameter, Series, group_rows

log = logging.getLogger("dismal.bea.client")

_RETRY_STATUSES = {429, 500, 502, 503, 504}
_QUOTA_NEEDLES = ("exceed", "throttl", "rate limit", "too many", "blocked", "limit of")
_KEY_NEEDLES = ("userid", "user id", "api key", "registration")
_KEY_PROBLEMS = ("invalid", "not valid", "not registered", "required", "missing", "unknown")


@dataclass(frozen=True)
class Limits:
    """Per-minute limits published by BEA (per key)."""

    requests_per_minute: int = 100
    megabytes_per_minute: int = 100
    errors_per_minute: int = 30
    block_minutes: int = 60


LIMITS = Limits()


def _as_list(value: Any) -> list[Any]:
    """BEA serialises single elements as objects instead of one-element lists."""
    if value is None or value == "":
        return []
    if isinstance(value, list):
        return value
    return [value]


def _is_quota_message(text: str) -> bool:
    low = text.lower()
    return any(n in low for n in _QUOTA_NEEDLES)


def _is_key_message(text: str) -> bool:
    low = text.lower()
    return any(n in low for n in _KEY_NEEDLES) and any(p in low for p in _KEY_PROBLEMS)


class BEAClient:
    """Thin, synchronous client for the BEA Data API.

    Parameters
    ----------
    api_key:
        The 36-character *UserID* issued at https://apps.bea.gov/API/signup/.
        Required by the API for every call.
    transport:
        Optional :class:`httpx.BaseTransport` (e.g. ``httpx.MockTransport``) used
        for testing.
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
        sleep: Callable[[float], None] = time.sleep,
    ) -> None:
        self.api_key = api_key or None
        self.base_url = base_url.rstrip("/")
        self.max_retries = max(0, max_retries)
        self._sleep = sleep
        headers = {"Accept": "application/json"}
        if user_agent:
            headers["User-Agent"] = user_agent
        self._http = httpx.Client(timeout=timeout, headers=headers, transport=transport)
        self.request_count = 0

    @classmethod
    def from_settings(
        cls, settings: Settings, *, transport: httpx.BaseTransport | None = None
    ) -> BEAClient:
        return cls(
            settings.api_key,
            base_url=settings.base_url,
            timeout=settings.timeout,
            max_retries=settings.max_retries,
            user_agent=settings.user_agent,
            transport=transport,
        )

    # -- lifecycle -----------------------------------------------------------
    def close(self) -> None:
        self._http.close()

    def __enter__(self) -> BEAClient:
        return self

    def __exit__(self, *exc: object) -> None:
        self.close()

    # -- limits ---------------------------------------------------------------
    @property
    def limits(self) -> Limits:
        return LIMITS

    # -- low level ------------------------------------------------------------
    def _request(self, params: Mapping[str, str]) -> dict[str, Any]:
        """Perform one GET with retries and return the decoded ``BEAAPI`` object."""
        attempt = 0
        shown = {k: v for k, v in params.items() if k != "UserID"}
        while True:
            attempt += 1
            self.request_count += 1
            log.debug("GET %s attempt=%d params=%s", self.base_url, attempt, shown)
            try:
                response = self._http.get(self.base_url, params=dict(params))
            except httpx.TimeoutException as exc:
                if attempt <= self.max_retries:
                    self._backoff(attempt, None)
                    continue
                raise BEANetworkError(
                    f"request to {self.base_url} timed out",
                    hint="increase BEA_TIMEOUT or retry later",
                ) from exc
            except httpx.HTTPError as exc:
                if attempt <= self.max_retries:
                    self._backoff(attempt, None)
                    continue
                raise BEANetworkError(
                    f"could not reach {self.base_url}: {exc}",
                    hint="check network connectivity and proxy settings",
                ) from exc

            if response.status_code in _RETRY_STATUSES and attempt <= self.max_retries:
                self._backoff(attempt, response.headers.get("Retry-After"))
                continue
            if response.status_code == 429:
                raise BEAQuotaError(
                    "HTTP 429",
                    "rate limited by apps.bea.gov",
                    hint="BEA blocks a key for one hour after more than 100 requests, "
                    "100 MB or 30 errors in a minute; wait before retrying",
                )
            if response.status_code >= 400:
                snippet = response.text.strip()[:300]
                raise BEAHTTPError(
                    response.status_code,
                    f"HTTP {response.status_code} from {self.base_url}: {snippet}",
                )
            try:
                body = response.json()
            except (json.JSONDecodeError, ValueError) as exc:
                raise BEAHTTPError(
                    response.status_code,
                    f"non-JSON response from {self.base_url}: {response.text[:200]!r}",
                ) from exc
            if not isinstance(body, dict):
                raise BEAHTTPError(response.status_code, "unexpected JSON payload (not an object)")
            api = body.get("BEAAPI", body)
            if not isinstance(api, dict):
                raise BEAHTTPError(response.status_code, "unexpected JSON payload (no BEAAPI)")
            return api

    def _backoff(self, attempt: int, retry_after: str | None) -> None:
        delay: float
        if retry_after and retry_after.strip().isdigit():
            delay = float(retry_after.strip())
        else:
            delay = min(30.0, 0.5 * (2 ** (attempt - 1))) + random.uniform(0, 0.25)
        log.debug("retrying in %.2fs", delay)
        self._sleep(delay)

    @staticmethod
    def _raise_for_error(error: Mapping[str, Any]) -> None:
        code = str(error.get("APIErrorCode", "") or "")
        description = str(error.get("APIErrorDescription", "") or "")
        detail = error.get("ErrorDetail")
        if isinstance(detail, Mapping) and detail.get("Description"):
            description = f"{description} ({detail['Description']})".strip()
        if _is_quota_message(description):
            raise BEAQuotaError(
                code,
                description,
                hint="BEA allows 100 requests, 100 MB and 30 errors per minute per key and "
                "blocks the key for an hour when exceeded",
            )
        if _is_key_message(description):
            raise BEAConfigError(
                f"BEA API error {code}: {description}",
                hint=f"check BEA_API_KEY; register a key at {SIGNUP_URL}",
            )
        raise BEAAPIError(code, description)

    def _results(self, method: str, **params: str) -> dict[str, Any]:
        """Call ``method`` and return the ``Results`` object (raising on API errors)."""
        query: dict[str, str] = {"method": method, "ResultFormat": "JSON"}
        if self.api_key:
            query["UserID"] = self.api_key
        query.update({k: v for k, v in params.items() if v is not None})
        api = self._request(query)
        error = api.get("Error")
        if isinstance(error, Mapping):
            self._raise_for_error(error)
        results = api.get("Results")
        if isinstance(results, list):
            for item in results:
                if isinstance(item, Mapping) and isinstance(item.get("Error"), Mapping):
                    self._raise_for_error(item["Error"])
            dicts = [r for r in results if isinstance(r, dict)]
            results = dicts[0] if dicts else {}
        if not isinstance(results, dict):
            results = {}
        error = results.get("Error")
        if isinstance(error, Mapping):
            self._raise_for_error(error)
        return results

    # -- endpoints ------------------------------------------------------------
    def datasets(self) -> list[Dataset]:
        """List the datasets the API exposes (``GetDataSetList``)."""
        results = self._results("GetDataSetList")
        items = [Dataset.from_api(d) for d in _as_list(results.get("Dataset"))]
        return [d for d in items if d.name]

    def parameters(self, dataset: str) -> list[Parameter]:
        """List the parameters of a dataset (``GetParameterList``)."""
        results = self._results("GetParameterList", datasetname=canonical_name(dataset))
        items = [Parameter.from_api(p) for p in _as_list(results.get("Parameter"))]
        return [p for p in items if p.name]

    def parameter_values(self, dataset: str, parameter: str) -> list[dict[str, Any]]:
        """Valid values of one parameter (``GetParameterValues``), as raw dicts."""
        results = self._results(
            "GetParameterValues", datasetname=canonical_name(dataset), ParameterName=parameter
        )
        return [dict(v) for v in _as_list(results.get("ParamValue")) if isinstance(v, Mapping)]

    def parameter_values_filtered(
        self, dataset: str, target: str, filters: Mapping[str, str]
    ) -> list[dict[str, Any]]:
        """Valid values of ``target`` given other parameters (``GetParameterValuesFiltered``)."""
        results = self._results(
            "GetParameterValuesFiltered",
            datasetname=canonical_name(dataset),
            TargetParameter=target,
            **dict(filters),
        )
        return [dict(v) for v in _as_list(results.get("ParamValue")) if isinstance(v, Mapping)]

    def get_data(self, dataset: str, params: Mapping[str, str]) -> DataResponse:
        """One ``GetData`` request, grouped into series (sorted chronologically)."""
        name = canonical_name(dataset)
        clean = {k: str(v) for k, v in params.items() if v is not None and str(v) != ""}
        results = self._results("GetData", datasetname=name, **clean)
        series = group_rows(name, _as_list(results.get("Data")))
        for s in series:
            s.sort()
        notes = [Note.from_api(n) for n in _as_list(results.get("Notes")) if isinstance(n, Mapping)]
        dims = [dict(d) for d in _as_list(results.get("Dimensions")) if isinstance(d, Mapping)]
        statistic = results.get("Statistic")
        production = results.get("UTCProductionTime")
        return DataResponse(
            dataset=name,
            series=series,
            notes=notes,
            dimensions=dims,
            params=clean,
            statistic=str(statistic) if statistic is not None else None,
            production_time=str(production) if production is not None else None,
            request_count=1,
        )

    def fetch(
        self,
        dataset: str,
        params: Mapping[str, str],
        *,
        table_param: str | None = None,
        tables: Sequence[str] | None = None,
    ) -> DataResponse:
        """Fetch data, issuing one request per table in ``tables`` and merging the results.

        ``table_param`` names the parameter that carries the table (``TableName``
        or ``TableID``). Without ``tables`` a single request is made with
        ``params`` as given.
        """
        name = canonical_name(dataset)
        wanted = _dedupe([t.strip() for t in (tables or []) if t and t.strip()])
        if wanted and not table_param:
            raise ValueError("table_param is required when tables are given")
        requests: list[tuple[str | None, dict[str, str]]] = []
        if wanted:
            for table in wanted:
                requests.append((table, {**dict(params), str(table_param): table}))
        else:
            requests.append((None, dict(params)))

        merged = DataResponse(dataset=name, params={k: str(v) for k, v in params.items()})
        by_id: dict[str, Series] = {}
        note_refs: set[str] = set()
        for source, req in requests:
            part = self.get_data(name, req)
            merged.request_count += part.request_count
            if not merged.dimensions:
                merged.dimensions = part.dimensions
            merged.statistic = merged.statistic or part.statistic
            merged.production_time = merged.production_time or part.production_time
            for note in part.notes:
                if note.ref not in note_refs:
                    note_refs.add(note.ref)
                    merged.notes.append(note)
            for s in part.series:
                if source is not None:
                    merged.series_tables.setdefault(s.series_id, set()).add(source)
                if s.series_id in by_id:
                    by_id[s.series_id].merge(s)
                else:
                    by_id[s.series_id] = s
        merged.series = list(by_id.values())
        for s in merged.series:
            s.sort()
        if wanted:
            merged.params[str(table_param)] = ",".join(wanted)
        return merged


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
