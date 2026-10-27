"""``dismal bls data`` and ``dismal bls latest``: fetch observations."""

from __future__ import annotations

from pathlib import Path
from typing import Annotated, Optional

import typer

from dismal.bls.cli._common import (
    State,
    build_client,
    collect_series_ids,
    emit_json,
    emit_records,
    get_state,
    handle_errors,
    parse_columns,
    resolve_format,
    select_columns,
    warn,
)
from dismal.bls.client import current_year
from dismal.bls.errors import BLSNoDataError
from dismal.bls.filters import ObservationFilter
from dismal.bls.output import OutputFormat
from dismal.bls.periods import Frequency, YearMonth, parse_date_spec
from dismal.bls.records import to_records, to_wide

SERIES_ARG = Annotated[
    Optional[list[str]],  # noqa: UP045 - typer needs Optional at runtime
    typer.Argument(
        help="BLS series ids, e.g. LNS14000000 CUUR0000SA0 (comma or space separated).",
        metavar="SERIES_ID...",
        show_default=False,
    ),
]
SERIES_FILE_OPT = Annotated[
    Optional[Path],  # noqa: UP045
    typer.Option(
        "--series-file",
        "-S",
        help="Read additional series ids from a file (one per line, # comments) or '-' for stdin.",
        show_default=False,
    ),
]
FORMAT_OPT = Annotated[
    Optional[OutputFormat],  # noqa: UP045
    typer.Option(
        "--format",
        "-f",
        help="Output format. Default: table on a terminal, json otherwise (or $BLS_FORMAT).",
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
COLUMNS_OPT = Annotated[
    Optional[str],  # noqa: UP045
    typer.Option(
        "--columns", help="Comma-separated subset/order of columns to emit.", show_default=False
    ),
]


def _resolve_years(
    start: str | None,
    end: str | None,
    years: int | None,
    latest: bool,
) -> tuple[int | None, int | None, YearMonth | None, YearMonth | None]:
    """Translate the date flags into API years and client-side month bounds."""
    if years is not None and (start or end):
        raise typer.BadParameter("--years cannot be combined with --start/--end")
    if years is not None and years < 1:
        raise typer.BadParameter("--years must be at least 1")
    if latest and (start or end or years):
        raise typer.BadParameter(
            "--latest returns only the newest observation; drop the date flags"
        )
    if latest:
        return None, None, None, None
    this_year = current_year()
    if years is not None:
        return this_year - years + 1, this_year, None, None
    lo = parse_date_spec(start) if start else None
    hi = parse_date_spec(end, end=True) if end else None
    if lo and hi and hi < lo:
        raise typer.BadParameter(f"--end {hi} precedes --start {lo}")
    if lo and hi:
        return lo.year, hi.year, lo, hi
    if lo:
        return lo.year, max(this_year, lo.year), lo, None
    if hi:
        return hi.year - 2, hi.year, None, hi  # mirrors the API's default three-year span
    return None, None, None, None


def _run_data(
    ctx: typer.Context,
    series: list[str] | None,
    series_file: Path | None,
    *,
    start: str | None,
    end: str | None,
    years: int | None,
    latest: bool,
    frequency: list[Frequency] | None,
    annual_average: bool,
    catalog: bool,
    calculations: bool,
    aspects: bool,
    layout: str,
    descending: bool,
    raw: bool,
    strict: bool,
    fmt: OutputFormat | None,
    output: Path | None,
    columns: str | None,
) -> None:
    state: State = get_state(ctx)
    ids = collect_series_ids(series or [], series_file)
    start_year, end_year, lo, hi = _resolve_years(start, end, years, latest)
    if layout not in {"long", "wide"}:
        raise typer.BadParameter("--layout must be 'long' or 'wide'")
    out_fmt = resolve_format(state, fmt)
    if raw and out_fmt not in {OutputFormat.JSON}:
        if fmt is None:
            out_fmt = OutputFormat.JSON
        else:
            raise typer.BadParameter("--raw only supports --format json")
    if catalog and not state.settings.has_api_key:
        warn(
            state, "--catalog needs a registration key (BLS_API_KEY); the API ignores it otherwise"
        )

    with build_client(state) as client:
        if len(ids) > client.limits.series_per_request:
            warn(
                state,
                f"{len(ids)} series exceed the per-request limit of "
                f"{client.limits.series_per_request}; splitting into multiple requests",
            )
        response = client.fetch(
            ids,
            start_year=start_year,
            end_year=end_year,
            latest=latest,
            catalog=catalog,
            calculations=calculations,
            annual_average=annual_average,
            aspects=aspects,
        )

    # Annual-average rows (M13/Q05/S03) carry frequency "annual", so a frequency
    # filter already decides whether they survive; no special casing needed.
    flt = ObservationFilter(
        start=lo,
        end=hi,
        frequencies=frozenset(frequency) if frequency else None,
    )
    series_list = flt.apply(response.series)

    empty = [sid for sid in ids if not any(s.series_id == sid and s.data for s in series_list)]
    for sid in empty:
        warn(state, f"no observations returned for {sid}")
    if strict and empty:
        raise BLSNoDataError(
            f"{len(empty)} series returned no data: {', '.join(empty)}",
            hint="check the ids with `dismal bls search` or widen the date range",
        )

    if descending:
        for s in series_list:
            s.data.reverse()

    if raw:
        response.series = series_list
        emit_json(state, response.to_api_dict(), output)
        return

    records = to_records(
        series_list,
        include_catalog=catalog,
        include_calculations=calculations,
        include_aspects=aspects,
        include_annual_average_flag=annual_average,
    )
    if layout == "wide":
        records = to_wide(records)
        if descending:
            records.reverse()
    cols = select_columns(records, parse_columns(columns))
    emit_records(state, records, out_fmt, output, columns=cols, title="BLS data")


def register(app: typer.Typer) -> None:
    @app.command("data", rich_help_panel="Data")
    @handle_errors
    def data(
        ctx: typer.Context,
        series: SERIES_ARG = None,
        series_file: SERIES_FILE_OPT = None,
        start: Annotated[
            Optional[str],  # noqa: UP045
            typer.Option(
                "--start",
                "-s",
                help="Inclusive start: YYYY, YYYY-MM, YYYY-Qn or YYYY-Hn.",
                show_default=False,
            ),
        ] = None,
        end: Annotated[
            Optional[str],  # noqa: UP045
            typer.Option(
                "--end",
                "-e",
                help="Inclusive end: YYYY, YYYY-MM, YYYY-Qn or YYYY-Hn.",
                show_default=False,
            ),
        ] = None,
        years: Annotated[
            Optional[int],  # noqa: UP045
            typer.Option(
                "--years",
                "-y",
                help="Shortcut: the last N calendar years including this one.",
                show_default=False,
            ),
        ] = None,
        latest: Annotated[
            bool, typer.Option("--latest", help="Only the most recent observation per series.")
        ] = False,
        frequency: Annotated[
            Optional[list[Frequency]],  # noqa: UP045
            typer.Option(
                "--frequency",
                "-F",
                help=(
                    "Keep only these frequencies (repeatable): "
                    "monthly, quarterly, semiannual, annual."
                ),
                show_default=False,
                case_sensitive=False,
            ),
        ] = None,
        annual_average: Annotated[
            bool,
            typer.Option(
                "--annual-average",
                "-A",
                help="Ask the API for annual-average rows (M13/Q05/S03) and flag them.",
            ),
        ] = False,
        catalog: Annotated[
            bool,
            typer.Option(
                "--catalog",
                "-c",
                help="Include catalog metadata (title, survey...). Needs an API key.",
            ),
        ] = False,
        calculations: Annotated[
            bool,
            typer.Option("--calculations", help="Include 1/3/6/12-period net and percent changes."),
        ] = False,
        aspects: Annotated[
            bool, typer.Option("--aspects", help="Include 'aspects' metadata.")
        ] = False,
        layout: Annotated[
            str,
            typer.Option(
                "--layout",
                "-L",
                help=(
                    "long: one row per series & period. "
                    "wide: one row per period, a column per series."
                ),
            ),
        ] = "long",
        descending: Annotated[
            bool,
            typer.Option("--descending", help="Newest observations first (default: oldest first)."),
        ] = False,
        raw: Annotated[
            bool,
            typer.Option(
                "--raw", help="Emit the API-shaped JSON (after filtering) instead of records."
            ),
        ] = False,
        strict: Annotated[
            bool,
            typer.Option(
                "--strict", help="Exit with status 6 if any requested series returned no data."
            ),
        ] = False,
        fmt: FORMAT_OPT = None,
        output: OUTPUT_OPT = None,
        columns: COLUMNS_OPT = None,
    ) -> None:
        """Fetch observations for one or more series.

        Examples:

          dismal bls data LNS14000000 --start 2020-01 --end 2024-12

          dismal bls data CUUR0000SA0 CUSR0000SA0 --years 5 --layout wide -f csv -o cpi.csv

          dismal bls data CES0000000001 --calculations --latest
        """
        _run_data(
            ctx,
            series,
            series_file,
            start=start,
            end=end,
            years=years,
            latest=latest,
            frequency=frequency,
            annual_average=annual_average,
            catalog=catalog,
            calculations=calculations,
            aspects=aspects,
            layout=layout,
            descending=descending,
            raw=raw,
            strict=strict,
            fmt=fmt,
            output=output,
            columns=columns,
        )

    @app.command("latest", rich_help_panel="Data")
    @handle_errors
    def latest(
        ctx: typer.Context,
        series: SERIES_ARG = None,
        series_file: SERIES_FILE_OPT = None,
        catalog: Annotated[
            bool,
            typer.Option("--catalog", "-c", help="Include catalog metadata. Needs an API key."),
        ] = False,
        calculations: Annotated[
            bool, typer.Option("--calculations", help="Include net and percent changes.")
        ] = False,
        strict: Annotated[
            bool,
            typer.Option("--strict", help="Exit with status 6 if any series returned no data."),
        ] = False,
        fmt: FORMAT_OPT = None,
        output: OUTPUT_OPT = None,
        columns: COLUMNS_OPT = None,
    ) -> None:
        """Fetch only the newest observation of each series (alias for `data --latest`)."""
        _run_data(
            ctx,
            series,
            series_file,
            start=None,
            end=None,
            years=None,
            latest=True,
            frequency=None,
            annual_average=False,
            catalog=catalog,
            calculations=calculations,
            aspects=False,
            layout="long",
            descending=False,
            raw=False,
            strict=strict,
            fmt=fmt,
            output=output,
            columns=columns,
        )
