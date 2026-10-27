"""Discovery commands: ``search``, ``series``, ``releases`` and ``categories``."""

from __future__ import annotations

import datetime as _dt
from typing import Annotated, Any, Optional

import typer

from dismal.fred.cache import FileCache
from dismal.fred.catalog import series_catalog
from dismal.fred.cli._common import (
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
from dismal.fred.cli.data import COLUMNS_OPT, FORMAT_OPT, OUTPUT_OPT, SERIES_ARG, SERIES_FILE_OPT
from dismal.fred.client import today
from dismal.fred.errors import FREDNotFoundError
from dismal.fred.models import Category, Release
from dismal.fred.periods import Frequency, normalise_frequency
from dismal.fred.search import search_rows, search_series

LIMIT_OPT = Annotated[
    int, typer.Option("--limit", "-n", help="Maximum number of results (0 = no limit).")
]
MIN_SCORE_OPT = Annotated[
    float, typer.Option("--min-score", help="Minimum fuzzy match score (0-100).")
]
REFRESH_OPT = Annotated[
    bool, typer.Option("--refresh", help="Ignore the cache and fetch from the API.")
]
QUERY_OPT = Annotated[
    Optional[str],  # noqa: UP045
    typer.Option("--query", "-q", help="Fuzzy-filter by name (and id).", show_default=False),
]

METADATA_TTL_SECONDS = 7 * 24 * 3600
ORDER_BY_CHOICES = (
    "search_rank",
    "series_id",
    "title",
    "units",
    "frequency",
    "seasonal_adjustment",
    "realtime_start",
    "realtime_end",
    "last_updated",
    "observation_start",
    "observation_end",
    "popularity",
    "group_popularity",
)
_FREQUENCY_NAMES = {
    Frequency.DAILY: "Daily",
    Frequency.WEEKLY: "Weekly",
    Frequency.BIWEEKLY: "Biweekly",
    Frequency.MONTHLY: "Monthly",
    Frequency.QUARTERLY: "Quarterly",
    Frequency.SEMIANNUAL: "Semiannual",
    Frequency.ANNUAL: "Annual",
}
_SEASONAL_NAMES = {
    "sa": "Seasonally Adjusted",
    "nsa": "Not Seasonally Adjusted",
    "saar": "Seasonally Adjusted Annual Rate",
}


def load_releases(state: State, *, refresh: bool = False) -> list[Release]:
    cache = FileCache(state.settings.cache_dir)
    name = "releases.json"
    if not refresh and cache.is_fresh(name, METADATA_TTL_SECONDS):
        raw = cache.read_json(name)
        if isinstance(raw, list):
            return [Release.from_api(r) for r in raw]
    with build_client(state) as client:
        releases = client.releases()
    cache.write_json(
        name,
        [
            {
                "id": r.id,
                "name": r.name,
                "press_release": r.press_release,
                "link": r.link,
                "notes": r.notes,
            }
            for r in releases
        ],
    )
    info(state, f"cached {len(releases)} releases in {cache.path(name)}")
    return releases


def load_category_children(
    state: State, category_id: int, *, refresh: bool = False
) -> list[Category]:
    cache = FileCache(state.settings.cache_dir / "categories")
    name = f"{category_id}.json"
    if not refresh and cache.is_fresh(name, METADATA_TTL_SECONDS):
        raw = cache.read_json(name)
        if isinstance(raw, list):
            return [Category.from_api(c) for c in raw]
    with build_client(state) as client:
        children = client.category_children(category_id)
    cache.write_json(
        name, [{"id": c.id, "name": c.name, "parent_id": c.parent_id} for c in children]
    )
    return children


def _filter_records(
    query: str | None,
    records: list[dict[str, Any]],
    *,
    id_col: str,
    text_col: str,
    min_score: float = 50.0,
) -> list[dict[str, Any]]:
    if not query:
        return records
    scored = search_rows(
        query,
        records,
        text_of=lambda r: f"{r.get(id_col, '')} {r.get(text_col, '')}",
        id_of=lambda r: str(r.get(id_col, "")),
        limit=0,
        min_score=min_score,
    )
    return [{**rec, "score": round(score, 1)} for score, rec in scored]


def register(app: typer.Typer) -> None:
    # -- search (offline) ----------------------------------------------------------
    @app.command("search", rich_help_panel="Discovery")
    @handle_errors
    def search(
        ctx: typer.Context,
        query: Annotated[
            list[str],
            typer.Argument(help="Free-text query, e.g. 'unemployment rate' or 'mortgage rates'."),
        ],
        limit: LIMIT_OPT = 20,
        min_score: MIN_SCORE_OPT = 55.0,
        fmt: FORMAT_OPT = None,
        output: OUTPUT_OPT = None,
        columns: COLUMNS_OPT = None,
    ) -> None:
        """Fuzzy-search the bundled catalog of popular series (offline).

        Typos, word order and everyday phrases ("mortgage rates", "jobs
        report") are tolerated. For every series FRED has, use
        `dismal fred series search` (the API's full-text search).
        """
        state = get_state(ctx)
        text = " ".join(query).strip()
        if not text:
            raise typer.BadParameter("empty query")
        hits = search_series(text, series_catalog(), limit=limit, min_score=min_score)
        records = [h.to_record() for h in hits]
        if not records:
            warn(
                state,
                f"no matches for {text!r} in the curated catalog; try `dismal fred series search "
                f"{text!r}` (live) or a lower --min-score",
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

    # -- series -----------------------------------------------------------------
    series_app = typer.Typer(help="Describe, search and track individual series (live).")
    app.add_typer(series_app, name="series", rich_help_panel="Discovery")

    @series_app.command("info")
    @handle_errors
    def series_info(
        ctx: typer.Context,
        series: SERIES_ARG = None,
        series_file: SERIES_FILE_OPT = None,
        notes: Annotated[
            bool, typer.Option("--notes", help="Include the (often long) notes column.")
        ] = False,
        fmt: FORMAT_OPT = None,
        output: OUTPUT_OPT = None,
        columns: COLUMNS_OPT = None,
    ) -> None:
        """Metadata for series: title, frequency, units, seasonal adjustment, coverage, updates."""
        state = get_state(ctx)
        ids = collect_series_ids(series or [], series_file)
        records = []
        with build_client(state) as client:
            for sid in ids:
                try:
                    records.append(client.series_info(sid).to_record(include_notes=notes))
                except FREDNotFoundError:
                    warn(state, f"series {sid} does not exist")
        cols = select_columns(records, parse_columns(columns))
        emit_records(
            state, records, resolve_format(state, fmt), output, columns=cols, title="series info"
        )

    @series_app.command("search")
    @handle_errors
    def series_search(
        ctx: typer.Context,
        query: Annotated[
            list[str], typer.Argument(help="Full-text query, e.g. 'median home price'.")
        ],
        limit: Annotated[int, typer.Option("--limit", "-n", help="Maximum results (1-1000).")] = 20,
        order_by: Annotated[
            str,
            typer.Option(
                "--order-by",
                help="search_rank (relevance), popularity, last_updated, title, series_id, ...",
            ),
        ] = "search_rank",
        sort: Annotated[
            Optional[str],  # noqa: UP045
            typer.Option("--sort", help="asc or desc (the API's default depends on --order-by)."),
        ] = None,
        frequency: Annotated[
            Optional[str],  # noqa: UP045
            typer.Option(
                "--frequency", "-F", help="Only series of this frequency: d, w, m, q, a, ..."
            ),
        ] = None,
        seasonal: Annotated[
            Optional[str],  # noqa: UP045
            typer.Option("--seasonal", help="Only sa, nsa or saar series."),
        ] = None,
        tags: Annotated[
            Optional[list[str]],  # noqa: UP045
            typer.Option("--tag", "-t", help="Require this FRED tag (repeatable)."),
        ] = None,
        exclude_tags: Annotated[
            Optional[list[str]],  # noqa: UP045
            typer.Option("--exclude-tag", help="Exclude this FRED tag (repeatable)."),
        ] = None,
        by_id: Annotated[
            bool,
            typer.Option("--id", help="Search series ids instead of titles (prefix match)."),
        ] = False,
        fmt: FORMAT_OPT = None,
        output: OUTPUT_OPT = None,
        columns: COLUMNS_OPT = None,
    ) -> None:
        """Search every FRED series with the API's full-text search (live).

        Examples:

          dismal fred series search "median home price" --order-by popularity

          dismal fred series search "unemployment rate" --frequency m --tag usa -n 10

          dismal fred series search "gdp" --tag "usa" --tag "quarterly" --exclude-tag "discontinued"
        """
        state = get_state(ctx)
        text = " ".join(query).strip()
        if not text:
            raise typer.BadParameter("empty query")
        if order_by not in ORDER_BY_CHOICES:
            raise typer.BadParameter(f"--order-by must be one of {', '.join(ORDER_BY_CHOICES)}")
        if sort and sort not in {"asc", "desc"}:
            raise typer.BadParameter("--sort must be asc or desc")
        if limit < 1:
            raise typer.BadParameter("--limit must be at least 1")
        filter_variable = filter_value = None
        if frequency and seasonal:
            raise typer.BadParameter("the API accepts one of --frequency or --seasonal per search")
        if frequency:
            freq = Frequency.from_code(normalise_frequency(frequency))
            if freq is None:
                raise typer.BadParameter("--frequency must be d, w, bw, m, q, sa or a")
            filter_variable, filter_value = "frequency", _FREQUENCY_NAMES[freq]
        if seasonal:
            if seasonal.lower() not in _SEASONAL_NAMES:
                raise typer.BadParameter("--seasonal must be sa, nsa or saar")
            filter_variable, filter_value = "seasonal_adjustment", _SEASONAL_NAMES[seasonal.lower()]
        with build_client(state) as client:
            hits, count = client.search(
                text,
                search_type="series_id" if by_id else "full_text",
                limit=limit,
                order_by=order_by,
                sort_order=sort,
                filter_variable=filter_variable,
                filter_value=filter_value,
                tag_names=tags,
                exclude_tag_names=exclude_tags,
            )
        records = [h.to_record() for h in hits]
        if count > len(records):
            info(state, f"{count} series match; showing {len(records)} (raise --limit for more)")
        if not records:
            warn(state, f"no series match {text!r}")
        cols = select_columns(records, parse_columns(columns))
        emit_records(
            state,
            records,
            resolve_format(state, fmt),
            output,
            columns=cols,
            title=f"search: {text}",
        )

    @series_app.command("vintages")
    @handle_errors
    def series_vintages(
        ctx: typer.Context,
        series_id: Annotated[
            str, typer.Argument(help="Series id, e.g. PAYEMS.", metavar="SERIES_ID")
        ],
        fmt: FORMAT_OPT = None,
        output: OUTPUT_OPT = None,
    ) -> None:
        """List the dates on which a series was released or revised (ALFRED vintages)."""
        state = get_state(ctx)
        with build_client(state) as client:
            dates = client.vintage_dates(series_id)
        records = [{"series_id": series_id.upper(), "vintage_date": d} for d in dates]
        emit_records(
            state,
            records,
            resolve_format(state, fmt),
            output,
            title=f"{series_id.upper()} vintages",
        )

    @series_app.command("updates")
    @handle_errors
    def series_updates(
        ctx: typer.Context,
        limit: Annotated[int, typer.Option("--limit", "-n", help="Maximum results (1-1000).")] = 50,
        fmt: FORMAT_OPT = None,
        output: OUTPUT_OPT = None,
        columns: COLUMNS_OPT = None,
    ) -> None:
        """Series most recently updated on FRED, newest first (live)."""
        state = get_state(ctx)
        with build_client(state) as client:
            hits = client.updates(limit=limit)
        records = [h.to_record() for h in hits]
        cols = select_columns(records, parse_columns(columns))
        emit_records(
            state, records, resolve_format(state, fmt), output, columns=cols, title="recent updates"
        )

    # -- releases ---------------------------------------------------------------
    releases_app = typer.Typer(
        help="List releases, their series and upcoming release dates.",
        invoke_without_command=True,
        no_args_is_help=False,
    )
    app.add_typer(releases_app, name="releases", rich_help_panel="Discovery")

    @releases_app.callback()
    @handle_errors
    def releases(
        ctx: typer.Context,
        refresh: REFRESH_OPT = False,
        query: QUERY_OPT = None,
        fmt: FORMAT_OPT = None,
        output: OUTPUT_OPT = None,
        columns: COLUMNS_OPT = None,
    ) -> None:
        """List every release (cached 7 days); --query fuzzy-filters by name."""
        if ctx.invoked_subcommand is not None:
            return
        state = get_state(ctx)
        records = [r.to_record() for r in load_releases(state, refresh=refresh)]
        records = _filter_records(query, records, id_col="id", text_col="name")
        if not records:
            warn(state, "no releases matched")
        cols = select_columns(records, parse_columns(columns))
        emit_records(
            state, records, resolve_format(state, fmt), output, columns=cols, title="FRED releases"
        )

    @releases_app.command("show")
    @handle_errors
    def releases_show(
        ctx: typer.Context,
        release_id: Annotated[
            int, typer.Argument(help="Release id, e.g. 53.", metavar="RELEASE_ID")
        ],
        output: OUTPUT_OPT = None,
    ) -> None:
        """Show one release's metadata (live request)."""
        state = get_state(ctx)
        with build_client(state) as client:
            rel = client.release(release_id)
        emit_json(state, {**rel.to_record(), "notes": rel.notes}, output)

    @releases_app.command("series")
    @handle_errors
    def releases_series(
        ctx: typer.Context,
        release_id: Annotated[
            int, typer.Argument(help="Release id, e.g. 53.", metavar="RELEASE_ID")
        ],
        limit: Annotated[
            int, typer.Option("--limit", "-n", help="Maximum results (1-1000).")
        ] = 100,
        fmt: FORMAT_OPT = None,
        output: OUTPUT_OPT = None,
        columns: COLUMNS_OPT = None,
    ) -> None:
        """List the series published in a release (live)."""
        state = get_state(ctx)
        with build_client(state) as client:
            hits, count = client.release_series(release_id, limit=limit)
        records = [h.to_record() for h in hits]
        if count > len(records):
            info(state, f"{count} series in the release; showing {len(records)}")
        cols = select_columns(records, parse_columns(columns))
        emit_records(
            state,
            records,
            resolve_format(state, fmt),
            output,
            columns=cols,
            title=f"release {release_id} series",
        )

    @releases_app.command("dates")
    @handle_errors
    def releases_dates(
        ctx: typer.Context,
        days: Annotated[
            int,
            typer.Option("--days", "-d", help="How many days ahead (or back, negative) to list."),
        ] = 14,
        fmt: FORMAT_OPT = None,
        output: OUTPUT_OPT = None,
        columns: COLUMNS_OPT = None,
    ) -> None:
        """Upcoming (or recent, with a negative --days) release dates: the FRED calendar."""
        state = get_state(ctx)
        start = today()
        end = start + _dt.timedelta(days=days)
        if days < 0:
            start, end = end, start
        with build_client(state) as client:
            dates = client.release_dates(start, end)
        records = [d.to_record() for d in dates]
        cols = select_columns(records, parse_columns(columns))
        emit_records(
            state,
            records,
            resolve_format(state, fmt),
            output,
            columns=cols,
            title=f"release dates {start} to {end}",
        )

    # -- categories -------------------------------------------------------------
    categories_app = typer.Typer(
        help="Browse the category tree (root categories without a subcommand).",
        invoke_without_command=True,
        no_args_is_help=False,
    )
    app.add_typer(categories_app, name="categories", rich_help_panel="Discovery")

    @categories_app.callback()
    @handle_errors
    def categories(
        ctx: typer.Context,
        refresh: REFRESH_OPT = False,
        query: QUERY_OPT = None,
        fmt: FORMAT_OPT = None,
        output: OUTPUT_OPT = None,
        columns: COLUMNS_OPT = None,
    ) -> None:
        """List the top-level categories (cached 7 days)."""
        if ctx.invoked_subcommand is not None:
            return
        state = get_state(ctx)
        records = [c.to_record() for c in load_category_children(state, 0, refresh=refresh)]
        records = _filter_records(query, records, id_col="id", text_col="name")
        cols = select_columns(records, parse_columns(columns))
        emit_records(
            state,
            records,
            resolve_format(state, fmt),
            output,
            columns=cols,
            title="FRED categories",
        )

    @categories_app.command("children")
    @handle_errors
    def categories_children(
        ctx: typer.Context,
        category_id: Annotated[
            int, typer.Argument(help="Category id, e.g. 32991.", metavar="CATEGORY_ID")
        ],
        refresh: REFRESH_OPT = False,
        fmt: FORMAT_OPT = None,
        output: OUTPUT_OPT = None,
        columns: COLUMNS_OPT = None,
    ) -> None:
        """List the child categories of a category (cached 7 days)."""
        state = get_state(ctx)
        records = [
            c.to_record() for c in load_category_children(state, category_id, refresh=refresh)
        ]
        if not records:
            warn(state, f"category {category_id} has no children")
        cols = select_columns(records, parse_columns(columns))
        emit_records(
            state,
            records,
            resolve_format(state, fmt),
            output,
            columns=cols,
            title=f"category {category_id} children",
        )

    @categories_app.command("series")
    @handle_errors
    def categories_series(
        ctx: typer.Context,
        category_id: Annotated[
            int, typer.Argument(help="Category id, e.g. 32991.", metavar="CATEGORY_ID")
        ],
        limit: Annotated[
            int, typer.Option("--limit", "-n", help="Maximum results (1-1000).")
        ] = 100,
        fmt: FORMAT_OPT = None,
        output: OUTPUT_OPT = None,
        columns: COLUMNS_OPT = None,
    ) -> None:
        """List the series in a category (live)."""
        state = get_state(ctx)
        with build_client(state) as client:
            hits, count = client.category_series(category_id, limit=limit)
        records = [h.to_record() for h in hits]
        if count > len(records):
            info(state, f"{count} series in the category; showing {len(records)}")
        cols = select_columns(records, parse_columns(columns))
        emit_records(
            state,
            records,
            resolve_format(state, fmt),
            output,
            columns=cols,
            title=f"category {category_id} series",
        )
