"""Discovery of *every* series in a survey via BLS flat files.

The JSON API has no endpoint that lists series ids. BLS publishes complete
series directories as tab-delimited text at
``https://download.bls.gov/pub/time.series/<survey>/<survey>.series``; this
module downloads, caches and parses them so ``dismal bls series list`` can offer
exhaustive, fuzzy-searchable discovery (``docs/adr/0010-flat-file-discovery.md``).

BLS blocks requests without a descriptive ``User-Agent``; set ``BLS_USER_AGENT``
to something like ``"my-project (me@example.com)"`` if you receive HTTP 403.
"""

from __future__ import annotations

import csv
import io
import logging
from collections.abc import Callable
from typing import Any

import httpx

from dismal.bls.cache import FileCache
from dismal.bls.config import Settings
from dismal.bls.errors import BLSHTTPError, BLSNetworkError

log = logging.getLogger("dismal.bls.flatfiles")

FLATFILE_TTL_SECONDS = 30 * 24 * 3600


def flatfile_url(base_url: str, survey: str, name: str | None = None) -> str:
    prefix = survey.lower()
    return f"{base_url.rstrip('/')}/{prefix}/{name or prefix + '.series'}"


def fetch_series_file(
    survey: str,
    settings: Settings,
    *,
    refresh: bool = False,
    transport: httpx.BaseTransport | None = None,
    progress: Callable[[str], None] | None = None,
) -> str:
    """Return the raw ``<survey>.series`` text, from cache when fresh."""
    cache = FileCache(settings.cache_dir / "flatfiles")
    name = f"{survey.lower()}.series"
    if not refresh and cache.is_fresh(name, FLATFILE_TTL_SECONDS):
        cached = cache.read_text(name)
        if cached:
            return cached
    url = flatfile_url(settings.flatfile_base_url, survey)
    if progress:
        progress(f"downloading {url}")
    headers = {"User-Agent": settings.user_agent, "Accept": "text/plain, */*"}
    try:
        with httpx.Client(timeout=max(settings.timeout, 120.0), transport=transport) as http:
            resp = http.get(url, headers=headers, follow_redirects=True)
    except httpx.HTTPError as exc:
        raise BLSNetworkError(f"could not download {url}: {exc}") from exc
    if resp.status_code == 403:
        raise BLSHTTPError(
            403,
            f"download.bls.gov refused the request (HTTP 403) for {url}",
            hint="BLS requires a descriptive User-Agent with contact info; "
            'set BLS_USER_AGENT="my-tool (you@example.com)"',
        )
    if resp.status_code == 404:
        raise BLSHTTPError(
            404,
            f"no series directory found for survey {survey.upper()!r} ({url})",
            hint="check the survey abbreviation with `dismal bls surveys`",
        )
    if resp.status_code >= 400:
        raise BLSHTTPError(resp.status_code, f"HTTP {resp.status_code} downloading {url}")
    text = resp.text
    cache.write_text(name, text)
    return text


def parse_series_file(text: str) -> list[dict[str, Any]]:
    """Parse a tab-delimited ``.series`` file into dicts with stripped values."""
    reader = csv.reader(io.StringIO(text), delimiter="\t")
    rows: list[dict[str, Any]] = []
    header: list[str] | None = None
    for raw in reader:
        if not raw or all(not c.strip() for c in raw):
            continue
        cells = [c.strip() for c in raw]
        if header is None:
            header = [c.strip() for c in cells]
            continue
        if len(cells) < len(header):
            cells += [""] * (len(header) - len(cells))
        rows.append(dict(zip(header, cells[: len(header)], strict=False)))
    return rows


def series_title_of(row: dict[str, Any]) -> str:
    """Best-effort title: ``series_title`` when present, else the other descriptive columns."""
    title = row.get("series_title")
    if title:
        return str(title)
    skip = {"series_id", "footnote_codes", "begin_year", "begin_period", "end_year", "end_period"}
    parts = [str(v) for k, v in row.items() if k not in skip and v and not k.endswith("_code")]
    return " ".join(parts)
