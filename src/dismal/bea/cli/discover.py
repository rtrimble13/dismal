"""Discovery commands: ``datasets``, ``search``, ``tables`` and ``values``."""

from __future__ import annotations

import re
from collections.abc import Mapping
from typing import Annotated, Any, Optional

import typer

from dismal.bea.cache import FileCache
from dismal.bea.catalog import (
    bundled_datasets,
    cached_datasets,
    store_datasets,
    table_catalog,
)
from dismal.bea.cli._common import (
    State,
    build_client,
    emit_records,
    get_state,
    handle_errors,
    info,
    parse_columns,
    parse_params,
    resolve_format,
    select_columns,
    values_to_records,
    warn,
)
from dismal.bea.cli.data import COLUMNS_OPT, FORMAT_OPT, OUTPUT_OPT
from dismal.bea.client import current_year
from dismal.bea.datasets import FREQUENCY, canonical_name, dataset_info
from dismal.bea.models import Dataset, Parameter
from dismal.bea.search import search_datasets, search_rows, search_tables

LIMIT_OPT = Annotated[
    int, typer.Option("--limit", "-n", help="Maximum number of results (0 = no limit).")
]
MIN_SCORE_OPT = Annotated[
    float, typer.Option("--min-score", help="Minimum fuzzy match score (0-100).")
]
DATASET_OPT = Annotated[
    Optional[str],  # noqa: UP045
    typer.Option("--dataset", "-d", help="Restrict to one dataset, e.g. NIPA.", show_default=False),
]
REFRESH_OPT = Annotated[
    bool, typer.Option("--refresh", help="Ignore the cache and fetch from the API.")
]
QUERY_OPT = Annotated[
    Optional[str],  # noqa: UP045
    typer.Option(
        "--query", "-q", help="Fuzzy-filter by description (and key).", show_default=False
    ),
]
DATASET_POS = Annotated[
    str, typer.Argument(help="Dataset name, e.g. NIPA or Regional.", metavar="DATASET")
]

METADATA_TTL_SECONDS = 7 * 24 * 3600


def load_datasets(state: State, *, refresh: bool = False, offline: bool = False) -> list[Dataset]:
    """Cached live list when available (or refreshed on demand), else the bundled snapshot."""
    cache = FileCache(state.settings.cache_dir)
    if refresh and not offline:
        with build_client(state) as client:
            datasets = client.datasets()
        store_datasets(cache, datasets)
        info(state, f"cached {len(datasets)} datasets in {cache.path('datasets.json')}")
        return datasets
    cached = cached_datasets(cache)
    if cached:
        return cached  # possibly stale but usable; `--refresh` updates it
    return bundled_datasets()


def _safe(text: str) -> str:
    return re.sub(r"[^A-Za-z0-9_.=-]+", "_", text)


def load_parameters(state: State, dataset: str, *, refresh: bool = False) -> list[Parameter]:
    cache = FileCache(state.settings.cache_dir / "params")
    name = f"{_safe(canonical_name(dataset))}.json"
    if not refresh and cache.is_fresh(name, METADATA_TTL_SECONDS):
        raw = cache.read_json(name)
        if isinstance(raw, list):
            return [Parameter.from_api(p) for p in raw]
    with build_client(state) as client:
        params = client.parameters(dataset)
    cache.write_json(
        name,
        [
            {
                "ParameterName": p.name,
                "ParameterDataType": p.data_type,
                "ParameterDescription": p.description,
                "ParameterIsRequiredFlag": "1" if p.required else "0",
                "ParameterDefaultValue": p.default,
                "MultipleAcceptedFlag": "1" if p.multiple else "0",
                "AllValue": p.all_value,
            }
            for p in params
        ],
    )
    return params


