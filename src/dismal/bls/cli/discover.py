"""Discovery commands: ``surveys``, ``search``, ``popular`` and ``series``."""

from __future__ import annotations

from typing import Annotated, Any, Optional

import typer

from dismal.bls.cache import FileCache
from dismal.bls.catalog import (
    SURVEYS_TTL_SECONDS,
    bundled_surveys,
    cached_surveys,
    series_catalog,
    store_surveys,
    survey_name,
)
from dismal.bls.cli._common import (
    State,
    build_client,
    collect_series_ids,
    emit_json,
    emit_records,
    get_state,
    handle_errors,
    info,
    parse_columns,
    resolve_format,
    select_columns,
    warn,
)
from dismal.bls.cli.data import COLUMNS_OPT, FORMAT_OPT, OUTPUT_OPT, SERIES_ARG, SERIES_FILE_OPT
from dismal.bls.flatfiles import fetch_series_file, parse_series_file, series_title_of
from dismal.bls.models import Survey
from dismal.bls.search import search_rows, search_series, search_surveys

LIMIT_OPT = Annotated[
    int, typer.Option("--limit", "-n", help="Maximum number of results (0 = no limit).")
]
MIN_SCORE_OPT = Annotated[
    float, typer.Option("--min-score", help="Minimum fuzzy match score (0-100).")
]
SURVEY_OPT = Annotated[
    Optional[str],  # noqa: UP045
    typer.Option(
        "--survey", "-u", help="Restrict to one survey abbreviation, e.g. CU.", show_default=False
    ),
]


def load_surveys(state: State, *, refresh: bool = False, offline: bool = False) -> list[Survey]:
    """Cached live list when available (or refreshed on demand), else the bundled snapshot."""
    cache = FileCache(state.settings.cache_dir)
    if refresh and not offline:
        with build_client(state) as client:
            surveys = client.surveys()
        store_surveys(cache, surveys)
        info(state, f"cached {len(surveys)} surveys in {cache.path('surveys.json')}")
        return surveys
    cached = cached_surveys(cache)
    if cached and (offline or cache.is_fresh("surveys.json", SURVEYS_TTL_SECONDS)):
        return cached
    if cached:
        return cached  # stale but usable; `--refresh` updates it
    return bundled_surveys()


