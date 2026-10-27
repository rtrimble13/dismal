"""Use the `dismal.bea` package as a library.

Run:  BEA_API_KEY=... python examples/bea/python_api.py

Reference: ../../docs/bea/python-api.md
"""

from __future__ import annotations

from dismal.bea import BEAClient, Settings
from dismal.bea.filters import ObservationFilter
from dismal.bea.periods import Frequency, parse_date_spec
from dismal.bea.records import to_records, to_wide


def main() -> None:
    settings = Settings.from_env()
    with BEAClient.from_settings(settings) as client:
        print(f"limits: {client.limits}")
        resp = client.fetch(
            "NIPA",
            {"Frequency": "Q,A", "Year": ",".join(str(y) for y in range(2019, 2025))},
            table_param="TableName",
            tables=["T10101", "T10105"],
        )
    print(f"{resp.request_count} request(s), {len(resp.series)} series, {len(resp.notes)} notes")

    # Keep Mar 2020 - Jun 2024, quarterly rows only.
    flt = ObservationFilter(
        start=parse_date_spec("2020-03"),
        end=parse_date_spec("2024-06", end=True),
        frequencies=frozenset({Frequency.QUARTERLY}),
    )
    series = flt.apply(resp.series)

    records = to_records(series, dataset="NIPA", include_notes=True, note_text=resp.note_text)
    print(records[0])

    wide = to_wide(records)
    print(wide[-1])

    # Optional: into pandas
    try:
        import pandas as pd
    except ImportError:
        return
    df = pd.DataFrame(records)
    df["date"] = pd.to_datetime(df["date"])
    print(df.pivot(index="date", columns="series_id", values="value").tail())


if __name__ == "__main__":
    main()
