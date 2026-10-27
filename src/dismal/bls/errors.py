"""Exception hierarchy and process exit codes.

Every error raised by this package derives from :class:`BLSError` and carries an
``exit_code`` so the CLI can map failures to stable, documented exit statuses
(see ``docs/agents.md``). ``ExitCode`` is shared by every source and lives in
:mod:`dismal.core.errors`; it is re-exported here for convenience.
"""

from __future__ import annotations

from dismal.core.errors import DismalError, ExitCode


class BLSError(DismalError):
    """Base class for all errors raised by the BLS source."""


class BLSConfigError(BLSError):
    """Configuration is missing or invalid."""

    exit_code = ExitCode.CONFIG


class BLSNetworkError(BLSError):
    """The request never produced an HTTP response."""

    exit_code = ExitCode.NETWORK


class BLSHTTPError(BLSError):
    """The server answered with a non-success HTTP status."""

    exit_code = ExitCode.API

    def __init__(self, status_code: int, message: str, *, hint: str | None = None) -> None:
        super().__init__(message, hint=hint)
        self.status_code = status_code


class BLSAPIError(BLSError):
    """The API returned ``status != REQUEST_SUCCEEDED``."""

    exit_code = ExitCode.API

    def __init__(self, status: str, messages: list[str], *, hint: str | None = None) -> None:
        detail = "; ".join(messages) if messages else "no detail provided"
        super().__init__(f"BLS API request failed ({status}): {detail}", hint=hint)
        self.status = status
        self.messages = messages


class BLSQuotaError(BLSAPIError):
    """The daily request threshold (or a rate limit) was exceeded."""

    exit_code = ExitCode.QUOTA


class BLSNoDataError(BLSError):
    """Raised in ``--strict`` mode when a requested series returned no observations."""

    exit_code = ExitCode.NO_DATA


__all__ = [
    "BLSAPIError",
    "BLSConfigError",
    "BLSError",
    "BLSHTTPError",
    "BLSNetworkError",
    "BLSNoDataError",
    "BLSQuotaError",
    "ExitCode",
]
