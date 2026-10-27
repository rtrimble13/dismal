"""Use the `dismal.bls` package as a library.

Run:  BLS_API_KEY=... python examples/bls/python_api.py
"""

from __future__ import annotations

from dismal.bls import BLSClient, Settings
from dismal.bls.filters import ObservationFilter
from dismal.bls.periods import Frequency, parse_date_spec
from dismal.bls.records import to_records, to_wide


def main() -> None:
    settings = Settings.from_env()
    with BLSClient.from_settings(settings, on_message=lambda m: print("note:", m)) as client:
        print(f"limits: {client.limits}")
        resp = client.fetch(
            ["LNS14000000", "CUUR0000SA0"],
            start_year=2019,
            end_year=2024,
            calculations=True,
        )
    print(f"{resp.request_count} request(s), {len(resp.series)} series")

    # Keep Mar 2020 - Jun 2024, monthly rows only.
    flt = ObservationFilter(
        start=parse_date_spec("2020-03"),
        end=parse_date_spec("2024-06", end=True),
        frequencies=frozenset({Frequency.MONTHLY}),
    )
    series = flt.apply(resp.series)

    records = to_records(series, include_calculations=True)
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
