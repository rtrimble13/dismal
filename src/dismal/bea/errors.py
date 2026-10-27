"""Exception hierarchy and process exit codes.

Every error raised by this package derives from :class:`BEAError` and carries an
``exit_code`` so the CLI can map failures to stable, documented exit statuses
(see ``docs/agents.md``). ``ExitCode`` is shared by every source and lives in
:mod:`dismal.core.errors`; it is re-exported here for convenience.
"""

from __future__ import annotations

from dismal.core.errors import DismalError, ExitCode


class BEAError(DismalError):
    """Base class for all errors raised by the BEA source."""


class BEAConfigError(BEAError):
    """Configuration is missing or invalid (most often: no API key)."""

    exit_code = ExitCode.CONFIG


class BEANetworkError(BEAError):
    """The request never produced an HTTP response."""

    exit_code = ExitCode.NETWORK


class BEAHTTPError(BEAError):
    """The server answered with a non-success HTTP status or a non-JSON body."""

    exit_code = ExitCode.API

    def __init__(self, status_code: int, message: str, *, hint: str | None = None) -> None:
        super().__init__(message, hint=hint)
        self.status_code = status_code


class BEAAPIError(BEAError):
    """The API returned an ``Error`` object instead of results."""

    exit_code = ExitCode.API

    def __init__(self, code: str, description: str, *, hint: str | None = None) -> None:
        label = f"BEA API error {code}" if code else "BEA API error"
        super().__init__(f"{label}: {description or 'no detail provided'}", hint=hint)
        self.code = code
        self.description = description


class BEAQuotaError(BEAAPIError):
    """A rate limit was exceeded (BEA then blocks the key for an hour)."""

    exit_code = ExitCode.QUOTA


class BEANoDataError(BEAError):
    """Raised in ``--strict`` mode when a request returned no observations."""

    exit_code = ExitCode.NO_DATA


__all__ = [
    "BEAAPIError",
    "BEAConfigError",
    "BEAError",
    "BEAHTTPError",
    "BEANetworkError",
    "BEANoDataError",
    "BEAQuotaError",
    "ExitCode",
]
