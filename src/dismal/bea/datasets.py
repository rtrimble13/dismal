"""Static knowledge about the BEA datasets.

The API is generic (``GetData`` takes ``datasetname`` plus dataset-specific
parameters), so the CLI needs a little per-dataset knowledge to offer
conveniences such as ``--table``, to build sensible defaults, and to derive a
stable ``series_id`` and ``series_title`` from each data row. Unknown datasets
fall back to a generic rule (join every dimension column), so new datasets keep
working without a release.
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass, field
from typing import Any

TABLE_NAME = "TableName"
TABLE_ID = "TableID"
YEAR = "Year"
FREQUENCY = "Frequency"


@dataclass(frozen=True)
class DatasetInfo:
    """What the CLI knows about one dataset (see ``docs/table-ids.md``)."""

    name: str
    description: str = ""
    table_param: str | None = None  # TableName or TableID, when the dataset has tables
    has_frequency: bool = False  # accepts a Frequency parameter
    frequencies: tuple[str, ...] = ()  # valid Frequency codes
    all_years: str = "ALL"  # the Year value meaning "every year"
    required: tuple[str, ...] = ()  # parameters GetData needs
    defaults: Mapping[str, str] = field(default_factory=dict)
    series_key: tuple[str, ...] = ()  # columns whose values identify a series
    title_columns: tuple[str, ...] = ()  # columns that describe a series
    known: bool = True

    @property
    def year_param(self) -> str:
        return YEAR


DATASETS: dict[str, DatasetInfo] = {
    d.name: d
    for d in (
        DatasetInfo(
            "NIPA",
            "Standard NIPA tables",
            table_param=TABLE_NAME,
            has_frequency=True,
            frequencies=("A", "Q", "M"),
            all_years="X",
            required=(TABLE_NAME, FREQUENCY, YEAR),
            series_key=("SeriesCode",),
            title_columns=("LineDescription",),
        ),
        DatasetInfo(
            "NIUnderlyingDetail",
            "Standard NI underlying detail tables",
            table_param=TABLE_NAME,
            has_frequency=True,
            frequencies=("A", "Q", "M"),
            all_years="X",
            required=(TABLE_NAME, FREQUENCY, YEAR),
            series_key=("SeriesCode",),
            title_columns=("LineDescription",),
        ),
        DatasetInfo(
            "FixedAssets",
            "Standard Fixed Assets tables",
            table_param=TABLE_NAME,
            all_years="X",
            required=(TABLE_NAME, YEAR),
            series_key=("SeriesCode",),
            title_columns=("LineDescription",),
        ),
        DatasetInfo(
            "Regional",
            "Regional data sets (state, county, metro)",
            table_param=TABLE_NAME,
            required=(TABLE_NAME, "LineCode", "GeoFips", YEAR),
            series_key=("Code", "GeoFips"),
            title_columns=("GeoName",),
        ),
        DatasetInfo(
            "GDPbyIndustry",
            "GDP by Industry",
            table_param=TABLE_ID,
            has_frequency=True,
            frequencies=("A", "Q"),
            required=(TABLE_ID, FREQUENCY, "Industry", YEAR),
            defaults={"Industry": "ALL"},
            series_key=(TABLE_ID, "Industry"),
            title_columns=("IndustrYDescription",),
        ),
        DatasetInfo(
            "UnderlyingGDPbyIndustry",
            "Underlying GDP by Industry",
            table_param=TABLE_ID,
            has_frequency=True,
            frequencies=("A", "Q"),
            required=(TABLE_ID, FREQUENCY, "Industry", YEAR),
            defaults={"Industry": "ALL"},
            series_key=(TABLE_ID, "Industry"),
            title_columns=("IndustrYDescription",),
        ),
        DatasetInfo(
            "ITA",
            "International Transactions Accounts",
            has_frequency=True,
            frequencies=("A", "QSA", "QNSA"),
            series_key=("TimeSeriesId",),
            title_columns=("TimeSeriesDescription",),
        ),
        DatasetInfo(
            "IIP",
            "International Investment Position",
            has_frequency=True,
            frequencies=("A", "QNSA"),
            series_key=("TimeSeriesId",),
            title_columns=("TimeSeriesDescription",),
        ),
        DatasetInfo(
            "InputOutput",
            "Input-Output Data",
            table_param=TABLE_ID,
            required=(TABLE_ID, YEAR),
            series_key=(TABLE_ID, "RowCode", "ColCode"),
            title_columns=("RowDescr", "ColDescr"),
        ),
        DatasetInfo(
            "IntlServTrade",
            "International Services Trade",
            series_key=("TimeSeriesId",),
            title_columns=("TimeSeriesDescription",),
        ),
        DatasetInfo(
            "IntlServSTA",
            "International Services Supplied Through Affiliates",
            series_key=("TimeSeriesId",),
            title_columns=("TimeSeriesDescription",),
        ),
        DatasetInfo(
            "MNE",
            "Multinational Enterprises",
            required=("DirectionOfInvestment", "Classification", YEAR),
            series_key=("SeriesID", "RowCode", "ColumnCode"),
            title_columns=("SeriesName", "Row", "Column"),
        ),
        DatasetInfo("APIDatasetMetaData", "Metadata about other API datasets"),
    )
}

_BY_LOWER = {name.lower(): name for name in DATASETS}


def canonical_name(name: str) -> str:
    """Return the dataset's official spelling (``nipa`` -> ``NIPA``); unknown names pass through."""
    text = name.strip()
    return _BY_LOWER.get(text.lower(), text)


def dataset_info(name: str) -> DatasetInfo:
    """Static information for a dataset; a generic fallback for unknown ones."""
    canonical = canonical_name(name)
    info = DATASETS.get(canonical)
    if info is None:
        return DatasetInfo(canonical, known=False)
    return info


def all_years_token(name: str) -> str:
    return dataset_info(name).all_years


# Columns of a data row that never identify a series.
TIME_COLUMNS = frozenset({"TimePeriod", "Year", "Quarter"})
VALUE_COLUMNS = frozenset(
    {"DataValue", "DataValueUnformatted", "CL_UNIT", "UNIT_MULT", "NoteRef", "METRIC_NAME"}
)
_DESCRIPTION_HINTS = ("descr", "description", "name", "desc")


def series_key_columns(info: DatasetInfo, row: Mapping[str, Any]) -> list[str]:
    """Columns that identify a series in ``row`` (declared, else every other dimension)."""
    declared = [c for c in info.series_key if c in row]
    if declared:
        return declared
    skip = TIME_COLUMNS | VALUE_COLUMNS | {FREQUENCY}
    return [
        c
        for c in row
        if c not in skip
        and not any(h in c.lower() for h in _DESCRIPTION_HINTS)
        and row[c] not in (None, "")
    ]


def title_columns(info: DatasetInfo, row: Mapping[str, Any]) -> list[str]:
    declared = [c for c in info.title_columns if c in row and row[c] not in (None, "")]
    if declared:
        return declared
    skip = TIME_COLUMNS | VALUE_COLUMNS
    return [
        c
        for c in row
        if c not in skip
        and any(h in c.lower() for h in _DESCRIPTION_HINTS)
        and row[c] not in (None, "")
    ][:1]
