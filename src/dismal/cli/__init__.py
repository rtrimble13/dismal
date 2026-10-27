"""The ``dismal`` command-line interface: one entry point, one subcommand per source.

``dismal bls``, ``dismal bea`` and ``dismal fred`` mount the source apps
unchanged, so every command, flag and output of the former stand-alone tools
is available under its source. The maintenance commands (``config``,
``doctor``, ``cache``, ``version``) exist per source and, aggregated across all
sources, at the top level.
"""

from __future__ import annotations

from pathlib import Path
from typing import Annotated, Any, Optional

import typer

from dismal import SOURCES, __version__
from dismal.bea.cli import app as bea_app
from dismal.bls.cli import app as bls_app
from dismal.core import cli as core
from dismal.core.cli import (
    State,
    cache_records,
    clear_cache,
    configure_logging,
    emit_json,
    emit_records,
    error_handler,
    info,
    python_check,
    resolve_format,
    version_line,
)
from dismal.core.errors import ExitCode
from dismal.core.output import OutputFormat
from dismal.fred.cli import app as fred_app

HELP = (
    "Source U.S. economic data from the command line: the Bureau of Labor Statistics "
    "(`bls`), the Bureau of Economic Analysis (`bea`) and FRED (`fred`), each with the same "
    "set of hooks (`data`, `latest`, `search`, discovery and maintenance commands).\n\n"
    "Run `dismal <source> --help` for a source's commands. API keys come from the "
    "environment only (BLS_API_KEY, BEA_API_KEY, FRED_API_KEY). Output defaults to a table "
    "on a terminal and JSON otherwise; use --format json|jsonl|csv|parquet|table to choose."
)

app = typer.Typer(
    name="dismal",
    help=HELP,
    no_args_is_help=True,
    rich_markup_mode="markdown",
    context_settings={"help_option_names": ["-h", "--help"]},
    pretty_exceptions_enable=False,
)

handle_errors = error_handler(core.PROG)

FORMAT_OPT = Annotated[
    Optional[OutputFormat],  # noqa: UP045
    typer.Option(
        "--format",
        "-f",
        help="Output format. Default: table on a terminal, json otherwise.",
        show_default=False,
        case_sensitive=False,
    ),
]
OUTPUT_OPT = Annotated[
    Optional[Path],  # noqa: UP045
    typer.Option(
        "--output", "-o", help="Write to this file instead of stdout.", show_default=False
    ),
]


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
    state = core.get_state(ctx, State)
    state.verbose = max(state.verbose, verbose)
    state.quiet = state.quiet or quiet
    configure_logging(state.verbose)


app.add_typer(bls_app, name="bls", rich_help_panel="Sources")
app.add_typer(bea_app, name="bea", rich_help_panel="Sources")
app.add_typer(fred_app, name="fred", rich_help_panel="Sources")


# --- Maintenance across all sources ---------------------------------------------------------


def _source_states(root: State) -> dict[str, Any]:
    """One per-source state (with that source's settings) sharing the root's flags."""
    from dismal.bea.cli import _common as bea_common
    from dismal.bls.cli import _common as bls_common
    from dismal.fred.cli import _common as fred_common

    factories = {"bls": bls_common.State, "bea": bea_common.State, "fred": fred_common.State}
    states: dict[str, Any] = {}
    for source in SOURCES:
        try:
            state = factories[source]()
        except ValueError as exc:  # a malformed <SOURCE>_* environment variable
            raise typer.BadParameter(str(exc)) from exc
        state.verbose, state.quiet, state.transport = root.verbose, root.quiet, root.transport
        states[source] = state
    return states


def _meta(source: str) -> Any:
    from dismal.bea.cli import meta as bea_meta
    from dismal.bls.cli import meta as bls_meta
    from dismal.fred.cli import meta as fred_meta

    return {"bls": bls_meta, "bea": bea_meta, "fred": fred_meta}[source]


@app.command("config", rich_help_panel="Maintenance")
@handle_errors
def config(ctx: typer.Context, output: OUTPUT_OPT = None) -> None:
    """Show the effective configuration of every source (API keys are masked)."""
    root = core.get_state(ctx, State)
    states = _source_states(root)
    report = {
        "version": __version__,
        "sources": {src: _meta(src).settings_record(states[src]) for src in SOURCES},
    }
    emit_json(root, report, output)


@app.command("doctor", rich_help_panel="Maintenance")
@handle_errors
def doctor(ctx: typer.Context, output: OUTPUT_OPT = None) -> None:
    """Check configuration and live connectivity for every source (one request each)."""
    root = core.get_state(ctx, State)
    states = _source_states(root)
    sources: dict[str, Any] = {}
    exit_code = ExitCode.OK
    for src in SOURCES:
        report, code = _meta(src).doctor_report(states[src])
        sources[src] = report
        if not report["healthy"] and exit_code is ExitCode.OK:
            exit_code = code
    combined = {
        "version": __version__,
        "python": python_check()["detail"],
        "sources": sources,
        "healthy": all(r["healthy"] for r in sources.values()),
    }
    emit_json(root, combined, output)
    if not combined["healthy"]:
        raise typer.Exit(code=int(exit_code or ExitCode.NETWORK))


cache_app = typer.Typer(
    help="Manage the local metadata caches of every source.", no_args_is_help=True
)
app.add_typer(cache_app, name="cache", rich_help_panel="Maintenance")


@cache_app.command("info")
@handle_errors
def cache_info(ctx: typer.Context, fmt: FORMAT_OPT = None, output: OUTPUT_OPT = None) -> None:
    """List cached files of every source."""
    root = core.get_state(ctx, State)
    states = _source_states(root)
    records = []
    for src in SOURCES:
        for rec in cache_records(states[src].settings.cache_dir):
            records.append({"source": src, **rec})
    emit_records(
        root,
        records,
        resolve_format(root, fmt),
        output,
        columns=["source", "file", "bytes"],
        title="cache",
    )


@cache_app.command("clear")
@handle_errors
def cache_clear(ctx: typer.Context) -> None:
    """Delete all cached metadata of every source."""
    root = core.get_state(ctx, State)
    states = _source_states(root)
    for src in SOURCES:
        cache_dir = states[src].settings.cache_dir
        removed = clear_cache(cache_dir)
        info(root, f"{src}: removed {removed} cached file(s) from {cache_dir}")


@app.command("version", rich_help_panel="Maintenance")
def version(
    short: Annotated[bool, typer.Option("--short", help="Print only the version number.")] = False,
) -> None:
    """Print the version."""
    typer.echo(__version__ if short else version_line(__version__))


def main() -> None:
    """Console-script entry point."""
    app()


__all__ = ["app", "main"]