def load_values(
    state: State,
    dataset: str,
    parameter: str,
    *,
    filters: Mapping[str, str] | None = None,
    refresh: bool = False,
) -> list[dict[str, Any]]:
    """Parameter values from the cache (7 days) or the API (filtered when ``filters`` is given)."""
    cache = FileCache(state.settings.cache_dir / "values")
    suffix = "".join(f"__{_safe(k)}={_safe(v)}" for k, v in sorted((filters or {}).items()))
    name = f"{_safe(canonical_name(dataset))}.{_safe(parameter)}{suffix}.json"
    if not refresh and cache.is_fresh(name, METADATA_TTL_SECONDS):
        raw = cache.read_json(name)
        if isinstance(raw, list):
            return [dict(v) for v in raw]
    with build_client(state) as client:
        values = (
            client.parameter_values_filtered(dataset, parameter, filters)
            if filters
            else client.parameter_values(dataset, parameter)
        )
    cache.write_json(name, values)
    return values


def _filtered_records(
    query: str | None,
    records: list[dict[str, Any]],
    *,
    limit: int,
    min_score: float,
    id_col: str,
    text_cols: tuple[str, ...],
) -> list[dict[str, Any]]:
    if query:
        scored = search_rows(
            query,
            records,
            text_of=lambda r: " ".join(str(r.get(c, "")) for c in (id_col, *text_cols)),
            id_of=lambda r: str(r.get(id_col, "")),
            limit=limit,
            min_score=min_score,
        )
        out = []
        for score, rec in scored:
            new = dict(rec)
            items = list(new.items())
            head = [(k, v) for k, v in items if k in (id_col, *text_cols)]
            tail = [(k, v) for k, v in items if k not in (id_col, *text_cols)]
            out.append(dict([*head, ("score", round(score, 1)), *tail]))
        return out
    return records[:limit] if limit else records


