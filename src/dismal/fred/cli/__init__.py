"""The ``dismal fred`` subcommand (built with Typer).

The Typer app defined here is mounted by :mod:`dismal.cli` as ``dismal fred``;
it can also be invoked on its own (``python -m dismal.fred``), which the tests
do.
"""

from __future__ import annotations

from typing import Annotated

import typer

from dismal import __version__
from dismal.fred.cli import data as _data
from dismal.fred.cli import discover as _discover
from dismal.fred.cli import meta as _meta
from dismal.fred.cli._common import State, configure_logging, get_state
from dismal.fred.config import Settings

HELP = (
    "Source data from FRED, the Federal Reserve Bank of St. Louis economic database.\n\n"
    "Set FRED_API_KEY to your 32-character key (free at "
    "https://fred.stlouisfed.org/docs/api/api_key.html); every live request needs it. "
    "Output defaults to a table on a terminal and JSON otherwise; use "
    "--format json|jsonl|csv|parquet|table to choose explicitly."
)

app = typer.Typer(
    name="fred",
    help=HELP,
    no_args_is_help=True,
    rich_markup_mode="markdown",
    context_settings={"help_option_names": ["-h", "--help"]},
    pretty_exceptions_enable=False,
)


def _version_callback(value: bool) -> None:
    if value:
        typer.echo(f"dismal {__version__}")
        raise typer.Exit()


@app.callback()
def _root(
    ctx: typer.Context,
    verbose: Annotated[
        int,
        typer.Option(
            "--verbose", "-v", count=True, help="Log HTTP activity to stderr (-vv for wire-level)."
        ),
    ] = 0,
    quiet: Annotated[
        bool, typer.Option("--quiet", "-q", help="Suppress warnings and notes on stderr.")
    ] = False,
    version: Annotated[
        bool,
        typer.Option(
            "--version",
            "-V",
            callback=_version_callback,
            is_eager=True,
            help="Show version and exit.",
        ),
    ] = False,
) -> None:
    try:
        state: State = get_state(ctx)
        state.settings = Settings.from_env()
    except ValueError as exc:  # a malformed FRED_* environment variable
        raise typer.BadParameter(str(exc)) from exc
    # Flags given before the source (``dismal -v fred ...``) are already on the state.
    state.verbose = max(state.verbose, verbose)
    state.quiet = state.quiet or quiet
    configure_logging(state.verbose)


_data.register(app)
_discover.register(app)
_meta.register(app)


def main() -> None:
    """Entry point for ``python -m dismal.fred``."""
    app()


__all__ = ["HELP", "app", "main"]
