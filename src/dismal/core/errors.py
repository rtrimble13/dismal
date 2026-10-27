"""Exit codes and the exception base class shared by every source.

Every error raised by a source package derives from :class:`DismalError` and
carries an ``exit_code`` so the CLI can map failures to stable, documented exit
statuses (see ``docs/agents.md``). The sources define their own subclasses
(``BLSError``, ``BEAError``, ``FREDError`` and their specialisations) so library
users can catch errors per API or all at once.
"""

from __future__ import annotations

from enum import IntEnum


class ExitCode(IntEnum):
    """Process exit codes used by the ``dismal`` CLI (identical for every source)."""

    OK = 0
    ERROR = 1  # unexpected / generic failure
    USAGE = 2  # bad arguments (also used by the argument parser)
    API = 3  # the API answered but reported a failure
    QUOTA = 4  # daily threshold or rate limit exceeded
    NETWORK = 5  # transport-level problem: DNS, timeout, TLS, connection reset
    NO_DATA = 6  # --strict was given and at least one series/table returned nothing
    CONFIG = 7  # missing/invalid configuration (e.g. no API key where one is required)


class DismalError(Exception):
    """Base class for all errors raised by any source package."""

    exit_code: ExitCode = ExitCode.ERROR

    def __init__(self, message: str, *, hint: str | None = None) -> None:
        super().__init__(message)
        self.message = message
        self.hint = hint

    def __str__(self) -> str:
        return self.message


class PeriodError(ValueError):
    """A date, period or frequency string could not be parsed (a usage error)."""
