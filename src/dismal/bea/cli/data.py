"""``dismal bea data`` and ``dismal bea latest``: fetch observations."""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from pathlib import Path
from typing import Annotated, Optional

import typer

from dismal.bea.cli._common import (
    State,
    build_client,
    emit_json,
    emit_records,
    get_state,
    handle_errors,
    parse_columns,
    parse_params,
    resolve_format,
    select_columns,
    warn,
)
from dismal.bea.client import current_year
from dismal.bea.datasets import FREQUENCY, DatasetInfo, canonical_name, dataset_info
from dismal.bea.errors import BEANoDataError
from dismal.bea.filters import ObservationFilter
from dismal.bea.output import OutputFormat
from dismal.bea.periods import Frequency, YearMonth, parse_date_spec
from dismal.bea.records import to_records, to_wide

DEFAULT_YEARS = 3  # like the BLS API: three calendar years when no range is given

DATASET_ARG = Annotated[
    str,
    typer.Argument(
        help="Dataset, e.g. NIPA, Regional, GDPbyIndustry, ITA (case-insensitive).",
        metavar="DATASET",
        show_default=False,
    ),
]
PARAMS_ARG = Annotated[
    Optional[list[str]],  # noqa: UP045 - typer needs Optional at runtime
    typer.Argument(
        help="Extra API parameters as NAME=VALUE, e.g. TableName=T10101 GeoFips=STATE.",
        metavar="[NAME=VALUE]...",
        show_default=False,
    ),
]
TABLE_OPT = Annotated[
    Optional[list[str]],  # noqa: UP045
    typer.Option(
        "--table",
        "-t",
        help="Table (TableName or TableID, by dataset). Repeatable: one request per table.",
        show_default=False,
    ),
]
FREQUENCY_OPT = Annotated[
    Optional[list[str]],  # noqa: UP045
    typer.Option(
        "--frequency",
        "-F",
        help=(
            "Frequency: A, Q, M (or annual, quarterly, monthly); dataset codes such as "
            "QSA/QNSA pass through. Repeatable."
        ),
        show_default=False,
    ),
]
GEO_OPT = Annotated[
    Optional[list[str]],  # noqa: UP045
    typer.Option(
        "--geo",
        "-g",
        help="Regional GeoFips: STATE, COUNTY, MSA or FIPS codes. Repeatable.",
        show_default=False,
    ),
]
LINE_OPT = Annotated[
    Optional[str],  # noqa: UP045
    typer.Option("--line", "-l", help="Regional LineCode, e.g. 1.", show_default=False),
]
INDUSTRY_OPT = Annotated[
    Optional[list[str]],  # noqa: UP045
    typer.Option(
        "--industry",
        "-i",
        help="GDPbyIndustry Industry code(s), default ALL. Repeatable.",
        show_default=False,
    ),
]
PARAM_OPT = Annotated[
    Optional[list[str]],  # noqa: UP045
    typer.Option(
        "--param",
        "-p",
        help="Any API parameter as NAME=VALUE (same as a positional NAME=VALUE). Repeatable.",
        show_default=False,
    ),
]
NOTES_OPT = Annotated[
    bool,
    typer.Option("--notes", help="Add a 'notes' column with the text of each row's NoteRef."),
]
STRICT_OPT = Annotated[
    bool,
    typer.Option("--strict", help="Exit with status 6 if a request returned no observations."),
]
FORMAT_OPT = Annotated[
    Optional[OutputFormat],  # noqa: UP045
    typer.Option(
        "--format",
        "-f",
        help="Output format. Default: table on a terminal, json otherwise (or $BEA_FORMAT).",
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
) -> tuple[list[int], YearMonth | None, YearMonth | None]:
    """Translate the date flags into the years to request and client-side month bounds."""
    if years is not None and (start or end):
        raise typer.BadParameter("--years cannot be combined with --start/--end")
    if years is not None and years < 1:
        raise typer.BadParameter("--years must be at least 1")
    if latest and (start or end or years):
        raise typer.BadParameter(
            "--latest returns only the newest observation; drop the date flags"
        )
    this_year = current_year()
    if years is not None:
        return list(range(this_year - years + 1, this_year + 1)), None, None
    lo = parse_date_spec(start) if start else None
    hi = parse_date_spec(end, end=True) if end else None
    if lo and hi and hi < lo:
        raise typer.BadParameter(f"--end {hi} precedes --start {lo}")
    if lo and hi:
        return list(range(lo.year, hi.year + 1)), lo, hi
    if lo:
        return list(range(lo.year, max(this_year, lo.year) + 1)), lo, None
    if hi:
        return list(range(hi.year - DEFAULT_YEARS + 1, hi.year + 1)), None, hi
    return list(range(this_year - DEFAULT_YEARS + 1, this_year + 1)), None, None


def _frequency_codes(values: Sequence[str]) -> tuple[list[str], frozenset[Frequency] | None]:
    """Map user frequency words/codes to API codes and (when possible) to a client-side filter."""
    codes: list[str] = []
    known: set[Frequency] = set()
    unknown = False
    for raw in values:
        for item in raw.split(","):
            text = item.strip()
            if not text:
                continue
            freq = Frequency.from_code(text)
            code = text.upper()
            if freq is not None:
                known.add(freq)
                if code in {"ANNUAL", "QUARTERLY", "MONTHLY", "A", "Q", "M"}:
                    code = freq.code
            else:
                unknown = True
            if code not in codes:
                codes.append(code)
    if not codes:
        raise typer.BadParameter("--frequency needs a value such as A, Q or M")
    return codes, (None if unknown or not known else frozenset(known))


def _find_key(params: Mapping[str, str], name: str) -> str | None:
    for key in params:
        if key.lower() == name.lower():
            return key
    return None


def _split_list(values: Sequence[str] | None) -> list[str]:
    out: list[str] = []
    for raw in values or []:
        out.extend(v.strip() for v in raw.split(",") if v.strip())
    return out


def build_request(
    info: DatasetInfo,
    user_params: Mapping[str, str],
    *,
    tables: Sequence[str] | None,
    frequency: Sequence[str] | None,
    geo: Sequence[str] | None,
    line: str | None,
    industry: Sequence[str] | None,
    years: Sequence[int],
) -> tuple[dict[str, str], list[str], frozenset[Frequency] | None]:
    """Assemble the GetData parameters; returns (params, tables, client-side frequency filter)."""
    params = dict(user_params)
    table_list = _split_list(tables)
    if table_list and not info.table_param:
        raise typer.BadParameter(
            f"dataset {info.name} has no table parameter; pass its parameters as NAME=VALUE"
        )
    if info.table_param:
        key = _find_key(params, info.table_param)
        if key is not None:
            if table_list:
                raise typer.BadParameter(
                    f"give the table either with --table or as {info.table_param}=..., not both"
                )
            table_list = _split_list([params.pop(key)])

    freq_filter: frozenset[Frequency] | None = None
    if frequency:
        codes, freq_filter = _frequency_codes(frequency)
        key = _find_key(params, FREQUENCY)
        if key is not None:
            raise typer.BadParameter("give the frequency either with --frequency or Frequency=")
        if info.has_frequency or not info.known:
            params[FREQUENCY] = ",".join(codes)
    if geo:
        params["GeoFips"] = ",".join(_split_list(geo))
    if line:
        params["LineCode"] = line.strip()
    if industry:
        params["Industry"] = ",".join(_split_list(industry))

    for name, value in info.defaults.items():
        if _find_key(params, name) is None:
            params[name] = value

    year_key = _find_key(params, info.year_param)
    if year_key is not None:
        value = params.pop(year_key).strip()
        params[info.year_param] = info.all_years if value.lower() in {"all", "x"} else value
    else:
        params[info.year_param] = ",".join(str(y) for y in years)

    missing = [
        p
        for p in info.required
        if _find_key(params, p) is None and not (p == info.table_param and table_list)
    ]
    if missing:
        hints = {
            info.table_param or "": "--table/-t",
            FREQUENCY: "--frequency/-F A|Q|M",
            "GeoFips": "--geo STATE|COUNTY|MSA|<fips>",
            "LineCode": "--line N (see `dismal bea tables show Regional TABLE`)",
            "Industry": "--industry CODE",
        }
        detail = "; ".join(f"{m} ({hints[m]})" if m in hints else m for m in missing)
        raise typer.BadParameter(
            f"{info.name} needs the parameter(s): {detail}. "
            f"`dismal bea datasets show {info.name}` lists every parameter."
        )
    return params, table_list, freq_filter


def _run_data(
    ctx: typer.Context,
    dataset: str,
    params: list[str] | None,
    *,
    param: list[str] | None,
    table: list[str] | None,
    frequency: list[str] | None,
    geo: list[str] | None,
    line: str | None,
    industry: list[str] | None,
    start: str | None,
    end: str | None,
    years: int | None,
    latest: bool,
    notes: bool,
    layout: str,
    descending: bool,
    raw: bool,
    strict: bool,
    fmt: OutputFormat | None,
    output: Path | None,
    columns: str | None,
) -> None:
    state: State = get_state(ctx)
    name = canonical_name(dataset)
    info = dataset_info(name)
    user_params = parse_params([*(params or []), *(param or [])])
    year_list, lo, hi = _resolve_years(start, end, years, latest)
    if _find_key(user_params, info.year_param) is not None and (start or end or years):
        raise typer.BadParameter(
            f"{info.year_param}= cannot be combined with --start/--end/--years"
        )
    if layout not in {"long", "wide"}:
        raise typer.BadParameter("--layout must be 'long' or 'wide'")
    out_fmt = resolve_format(state, fmt)
    if raw and out_fmt is not OutputFormat.JSON:
        if fmt is None:
            out_fmt = OutputFormat.JSON
        else:
            raise typer.BadParameter("--raw only supports --format json")
    request, tables, freq_filter = build_request(
        info,
        user_params,
        tables=table,
        frequency=frequency,
        geo=geo,
        line=line,
        industry=industry,
        years=year_list,
    )
    if not info.known:
        warn(state, f"unknown dataset {name!r}; parameters are passed through unchanged")

    with build_client(state) as client:
        if len(tables) > 1:
            warn(state, f"{len(tables)} tables requested; issuing one request per table")
        response = client.fetch(name, request, table_param=info.table_param, tables=tables)

    flt = ObservationFilter(start=lo, end=hi, frequencies=freq_filter, only_latest=latest)
    series_list = flt.apply(response.series)

    empty: list[str] = []
    if tables and info.table_param:
        for t in tables:
            if not any(
                s.data and t in response.series_tables.get(s.series_id, ()) for s in series_list
            ):
                empty.append(t)
        for t in empty:
            warn(state, f"no observations returned for {name} table {t}")
    elif not any(s.data for s in series_list):
        empty.append(name)
        warn(state, f"no observations returned for {name} with {_describe(request)}")
    if strict and empty:
        raise BEANoDataError(
            f"{len(empty)} request(s) returned no data: {', '.join(empty)}",
            hint=(
                "check the parameters with `dismal bea tables list` / `dismal bea values` "
                "or widen the range"
            ),
        )

    if descending:
        for s in series_list:
            s.data.reverse()

    if raw:
        response.series = series_list
        emit_json(state, response.to_api_dict(), output)
        return

    records = to_records(
        series_list, dataset=name, include_notes=notes, note_text=response.note_text
    )
    if layout == "wide":
        records = to_wide(records)
        if descending:
            records.reverse()
    cols = select_columns(records, parse_columns(columns))
    emit_records(state, records, out_fmt, output, columns=cols, title=f"{name} data")


def _describe(params: Mapping[str, str]) -> str:
    return " ".join(f"{k}={v}" for k, v in params.items())


def register(app: typer.Typer) -> None:
    @app.command("data", rich_help_panel="Data")
    @handle_errors
    def data(
        ctx: typer.Context,
        dataset: DATASET_ARG,
        params: PARAMS_ARG = None,
        table: TABLE_OPT = None,
        frequency: FREQUENCY_OPT = None,
        geo: GEO_OPT = None,
        line: LINE_OPT = None,
        industry: INDUSTRY_OPT = None,
        param: PARAM_OPT = None,
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
        notes: NOTES_OPT = False,
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
        strict: STRICT_OPT = False,
        fmt: FORMAT_OPT = None,
        output: OUTPUT_OPT = None,
        columns: COLUMNS_OPT = None,
    ) -> None:
        """Fetch observations from a dataset (the API's GetData method).

        Without a date flag the last three calendar years are requested; pass
        `Year=ALL` for everything the table has.

        Examples:

          dismal bea data NIPA --table T10101 --frequency Q --start 2020 --end 2024-Q2

          dismal bea data Regional TableName=SAINC1 --line 1 --geo STATE --years 5 -o income.csv

          dismal bea data GDPbyIndustry -t 1 -F A --industry 11 --industry 21 --latest

          dismal bea data ITA Indicator=BalGds AreaOrCountry=AllCountries -F QSA --layout wide
        """
        _run_data(
            ctx,
            dataset,
            params,
            param=param,
            table=table,
            frequency=frequency,
            geo=geo,
            line=line,
            industry=industry,
            start=start,
            end=end,
            years=years,
            latest=latest,
            notes=notes,
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
        dataset: DATASET_ARG,
        params: PARAMS_ARG = None,
        table: TABLE_OPT = None,
        frequency: FREQUENCY_OPT = None,
        geo: GEO_OPT = None,
        line: LINE_OPT = None,
        industry: INDUSTRY_OPT = None,
        param: PARAM_OPT = None,
        notes: NOTES_OPT = False,
        strict: STRICT_OPT = False,
        fmt: FORMAT_OPT = None,
        output: OUTPUT_OPT = None,
        columns: COLUMNS_OPT = None,
    ) -> None:
        """Fetch only the newest observation of each series (alias for `data --latest`).

        The last three calendar years are requested and the newest row per
        series is kept.
        """
        _run_data(
            ctx,
            dataset,
            params,
            param=param,
            table=table,
            frequency=frequency,
            geo=geo,
            line=line,
            industry=industry,
            start=None,
            end=None,
            years=None,
            latest=True,
            notes=notes,
            layout="long",
            descending=False,
            raw=False,
            strict=strict,
            fmt=fmt,
            output=output,
            columns=columns,
        )
