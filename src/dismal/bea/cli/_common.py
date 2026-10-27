"""CLI plumbing for the BEA source: state, client construction, parameter parsing.

Everything generic (output selection, error mapping, column selection) comes
from :mod:`dismal.core.cli`; this module binds it to the BEA ``Settings``,
``BEAClient`` and record layout, and adds ``Key=Value`` parameter parsing.
"""

from __future__ import annotations

from collections.abc import Iterable, Sequence
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import typer

from dismal.bea.client import BEAClient
from dismal.bea.config import ENV_API_KEY, ENV_FORMAT, SIGNUP_URL, SOURCE, Settings
from dismal.bea.errors import BEAConfigError
from dismal.bea.records import Record, column_order
from dismal.core import cli as core
from dismal.core.cli import (
    configure_logging,
    emit_json,
    error_handler,
    info,
    parse_columns,
    warn,
)
from dismal.core.output import OutputFormat

__all__ = [
    "State",
    "build_client",
    "configure_logging",
    "emit_json",
    "emit_records",
    "get_state",
    "handle_errors",
    "info",
    "parse_columns",
    "parse_params",
    "require_api_key",
    "resolve_format",
    "select_columns",
    "values_to_records",
    "warn",
]


@dataclass
class State(core.State):
    """Per-invocation state for ``dismal bea`` (tests inject a mock ``transport``)."""

    settings: Settings = field(default_factory=Settings.from_env)
    source: str = SOURCE


def get_state(ctx: typer.Context) -> State:
    return core.get_state(ctx, State)


handle_errors = error_handler(f"{core.PROG} {SOURCE}")


def require_api_key(state: State) -> None:
    """Every live request needs a key; fail early with a clear hint when it is missing."""
    if not state.settings.has_api_key:
        raise BEAConfigError(
            f"{ENV_API_KEY} is not set; the BEA API requires a registered UserID for every request",
            hint=f"register (free) at {SIGNUP_URL} and export {ENV_API_KEY}=<36-character key>",
        )


def build_client(state: State) -> BEAClient:
    """Create a client from the current settings (patched by tests)."""
    require_api_key(state)
    return BEAClient.from_settings(state.settings, transport=state.transport)


def resolve_format(
    state: State, fmt: OutputFormat | None, *, allow_table: bool = True
) -> OutputFormat:
    """Pick the output format: flag > BEA_FORMAT > table on a TTY, else JSON."""
    return core.resolve_format(state, fmt, allow_table=allow_table, env_name=ENV_FORMAT)


def emit_records(
    state: State,
    records: Sequence[Record],
    fmt: OutputFormat,
    output: Path | None,
    *,
    columns: Sequence[str] | None = None,
    title: str | None = None,
) -> None:
    core.emit_records(
        state, records, fmt, output, columns=columns, title=title, column_order=column_order
    )


def select_columns(records: Sequence[Record], requested: Sequence[str] | None) -> list[str]:
    return core.select_columns(records, requested, column_order=column_order)


def parse_params(items: Iterable[str]) -> dict[str, str]:
    """Parse ``Key=Value`` strings (repeatable) into a dict; later keys win, case-insensitively."""
    out: dict[str, str] = {}
    for item in items:
        if "=" not in item:
            raise typer.BadParameter(
                f"expected PARAMETER=VALUE, got {item!r} (e.g. TableName=T10101)"
            )
        key, value = item.split("=", 1)
        key, value = key.strip(), value.strip()
        if not key:
            raise typer.BadParameter(f"empty parameter name in {item!r}")
        for existing in list(out):
            if existing.lower() == key.lower():
                del out[existing]
        out[key] = value
    return out


def values_to_records(values: Sequence[dict[str, Any]]) -> list[Record]:
    """Normalise ``GetParameterValues`` rows to ``key``/``description`` plus the raw columns.

    BEA names the columns differently per parameter (``Key``/``Desc``,
    ``TableName``/``Description``, ``FrequencyID``/``Description``, ...).
    """
    records: list[Record] = []
    for row in values:
        cols = list(row)
        key_col = next((c for c in cols if c.lower() == "key"), cols[0] if cols else None)
        desc_col = next(
            (c for c in cols if c != key_col and c.lower().endswith(("desc", "description"))),
            None,
        )
        rec: Record = {
            "key": "" if key_col is None else str(row[key_col]).strip(),
            "description": "" if desc_col is None else str(row[desc_col]).strip(),
        }
        for c in cols:
            if c not in {key_col, desc_col}:
                rec[c] = row[c]
        records.append(rec)
    return records
