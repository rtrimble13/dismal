"""Housekeeping commands for ``dismal bea``: ``config``, ``doctor``, ``cache`` and ``version``.

``settings_record`` and ``doctor_report`` are also used by the top-level
``dismal config`` / ``dismal doctor`` commands, which aggregate every source.
"""

from __future__ import annotations

from typing import Annotated, Any

import typer

from dismal import __version__
from dismal.bea.cli._common import (
    State,
    build_client,
    emit_json,
    emit_records,
    get_state,
    handle_errors,
    info,
    resolve_format,
)
from dismal.bea.cli.data import FORMAT_OPT, OUTPUT_OPT
from dismal.bea.client import LIMITS
from dismal.bea.config import (
    API_KEY_LENGTH,
    ENV_API_KEY,
    ENV_BASE_URL,
    ENV_CACHE_DIR,
    ENV_FORMAT,
    ENV_MAX_RETRIES,
    ENV_TIMEOUT,
    ENV_USER_AGENT,
    SIGNUP_URL,
)
from dismal.bea.errors import BEAError, ExitCode
from dismal.core.cli import cache_records, clear_cache, python_check, version_line

__all__ = ["doctor_report", "register", "settings_record"]


def settings_record(state: State) -> dict[str, Any]:
    """The effective configuration of this source (API key masked)."""
    s = state.settings
    return {
        "source": "bea",
        "version": __version__,
        "api_key": s.masked_api_key(),
        "api_key_env": ENV_API_KEY,
        "base_url": s.base_url,
        "timeout_seconds": s.timeout,
        "max_retries": s.max_retries,
        "cache_dir": str(s.cache_dir),
        "user_agent": s.user_agent,
        "default_format": s.default_format or ("table on a TTY, json otherwise"),
        "limits": {
            "requests_per_minute": LIMITS.requests_per_minute,
            "megabytes_per_minute": LIMITS.megabytes_per_minute,
            "errors_per_minute": LIMITS.errors_per_minute,
            "block_minutes": LIMITS.block_minutes,
        },
        "environment_variables": [
            ENV_API_KEY,
            ENV_BASE_URL,
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
    settings = state.settings
    if not settings.has_api_key:
        key_detail = f"{ENV_API_KEY} not set; the API needs a key ({SIGNUP_URL})"
    elif not settings.api_key_looks_valid:
        key_detail = (
            f"{ENV_API_KEY} is set but has {len(settings.api_key or '')} characters; "
            f"BEA keys have {API_KEY_LENGTH}"
        )
    else:
        key_detail = f"{ENV_API_KEY} is set"
    checks.append({"check": "api_key", "ok": settings.api_key_looks_valid, "detail": key_detail})
    exit_code = ExitCode.OK
    if settings.has_api_key:
        try:
            with build_client(state) as client:
                listed = client.datasets()
            checks.append(
                {
                    "check": "api_reachable",
                    "ok": True,
                    "detail": f"{len(listed)} datasets listed",
                }
            )
        except BEAError as exc:
            checks.append({"check": "api_reachable", "ok": False, "detail": exc.message})
            exit_code = exc.exit_code or ExitCode.NETWORK
    else:
        checks.append({"check": "api_reachable", "ok": False, "detail": "skipped: no API key"})
        exit_code = ExitCode.CONFIG
    checks.append(python_check())
    report["checks"] = checks
    report["healthy"] = all(c["ok"] for c in checks)
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
        """Check configuration and live connectivity to the BEA API (costs one request)."""
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
        """Delete all cached metadata (datasets, parameters, parameter values)."""
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
