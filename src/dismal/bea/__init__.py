"""dismal.bea - the BEA source of ``dismal``: a typed client and CLI for the BEA Data API.

The package exposes a small, typed Python API (:class:`dismal.bea.client.BEAClient`)
and the ``dismal bea`` subcommand built on top of it. See the README for usage.
"""

from __future__ import annotations

from dismal import __version__
from dismal.bea.client import BEAClient
from dismal.bea.config import Settings
from dismal.bea.errors import (
    BEAAPIError,
    BEAConfigError,
    BEAError,
    BEAHTTPError,
    BEANetworkError,
    BEAQuotaError,
)
from dismal.bea.models import DataResponse, Dataset, Note, Observation, Parameter, Series
from dismal.bea.periods import Frequency

__all__ = [
    "BEAAPIError",
    "BEAClient",
    "BEAConfigError",
    "BEAError",
    "BEAHTTPError",
    "BEANetworkError",
    "BEAQuotaError",
    "DataResponse",
    "Dataset",
    "Frequency",
    "Note",
    "Observation",
    "Parameter",
    "Series",
    "Settings",
    "__version__",
]