def register(app: typer.Typer) -> None:
    # -- datasets -----------------------------------------------------------------
    datasets_app = typer.Typer(
        help="List datasets or show a dataset's parameters.",
        invoke_without_command=True,
        no_args_is_help=False,
    )
    app.add_typer(datasets_app, name="datasets", rich_help_panel="Discovery")

    @datasets_app.callback()
    @handle_errors
    def datasets(
        ctx: typer.Context,
        refresh: Annotated[
            bool, typer.Option("--refresh", help="Fetch the live list from the API and cache it.")
        ] = False,
        query: Annotated[
            Optional[str],  # noqa: UP045
            typer.Option(
                "--query",
                "-q",
                help="Fuzzy-filter datasets by name or description.",
                show_default=False,
            ),
        ] = None,
        fmt: FORMAT_OPT = None,
        output: OUTPUT_OPT = None,
        columns: COLUMNS_OPT = None,
    ) -> None:
        """List datasets (offline snapshot or the cached live list unless --refresh)."""
        if ctx.invoked_subcommand is not None:
            return
        state = get_state(ctx)
        datasets = load_datasets(state, refresh=refresh)
        if query:
            hits = search_datasets(query, datasets, limit=0, min_score=50)
            records: list[dict[str, Any]] = [
                {"dataset": h.id, "description": h.title, "score": round(h.score, 1)} for h in hits
            ]
        else:
            records = [{"dataset": d.name, "description": d.description} for d in datasets]
        cols = select_columns(records, parse_columns(columns))
        emit_records(
            state, records, resolve_format(state, fmt), output, columns=cols, title="BEA datasets"
        )

    @datasets_app.command("show")
    @handle_errors
    def datasets_show(
        ctx: typer.Context,
        dataset: DATASET_POS,
        refresh: REFRESH_OPT = False,
        fmt: FORMAT_OPT = None,
        output: OUTPUT_OPT = None,
        columns: COLUMNS_OPT = None,
    ) -> None:
        """List the parameters of one dataset (GetParameterList; cached 7 days)."""
        state = get_state(ctx)
        params = load_parameters(state, dataset, refresh=refresh)
        records = [p.to_record() for p in params]
        cols = select_columns(records, parse_columns(columns))
        emit_records(
            state,
            records,
            resolve_format(state, fmt),
            output,
            columns=cols,
            title=f"{canonical_name(dataset)} parameters",
        )

    # -- search -------------------------------------------------------------------
    @app.command("search", rich_help_panel="Discovery")
    @handle_errors
    def search(
        ctx: typer.Context,
        query: Annotated[
            list[str],
            typer.Argument(help="Free-text query, e.g. 'real gdp' or 'state personal income'."),
        ],
        dataset: DATASET_OPT = None,
        kind: Annotated[
            str, typer.Option("--kind", "-k", help="What to search: tables, datasets or all.")
        ] = "tables",
        limit: LIMIT_OPT = 20,
        min_score: MIN_SCORE_OPT = 55.0,
        fmt: FORMAT_OPT = None,
        output: OUTPUT_OPT = None,
        columns: COLUMNS_OPT = None,
    ) -> None:
        """Fuzzy-search the bundled catalog of popular tables and the dataset list (offline).

        Typos and word order are tolerated. Each hit includes a ready-to-run
        `command`. For every table of a dataset use `dismal bea tables list DATASET --query ...`.
        """
        state = get_state(ctx)
        text = " ".join(query).strip()
        if not text:
            raise typer.BadParameter("empty query")
        if kind not in {"tables", "datasets", "all"}:
            raise typer.BadParameter("--kind must be tables, datasets or all")
        hits = []
        if kind in {"tables", "all"}:
            hits += search_tables(
                text, table_catalog(), dataset=dataset, limit=limit, min_score=min_score
            )
        if kind in {"datasets", "all"}:
            hits += search_datasets(
                text, load_datasets(state, offline=True), limit=limit, min_score=min_score
            )
        hits.sort(key=lambda h: -h.score)  # stable: keeps catalog order within a score
        if limit:
            hits = hits[:limit]
        records = [h.to_record() for h in hits]
        if not records:
            warn(
                state,
                f"no matches for {text!r} (try a lower --min-score or `dismal bea tables list`)",
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

    # -- tables -------------------------------------------------------------------
    tables_app = typer.Typer(help="Discover the tables of a dataset and their lines.")
    app.add_typer(tables_app, name="tables", rich_help_panel="Discovery")

    @tables_app.command("list")
    @handle_errors
    def tables_list(
        ctx: typer.Context,
        dataset: DATASET_POS,
        query: QUERY_OPT = None,
        limit: LIMIT_OPT = 50,
        min_score: MIN_SCORE_OPT = 60.0,
        refresh: REFRESH_OPT = False,
        fmt: FORMAT_OPT = None,
        output: OUTPUT_OPT = None,
        columns: COLUMNS_OPT = None,
    ) -> None:
        """List every table of a dataset (GetParameterValues for TableName/TableID; cached 7 days).

        Use --query to fuzzy-filter by title; --limit 0 lists everything.
        """
        state = get_state(ctx)
        name = canonical_name(dataset)
        dinfo = dataset_info(name)
        if not dinfo.table_param:
            raise typer.BadParameter(
                f"{name} has no tables; list its parameters with `dismal bea datasets show {name}` "
                f"and their values with `dismal bea values {name} PARAMETER`"
            )
        values = load_values(state, name, dinfo.table_param, refresh=refresh)
        records = [
            {
                "table": r["key"],
                "title": r["description"],
                **{k: v for k, v in r.items() if k not in {"key", "description"}},
            }
            for r in values_to_records(values)
        ]
        records = _filtered_records(
            query, records, limit=limit, min_score=min_score, id_col="table", text_cols=("title",)
        )
        if not records:
            warn(state, "no tables matched")
        cols = select_columns(records, parse_columns(columns))
        emit_records(
            state,
            records,
            resolve_format(state, fmt),
            output,
            columns=cols,
            title=f"{name} tables",
        )

    @tables_app.command("show")
    @handle_errors
    def tables_show(
        ctx: typer.Context,
        dataset: DATASET_POS,
        table: Annotated[
            str, typer.Argument(help="Table, e.g. T10101 or SAINC1.", metavar="TABLE")
        ],
        fmt: FORMAT_OPT = None,
        output: OUTPUT_OPT = None,
        columns: COLUMNS_OPT = None,
    ) -> None:
        """Describe the lines (series) of one table with their latest value (one request).

        For NIPA-style datasets the table is fetched for the last two years at
        every frequency; for Regional the valid LineCode values are listed.
        """
        state = get_state(ctx)
        name = canonical_name(dataset)
        dinfo = dataset_info(name)
        if not dinfo.table_param:
            raise typer.BadParameter(
                f"{name} has no tables; use `dismal bea values {name} PARAMETER`"
            )
        if name == "Regional":
            values = load_values(
                state, name, "LineCode", filters={dinfo.table_param: table.strip()}
            )
            records: list[dict[str, Any]] = [
                {"line_code": r["key"], "description": r["description"]}
                for r in values_to_records(values)
            ]
            if not records:
                warn(state, f"no line codes returned for {name} table {table}")
            cols = select_columns(records, parse_columns(columns))
            emit_records(
                state,
                records,
                resolve_format(state, fmt),
                output,
                columns=cols,
                title=f"{name} {table} lines",
            )
            return
        if not (dinfo.has_frequency or name == "FixedAssets" or not dinfo.known):
            raise typer.BadParameter(
                f"`dismal bea tables show` does not support {name}; "
                f"fetch it with `dismal bea data {name}`"
            )
        this_year = current_year()
        params: dict[str, str] = {
            dinfo.table_param: table.strip(),
            dinfo.year_param: f"{this_year - 1},{this_year}",
            **dict(dinfo.defaults),
        }
        if dinfo.has_frequency and dinfo.frequencies:
            params[FREQUENCY] = ",".join(dinfo.frequencies)
        with build_client(state) as client:
            resp = client.get_data(name, params)
        records = []
        for s in resp.series:
            if not s.data:
                continue
            last = s.data[-1]
            rec: dict[str, Any] = {"series_id": s.series_id, "series_title": s.title}
            rec.update(s.attributes)
            rec.update(
                {
                    "unit": last.unit,
                    "unit_mult": last.unit_mult,
                    "frequencies": ",".join(
                        sorted({o.frequency.code for o in s.data}, key="AQM".index)
                    ),
                    "latest_period": last.period,
                    "latest_value": last.value,
                }
            )
            records.append(rec)
        if not records:
            warn(state, f"no series returned for {name} table {table}")
        cols = select_columns(records, parse_columns(columns))
        emit_records(
            state,
            records,
            resolve_format(state, fmt),
            output,
            columns=cols,
            title=f"{name} {table}",
        )

    # -- values -------------------------------------------------------------------
    @app.command("values", rich_help_panel="Discovery")
    @handle_errors
    def values(
        ctx: typer.Context,
        dataset: DATASET_POS,
        parameter: Annotated[
            str,
            typer.Argument(
                help="Parameter name, e.g. TableName, LineCode, GeoFips, Year.",
                metavar="PARAMETER",
            ),
        ],
        query: QUERY_OPT = None,
        filters: Annotated[
            Optional[list[str]],  # noqa: UP045
            typer.Option(
                "--filter",
                "-F",
                help="Narrow by another parameter as NAME=VALUE (GetParameterValuesFiltered).",
                show_default=False,
            ),
        ] = None,
        limit: LIMIT_OPT = 50,
        min_score: MIN_SCORE_OPT = 60.0,
        refresh: REFRESH_OPT = False,
        fmt: FORMAT_OPT = None,
        output: OUTPUT_OPT = None,
        columns: COLUMNS_OPT = None,
    ) -> None:
        """List the valid values of a dataset parameter (cached 7 days).

        Examples:

          dismal bea values Regional LineCode --filter TableName=SAINC1

          dismal bea values Regional GeoFips --query california

          dismal bea values NIPA Year --filter TableName=T10101
        """
        state = get_state(ctx)
        name = canonical_name(dataset)
        flt = parse_params(filters or [])
        raw = load_values(state, name, parameter, filters=flt or None, refresh=refresh)
        records = values_to_records(raw)
        records = _filtered_records(
            query,
            records,
            limit=limit,
            min_score=min_score,
            id_col="key",
            text_cols=("description",),
        )
        if not records:
            warn(state, "no values matched")
        cols = select_columns(records, parse_columns(columns))
        emit_records(
            state,
            records,
            resolve_format(state, fmt),
            output,
            columns=cols,
            title=f"{name} {parameter}",
        )
