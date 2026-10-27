"""Housekeeping commands for ``dismal bls``: ``config``, ``doctor``, ``cache`` and ``version``.

``settings_record`` and ``doctor_report`` are also used by the top-level
``dismal config`` / ``dismal doctor`` commands, which aggregate every source.
"""

from __future__ import annotations

from typing import Annotated, Any

import typer

from dismal import __version__
from dismal.bls.cli._common import (
    State,
    build_client,
    emit_json,
    emit_records,
    get_state,
    handle_errors,
    info,
    resolve_format,
)
from dismal.bls.cli.data import FORMAT_OPT, OUTPUT_OPT
from dismal.bls.config import (
    ENV_API_KEY,
    ENV_BASE_URL,
    ENV_CACHE_DIR,
    ENV_FLATFILE_BASE_URL,
    ENV_FORMAT,
    ENV_MAX_RETRIES,
    ENV_TIMEOUT,
    ENV_USER_AGENT,
)
from dismal.bls.errors import BLSError, ExitCode
from dismal.core.cli import cache_records, clear_cache, python_check, version_line

__all__ = ["doctor_report", "register", "settings_record"]


def settings_record(state: State) -> dict[str, Any]:
    """The effective configuration of this source (API key masked)."""
    s = state.settings
    with build_client(state) as client:
        limits = client.limits
    return {
        "source": "bls",
        "version": __version__,
        "api_key": s.masked_api_key(),
        "api_key_env": ENV_API_KEY,
        "base_url": s.base_url,
        "flatfile_base_url": s.flatfile_base_url,
        "timeout_seconds": s.timeout,
        "max_retries": s.max_retries,
        "cache_dir": str(s.cache_dir),
        "user_agent": s.user_agent,
        "default_format": s.default_format or ("table on a TTY, json otherwise"),
        "limits": {
            "series_per_request": limits.series_per_request,
            "years_per_request": limits.years_per_request,
            "daily_requests": limits.daily_requests,
        },
        "environment_variables": [
            ENV_API_KEY,
            ENV_BASE_URL,
            ENV_FLATFILE_BASE_URL,
            ENV_TIMEOUT,
            ENV_MAX_RETRIES,
            ENV_CACHE_DIR,
            ENV_USER_AGENT,
            ENV_FORMAT,
        ],
    }


def doctor_report(state: State) -> tuple[dict[str, Any], ExitCode]:
    """Run the configuration and connectivity checks; returns the report and an exit code."""
    report = settings_record(state)
    checks: list[dict[str, Any]] = []
    checks.append(
        {
            "check": "api_key",
            "ok": state.settings.has_api_key,
            "detail": f"{ENV_API_KEY} is set"
            if state.settings.has_api_key
            else f"{ENV_API_KEY} not set: 25 requests/day, 25 series and 10 years per request",
        }
    )
    exit_code = ExitCode.OK
    try:
        with build_client(state) as client:
            surveys = client.surveys()
        checks.append(
            {"check": "api_reachable", "ok": True, "detail": f"{len(surveys)} surveys listed"}
        )
    except BLSError as exc:
        checks.append({"check": "api_reachable", "ok": False, "detail": exc.message})
        exit_code = ExitCode.NETWORK
    checks.append(python_check())
    report["checks"] = checks
    report["healthy"] = all(c["ok"] for c in checks if c["check"] != "api_key")
    return report, exit_code


def register(app: typer.Typer) -> None:
    @app.command("config", rich_help_panel="Maintenance")
    @handle_errors
    def config(ctx: typer.Context, output: OUTPUT_OPT = None) -> None:
        """Show the effective configuration (the API key is masked)."""
        state = get_state(ctx)
        emit_json(state, settings_record(state), output)

    @app.command("doctor", rich_help_panel="Maintenance")
    @handle_errors
    def doctor(ctx: typer.Context, output: OUTPUT_OPT = None) -> None:
        """Check configuration and live connectivity to the BLS API (costs one request)."""
        state = get_state(ctx)
        report, exit_code = doctor_report(state)
        emit_json(state, report, output)
        if not report["healthy"]:
            raise typer.Exit(code=int(exit_code))

    cache_app = typer.Typer(help="Manage the local metadata cache.", no_args_is_help=True)
    app.add_typer(cache_app, name="cache", rich_help_panel="Maintenance")

    @cache_app.command("info")
    @handle_errors
    def cache_info(ctx: typer.Context, fmt: FORMAT_OPT = None, output: OUTPUT_OPT = None) -> None:
        """List cached files."""
        state = get_state(ctx)
        root = state.settings.cache_dir
        emit_records(
            state, cache_records(root), resolve_format(state, fmt), output, title=f"cache: {root}"
        )

    @cache_app.command("clear")
    @handle_errors
    def cache_clear(ctx: typer.Context) -> None:
        """Delete all cached metadata (surveys, flat files)."""
        state = get_state(ctx)
        removed = clear_cache(state.settings.cache_dir)
        info(state, f"removed {removed} cached file(s) from {state.settings.cache_dir}")

    @app.command("version", rich_help_panel="Maintenance")
    def version(
        short: Annotated[
            bool, typer.Option("--short", help="Print only the version number.")
        ] = False,
    ) -> None:
        """Print the version."""
        typer.echo(__version__ if short else version_line(__version__))
