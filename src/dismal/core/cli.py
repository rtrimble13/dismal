"""CLI plumbing shared by every source: state, logging, output selection, error mapping.

The per-source ``cli._common`` modules import from here and add what is
specific to their API (building a client, parsing ids or parameters).
"""

from __future__ import annotations

import functools
import logging
import platform
import re
import sys
from collections.abc import Callable, Iterable, Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import Any, TypeVar

import httpx
import typer

from dismal.core.cache import FileCache
from dismal.core.errors import DismalError, ExitCode, PeriodError
from dismal.core.output import OutputFormat, write_json, write_records
from dismal.core.records import Record, first_seen_columns

F = TypeVar("F", bound=Callable[..., Any])
ST = TypeVar("ST", bound="State")

PROG = "dismal"


@dataclass
class State:
    """Per-invocation state stored on the root Typer context.

    The ``dismal`` root command creates a bare state (no ``settings``); the
    source subcommand that runs next promotes it to its own subclass, which
    carries that source's ``Settings``. Tests inject a mock ``transport`` here.
    """

    settings: Any = None
    source: str = ""
    verbose: int = 0
    quiet: bool = False
    transport: httpx.BaseTransport | None = None

    @property
    def prog(self) -> str:
        """The program name used as a prefix on stderr: ``dismal`` or ``dismal bls``."""
        return f"{PROG} {self.source}" if self.source else PROG


def get_state(ctx: typer.Context, cls: type[ST]) -> ST:
    """Return the state of type ``cls`` for this invocation, creating or promoting it.

    A state of another type (the bare root state) is replaced by a fresh ``cls``
    instance that inherits its ``verbose``, ``quiet`` and ``transport``.
    """
    root = ctx.find_root()
    obj = root.obj
    if isinstance(obj, cls):
        return obj
    state = cls()
    if isinstance(obj, State):
        state.verbose = obj.verbose
        state.quiet = obj.quiet
        state.transport = obj.transport
    root.obj = state
    return state


def configure_logging(verbose: int) -> None:
    if verbose <= 0:
        return
    logging.basicConfig(
        level=logging.DEBUG, stream=sys.stderr, format="%(name)s: %(message)s", force=True
    )
    if verbose < 2:
        logging.getLogger("httpx").setLevel(logging.WARNING)
        logging.getLogger("httpcore").setLevel(logging.WARNING)


def warn(state: State, message: str) -> None:
    if not state.quiet:
        sys.stderr.write(f"{state.prog}: warning: {message}\n")
        sys.stderr.flush()


def info(state: State, message: str) -> None:
    if not state.quiet:
        sys.stderr.write(f"{state.prog}: {message}\n")
        sys.stderr.flush()


def resolve_format(
    state: State, fmt: OutputFormat | None, *, allow_table: bool = True, env_name: str = "FORMAT"
) -> OutputFormat:
    """Pick the output format: flag > ``<PREFIX>_FORMAT`` > table on a TTY, else JSON."""
    if fmt is not None:
        return fmt
    default_format = state.settings.default_format if state.settings is not None else None
    if default_format:
        try:
            return OutputFormat(default_format)
        except ValueError as exc:
            raise typer.BadParameter(
                f"{env_name}={default_format!r} is not one of "
                + ", ".join(f.value for f in OutputFormat)
            ) from exc
    if allow_table and sys.stdout.isatty():
        return OutputFormat.TABLE
    return OutputFormat.JSON


def emit_records(
    state: State,
    records: Sequence[Record],
    fmt: OutputFormat,
    output: Path | None,
    *,
    columns: Sequence[str] | None = None,
    title: str | None = None,
    column_order: Callable[[Sequence[Record]], list[str]] = first_seen_columns,
) -> None:
    cols = list(columns) if columns else column_order(records)
    no_color = bool(state.settings.no_color) if state.settings is not None else False
    write_records(
        records,
        fmt,
        None if output is None else str(output),
        columns=cols,
        title=title,
        no_color=no_color,
    )
    if output is not None and str(output) != "-":
        info(state, f"wrote {len(records)} row(s) to {output}")


