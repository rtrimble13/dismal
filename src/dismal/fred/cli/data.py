"""``dismal fred data`` and ``dismal fred latest``: fetch observations."""

from __future__ import annotations

import datetime as _dt
from pathlib import Path
from typing import Annotated, Optional

import typer

from dismal.fred.cli._common import (
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
from dismal.fred.client import LIMITS, current_year
from dismal.fred.errors import FREDNoDataError
from dismal.fred.output import OutputFormat
from dismal.fred.periods import (
    normalise_aggregation,
    normalise_frequency,
    normalise_units,
    parse_date_spec,
    parse_iso_date,
)
from dismal.fred.records import to_records, to_wide

SERIES_ARG = Annotated[
    Optional[list[str]],  # noqa: UP045 - typer needs Optional at runtime
    typer.Argument(
        help="FRED series ids, e.g. UNRATE CPIAUCSL DGS10 (comma or space separated).",
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
        help="Output format. Default: table on a terminal, json otherwise (or $FRED_FORMAT).",
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
UNITS_OPT = Annotated[
    Optional[str],  # noqa: UP045
    typer.Option(
        "--units",
        "-u",
        help=(
            "Transformation applied by the API: lin (levels), chg, ch1 (change from a year "
            "ago), pch, pc1 (percent change from a year ago), pca, cch, cca, log."
        ),
        show_default=False,
    ),
]
FREQUENCY_OPT = Annotated[
    Optional[str],  # noqa: UP045
    typer.Option(
        "--frequency",
        "-F",
        help=(
            "Aggregate to a lower frequency: d, w, bw, m, q, sa, a (or daily ... annual); "
            "week-ending codes such as wef pass through."
        ),
        show_default=False,
    ),
]
AGGREGATION_OPT = Annotated[
    Optional[str],  # noqa: UP045
    typer.Option(
        "--aggregation",
        help="How --frequency aggregates: avg (default), sum or eop (end of period).",
        show_default=False,
    ),
]
AS_OF_OPT = Annotated[
    Optional[str],  # noqa: UP045
    typer.Option(
        "--as-of",
        help=(
            "Values as they were known on this date (YYYY-MM-DD), from ALFRED; adds "
            "realtime_start/realtime_end columns."
        ),
        show_default=False,
    ),
]
META_OPT = Annotated[
    bool,
    typer.Option(
        "--meta",
        "-m",
        help="Add title, units, frequency, seasonal_adjustment and last_updated columns "
        "(one extra request per series).",
    ),
]
STRICT_OPT = Annotated[
    bool,
    typer.Option("--strict", help="Exit with status 6 if any requested series returned no data."),
]


def _resolve_dates(
    start: str | None, end: str | None, years: int | None, latest: bool
) -> tuple[_dt.date | None, _dt.date | None]:
    """Translate the date flags into observation_start/observation_end dates."""
    if years is not None and (start or end):
        raise typer.BadParameter("--years cannot be combined with --start/--end")
    if years is not None and years < 1:
        raise typer.BadParameter("--years must be at least 1")
    if latest and (start or end or years):
        raise typer.BadParameter(
            "--latest returns only the newest observation; drop the date flags"
        )
    if years is not None:
        return _dt.date(current_year() - years + 1, 1, 1), None
    lo = parse_date_spec(start).start if start else None
    hi = parse_date_spec(end).end if end else None
    if lo and hi and hi < lo:
        raise typer.BadParameter(f"--end {hi} precedes --start {lo}")
    return lo, hi


def _run_data(
    ctx: typer.Context,
    series: list[str] | None,
    series_file: Path | None,
    *,
    start: str | None,
    end: str | None,
    years: int | None,
    latest: bool,
    units: str | None,
    frequency: str | None,
    aggregation: str | None,
    as_of: str | None,
    meta: bool,
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
    lo, hi = _resolve_dates(start, end, years, latest)
    if layout not in {"long", "wide"}:
        raise typer.BadParameter("--layout must be 'long' or 'wide'")
    out_fmt = resolve_format(state, fmt)
    if raw and out_fmt is not OutputFormat.JSON:
        if fmt is None:
            out_fmt = OutputFormat.JSON
        else:
            raise typer.BadParameter("--raw only supports --format json")
    units_code = normalise_units(units) if units else None
    freq_code = normalise_frequency(frequency) if frequency else None
    agg_code = normalise_aggregation(aggregation) if aggregation else None
    if agg_code and not freq_code:
        raise typer.BadParameter("--aggregation needs --frequency")
    vintage = parse_iso_date(as_of) if as_of else None

    with build_client(state) as client:
        if len(ids) >= 50:
            warn(
                state,
                f"{len(ids)} series means {len(ids) * (2 if meta else 1)} requests; "
                f"FRED allows {LIMITS.requests_per_minute} per minute",
            )
        response = client.fetch(
            ids,
            start=lo,
            end=hi,
            units=units_code,
            frequency=freq_code,
            aggregation=agg_code,
            as_of=vintage,
            latest=latest,
            meta=meta,
        )

    empty = [sid for sid in ids if not any(s.series_id == sid and s.data for s in response.series)]
    for sid in empty:
        if not any(sid in m for m in response.messages):
            warn(state, f"no observations returned for {sid}")
    if strict and empty:
        raise FREDNoDataError(
            f"{len(empty)} series returned no data: {', '.join(empty)}",
            hint="check the ids with `dismal fred series info` or widen the date range",
        )

    if descending:
        for s in response.series:
            s.data.reverse()

    if raw:
        emit_json(state, response.to_api_dict(), output)
        return

    records = to_records(response.series, include_meta=meta, include_realtime=vintage is not None)
    if layout == "wide":
        records = to_wide(records)
        if descending:
            records.reverse()
    cols = select_columns(records, parse_columns(columns))
    emit_records(state, records, out_fmt, output, columns=cols, title="FRED data")


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
                help="Inclusive start: YYYY, YYYY-MM, YYYY-MM-DD, YYYY-Qn or YYYY-Hn.",
                show_default=False,
            ),
        ] = None,
        end: Annotated[
            Optional[str],  # noqa: UP045
            typer.Option(
                "--end",
                "-e",
                help="Inclusive end: YYYY, YYYY-MM, YYYY-MM-DD, YYYY-Qn or YYYY-Hn.",
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
        units: UNITS_OPT = None,
        frequency: FREQUENCY_OPT = None,
        aggregation: AGGREGATION_OPT = None,
        as_of: AS_OF_OPT = None,
        meta: META_OPT = False,
        layout: Annotated[
            str,
            typer.Option(
                "--layout",
                "-L",
                help=(
                    "long: one row per series & date. wide: one row per date, a column per series."
                ),
            ),
        ] = "long",
        descending: Annotated[
            bool,
            typer.Option("--descending", help="Newest observations first (default: oldest first)."),
        ] = False,
        raw: Annotated[
            bool,
            typer.Option("--raw", help="Emit API-shaped JSON instead of records."),
        ] = False,
        strict: STRICT_OPT = False,
        fmt: FORMAT_OPT = None,
        output: OUTPUT_OPT = None,
        columns: COLUMNS_OPT = None,
    ) -> None:
        """Fetch observations for one or more series (one request each).

        Without a date flag the series' full history is returned; use
        `--years`, `--start/--end` or `--latest` to narrow it.

        Examples:

          dismal fred data UNRATE --start 2020-01 --end 2024-12

          dismal fred data CPIAUCSL --units pc1 --years 5                 # 12-month inflation rate

          dismal fred data DGS10 DGS2 --frequency m --years 10 --layout wide -f csv -o yields.csv

          dismal fred data PAYEMS --as-of 2024-02-02 --years 1              # as first published
        """
        _run_data(
            ctx,
            series,
            series_file,
            start=start,
            end=end,
            years=years,
            latest=latest,
            units=units,
            frequency=frequency,
            aggregation=aggregation,
            as_of=as_of,
            meta=meta,
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
        units: UNITS_OPT = None,
        frequency: FREQUENCY_OPT = None,
        aggregation: AGGREGATION_OPT = None,
        as_of: AS_OF_OPT = None,
        meta: META_OPT = False,
        strict: STRICT_OPT = False,
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
            units=units,
            frequency=frequency,
            aggregation=aggregation,
            as_of=as_of,
            meta=meta,
            layout="long",
            descending=False,
            raw=False,
            strict=strict,
            fmt=fmt,
            output=output,
            columns=columns,
        )