def register(app: typer.Typer) -> None:
    # -- surveys ----------------------------------------------------------------
    surveys_app = typer.Typer(
        help="List or inspect BLS surveys (data sets).",
        invoke_without_command=True,
        no_args_is_help=False,
    )
    app.add_typer(surveys_app, name="surveys", rich_help_panel="Discovery")

    @surveys_app.callback()
    @handle_errors
    def surveys(
        ctx: typer.Context,
        refresh: Annotated[
            bool, typer.Option("--refresh", help="Fetch the live list from the API and cache it.")
        ] = False,
        query: Annotated[
            Optional[str],  # noqa: UP045
            typer.Option(
                "--query",
                "-q",
                help="Fuzzy-filter surveys by name or abbreviation.",
                show_default=False,
            ),
        ] = None,
        fmt: FORMAT_OPT = None,
        output: OUTPUT_OPT = None,
        columns: COLUMNS_OPT = None,
    ) -> None:
        """List surveys. Without --refresh an offline snapshot (or the cached live list) is used."""
        if ctx.invoked_subcommand is not None:
            return
        state = get_state(ctx)
        surveys = load_surveys(state, refresh=refresh)
        if query:
            hits = search_surveys(query, surveys, limit=0, min_score=50)
            records: list[dict[str, Any]] = [
                {"abbreviation": h.id, "name": h.title, "score": round(h.score, 1)} for h in hits
            ]
        else:
            records = [{"abbreviation": s.abbreviation, "name": s.name} for s in surveys]
        cols = select_columns(records, parse_columns(columns))
        emit_records(
            state, records, resolve_format(state, fmt), output, columns=cols, title="BLS surveys"
        )

    @surveys_app.command("show")
    @handle_errors
    def surveys_show(
        ctx: typer.Context,
        abbreviation: Annotated[str, typer.Argument(help="Survey abbreviation, e.g. CU.")],
        output: OUTPUT_OPT = None,
    ) -> None:
        """Show the API's metadata for one survey (live request)."""
        state = get_state(ctx)
        with build_client(state) as client:
            payload = client.survey(abbreviation)
        emit_json(state, payload, output)

    # -- search -----------------------------------------------------------------
    @app.command("search", rich_help_panel="Discovery")
    @handle_errors
    def search(
        ctx: typer.Context,
        query: Annotated[
            list[str],
            typer.Argument(help="Free-text query, e.g. 'core cpi' or 'unemployment rate'."),
        ],
        survey: SURVEY_OPT = None,
        kind: Annotated[
            str, typer.Option("--kind", "-k", help="What to search: series, surveys or all.")
        ] = "series",
        limit: LIMIT_OPT = 20,
        min_score: MIN_SCORE_OPT = 55.0,
        fmt: FORMAT_OPT = None,
        output: OUTPUT_OPT = None,
        columns: COLUMNS_OPT = None,
    ) -> None:
        """Fuzzy-search the bundled catalog of popular series and the survey list (offline).

        Typos and word order are tolerated. For an exhaustive directory of a
        survey use `dismal bls series list --survey XX --query ...`.
        """
        state = get_state(ctx)
        text = " ".join(query).strip()
        if not text:
            raise typer.BadParameter("empty query")
        if kind not in {"series", "surveys", "all"}:
            raise typer.BadParameter("--kind must be series, surveys or all")
        hits = []
        if kind in {"series", "all"}:
            hits += search_series(
                text, series_catalog(), survey=survey, limit=limit, min_score=min_score
            )
        if kind in {"surveys", "all"}:
            hits += search_surveys(
                text, load_surveys(state, offline=True), limit=limit, min_score=min_score
            )
        hits.sort(key=lambda h: -h.score)  # stable: keeps catalog order within a score
        if limit:
            hits = hits[:limit]
        records = [h.to_record() for h in hits]
        if not records:
            warn(
                state,
                f"no matches for {text!r} (try a lower --min-score or `dismal bls series list`)",
            )
        cols = select_columns(records, parse_columns(columns))
        emit_records(
            state,
            records,
            resolve_format(state, fmt),
            output,
            columns=cols,
            title=f"search: {text}",
        )

    # -- popular ----------------------------------------------------------------
    @app.command("popular", rich_help_panel="Discovery")
    @handle_errors
    def popular(
        ctx: typer.Context,
        survey: SURVEY_OPT = None,
        catalog: Annotated[
            bool,
            typer.Option(
                "--catalog",
                "-c",
                help="Also fetch titles via the data endpoint (needs an API key).",
            ),
        ] = False,
        fmt: FORMAT_OPT = None,
        output: OUTPUT_OPT = None,
        columns: COLUMNS_OPT = None,
    ) -> None:
        """List the series BLS currently flags as popular, overall or for one survey (live)."""
        state = get_state(ctx)
        with build_client(state) as client:
            ids = client.popular(survey)
            titles: dict[str, str | None] = {}
            if catalog and ids:
                resp = client.fetch(ids, latest=True, catalog=True)
                titles = {s.series_id: s.title for s in resp.series}
        surveys = load_surveys(state, offline=True)
        records = []
        for sid in ids:
            rec: dict[str, Any] = {"series_id": sid, "survey": sid[:2]}
            name = survey_name(sid[:2], surveys)
            if name:
                rec["survey_name"] = name
            if catalog:
                rec["title"] = titles.get(sid)
            records.append(rec)
        cols = select_columns(records, parse_columns(columns))
        emit_records(
            state, records, resolve_format(state, fmt), output, columns=cols, title="popular series"
        )

    # -- series -----------------------------------------------------------------
    series_app = typer.Typer(help="Discover and describe individual series.", no_args_is_help=True)
    app.add_typer(series_app, name="series", rich_help_panel="Discovery")

    @series_app.command("list")
    @handle_errors
    def series_list(
        ctx: typer.Context,
        survey: Annotated[
            str, typer.Option("--survey", "-u", help="Survey abbreviation, e.g. CU, CE, LN.")
        ],
        query: Annotated[
            Optional[str],  # noqa: UP045
            typer.Option(
                "--query", "-q", help="Fuzzy-filter by series title (and id).", show_default=False
            ),
        ] = None,
        limit: LIMIT_OPT = 50,
        min_score: MIN_SCORE_OPT = 60.0,
        refresh: Annotated[
            bool, typer.Option("--refresh", help="Re-download the series directory.")
        ] = False,
        fmt: FORMAT_OPT = None,
        output: OUTPUT_OPT = None,
        columns: COLUMNS_OPT = None,
    ) -> None:
        """List every series of a survey from the BLS flat-file directory (download.bls.gov).

        The file is cached for 30 days under BLS_CACHE_DIR. Some directories are
        large (tens of MB); use --query to narrow the output.
        """
        state = get_state(ctx)
        text = fetch_series_file(
            survey,
            state.settings,
            refresh=refresh,
            transport=state.transport,
            progress=lambda m: info(state, m),
        )
        rows = parse_series_file(text)
        if "series_id" not in (rows[0] if rows else {}):
            raise typer.BadParameter(f"unexpected flat-file layout for survey {survey.upper()}")
        if query:
            scored = search_rows(
                query,
                rows,
                text_of=lambda r: f"{r['series_id']} {series_title_of(r)}",
                id_of=lambda r: str(r["series_id"]),
                limit=limit,
                min_score=min_score,
            )
            records = [
                {
                    "series_id": r["series_id"],
                    "title": series_title_of(r),
                    "score": round(s, 1),
                    **{k: v for k, v in r.items() if k not in {"series_id", "series_title"}},
                }
                for s, r in scored
            ]
        else:
            records = [
                {
                    "series_id": r["series_id"],
                    "title": series_title_of(r),
                    **{k: v for k, v in r.items() if k not in {"series_id", "series_title"}},
                }
                for r in (rows[:limit] if limit else rows)
            ]
        if not records:
            warn(state, "no series matched")
        cols = select_columns(records, parse_columns(columns))
        emit_records(
            state,
            records,
            resolve_format(state, fmt),
            output,
            columns=cols,
            title=f"{survey.upper()} series",
        )

    @series_app.command("info")
    @handle_errors
    def series_info(
        ctx: typer.Context,
        series: SERIES_ARG = None,
        series_file: SERIES_FILE_OPT = None,
        fmt: FORMAT_OPT = None,
        output: OUTPUT_OPT = None,
    ) -> None:
        """Describe series via API catalog metadata plus their latest value (needs an API key)."""
        state = get_state(ctx)
        ids = collect_series_ids(series or [], series_file)
        if not state.settings.has_api_key:
            warn(
                state, "catalog metadata requires BLS_API_KEY; only the latest values will be shown"
            )
        with build_client(state) as client:
            resp = client.fetch(ids, latest=True, catalog=True)
        records = []
        for s in resp.series:
            rec: dict[str, Any] = {"series_id": s.series_id}
            if s.catalog:
                rec.update(
                    {k: v for k, v in s.catalog.items() if k != "series_id" and v not in ("", None)}
                )
            if s.data:
                latest = s.data[-1]
                rec.update(
                    {
                        "latest_year": latest.year,
                        "latest_period": latest.period,
                        "latest_value": latest.value,
                    }
                )
            records.append(rec)
        for sid in ids:
            if not any(r["series_id"] == sid for r in records):
                warn(state, f"no information returned for {sid}")
        emit_records(state, records, resolve_format(state, fmt), output, title="series info")