def emit_json(state: State, obj: Any, output: Path | None) -> None:
    write_json(obj, None if output is None else str(output))
    if output is not None and str(output) != "-":
        info(state, f"wrote {output}")


def error_handler(prog: str) -> Callable[[F], F]:
    """Build a decorator mapping package exceptions to stable exit codes and tidy stderr."""

    def handle_errors(func: F) -> F:
        @functools.wraps(func)
        def wrapper(*args: Any, **kwargs: Any) -> Any:
            try:
                return func(*args, **kwargs)
            except DismalError as exc:
                sys.stderr.write(f"{prog}: error: {exc.message}\n")
                if exc.hint:
                    sys.stderr.write(f"{prog}: hint: {exc.hint}\n")
                sys.stderr.flush()
                raise typer.Exit(code=int(exc.exit_code)) from exc
            except PeriodError as exc:
                raise typer.BadParameter(str(exc)) from exc
            except BrokenPipeError:  # e.g. `dismal bls data ... | head`
                try:
                    sys.stdout.close()
                finally:
                    raise typer.Exit(code=int(ExitCode.OK)) from None

        return wrapper  # type: ignore[return-value]

    return handle_errors


_SPLIT_RE = re.compile(r"[,\s]+")


def collect_series_ids(args: Iterable[str], series_file: Path | None) -> list[str]:
    """Combine positional ids (comma/space separated) with ids from a file or stdin."""
    ids: list[str] = []
    for arg in args:
        ids.extend(p for p in _SPLIT_RE.split(arg) if p)
    if series_file is not None:
        try:
            text = sys.stdin.read() if str(series_file) == "-" else series_file.read_text("utf-8")
        except OSError as exc:
            raise typer.BadParameter(
                f"cannot read series file {series_file}: {exc.strerror or exc}"
            ) from exc
        for raw_line in text.splitlines():
            line = raw_line.split("#", 1)[0].strip()
            if line:
                ids.extend(p for p in _SPLIT_RE.split(line) if p)
    seen: set[str] = set()
    unique: list[str] = []
    for sid in ids:
        key = sid.upper()
        if key not in seen:
            seen.add(key)
            unique.append(key)
    if not unique:
        raise typer.BadParameter(
            "no series ids given (pass them as arguments or via --series-file)"
        )
    return unique


def parse_columns(spec: str | None) -> list[str] | None:
    if not spec:
        return None
    cols = [c.strip() for c in spec.split(",") if c.strip()]
    return cols or None


def select_columns(
    records: Sequence[Record],
    requested: Sequence[str] | None,
    *,
    column_order: Callable[[Sequence[Record]], list[str]] = first_seen_columns,
) -> list[str]:
    available = column_order(records)
    if not requested:
        return available
    missing = [c for c in requested if c not in available]
    if missing and records:
        raise typer.BadParameter(
            f"unknown column(s): {', '.join(missing)}; available: {', '.join(available)}"
        )
    return list(requested)


# --- Maintenance helpers shared by the per-source and the top-level commands --------------


def cache_records(cache_dir: Path) -> list[Record]:
    """One record per cached file (relative path and size), for ``cache info``."""
    records: list[Record] = []
    if cache_dir.is_dir():
        for p in sorted(cache_dir.rglob("*")):
            if p.is_file():
                records.append({"file": str(p.relative_to(cache_dir)), "bytes": p.stat().st_size})
    return records


def clear_cache(cache_dir: Path) -> int:
    """Delete every cached file under ``cache_dir``; returns the number removed."""
    return FileCache(cache_dir).clear()


def python_check() -> dict[str, Any]:
    return {
        "check": "python",
        "ok": True,
        "detail": f"{platform.python_version()} on {platform.system()}",
    }


def version_line(version: str) -> str:
    return f"{PROG} {version} (python {platform.python_version()})"
