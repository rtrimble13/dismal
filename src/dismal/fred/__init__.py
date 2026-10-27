"""dismal.fred - the FRED source of ``dismal``: a typed client and CLI for the FRED API.

The package exposes a small, typed Python API (:class:`dismal.fred.client.FREDClient`)
and the ``dismal fred`` subcommand built on top of it. See the README for usage.
"""

from __future__ import annotations

from dismal import __version__
from dismal.fred.client import FREDClient
from dismal.fred.config import Settings
from dismal.fred.errors import (
    FREDAPIError,
    FREDConfigError,
    FREDError,
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
from dismal.fred.periods import Frequency

__all__ = [
    "Category",
    "DataResponse",
    "FREDAPIError",
    "FREDClient",
    "FREDConfigError",
    "FREDError",
    "FREDHTTPError",
    "FREDNetworkError",
    "FREDNotFoundError",
    "FREDQuotaError",
    "Frequency",
    "Observation",
    "Release",
    "ReleaseDate",
    "Series",
    "SeriesInfo",
    "Settings",
    "Source",
    "__version__",
]
