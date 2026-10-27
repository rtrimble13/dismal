"""CLI plumbing for the BLS source: state, client construction, column order.

Everything generic (output selection, error mapping, series-id parsing) comes
from :mod:`dismal.core.cli`; this module binds it to the BLS ``Settings``,
``BLSClient`` and record layout.
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass, field
from pathlib import Path

import typer

from dismal.bls.client import BLSClient
from dismal.bls.config import ENV_FORMAT, SOURCE, Settings
from dismal.bls.records import Record, column_order
from dismal.core import cli as core
from dismal.core.cli import (
    collect_series_ids,
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
    "collect_series_ids",
    "configure_logging",
    "emit_json",
    "emit_records",
    "get_state",
    "handle_errors",
    "info",
    "parse_columns",
    "resolve_format",
    "select_columns",
    "warn",
]


@dataclass
class State(core.State):
    """Per-invocation state for ``dismal bls`` (tests inject a mock ``transport``)."""

    settings: Settings = field(default_factory=Settings.from_env)
    source: str = SOURCE


def get_state(ctx: typer.Context) -> State:
    return core.get_state(ctx, State)


handle_errors = error_handler(f"{core.PROG} {SOURCE}")


def build_client(state: State) -> BLSClient:
    """Create a client from the current settings (patched by tests)."""
    return BLSClient.from_settings(
        state.settings,
        transport=state.transport,
        on_message=lambda m: warn(state, m),
    )


def resolve_format(
    state: State, fmt: OutputFormat | None, *, allow_table: bool = True
) -> OutputFormat:
    """Pick the output format: flag > BLS_FORMAT > table on a TTY, else JSON."""
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
