"""dismal.bls - the BLS source of ``dismal``: a typed client and CLI for the BLS Public Data API.

The package exposes a small, typed Python API (:class:`dismal.bls.client.BLSClient`)
and the ``dismal bls`` subcommand built on top of it. See the README for usage.
"""

from __future__ import annotations

from dismal import __version__
from dismal.bls.client import BLSClient
from dismal.bls.config import Settings
from dismal.bls.errors import (
    BLSAPIError,
    BLSError,
    BLSHTTPError,
    BLSNetworkError,
    BLSQuotaError,
)
from dismal.bls.models import DataResponse, Observation, Series, Survey
from dismal.bls.periods import Frequency

__all__ = [
    "BLSAPIError",
    "BLSClient",
    "BLSError",
    "BLSHTTPError",
    "BLSNetworkError",
    "BLSQuotaError",
    "DataResponse",
    "Frequency",
    "Observation",
    "Series",
    "Settings",
    "Survey",
    "__version__",
]
