"""Use the `dismal.fred` package as a library.

Run:  FRED_API_KEY=... python examples/fred/python_api.py
"""

from __future__ import annotations

from datetime import date

from dismal.fred import FREDClient, Settings
from dismal.fred.records import to_records, to_wide


def main() -> None:
    settings = Settings.from_env()
    with FREDClient.from_settings(settings, on_message=lambda m: print("note:", m)) as client:
        print(f"limits: {client.limits}")
        resp = client.fetch(
            ["UNRATE", "CPIAUCSL"],
            start=date(2019, 1, 1),
            units="pc1",  # percent change from a year ago, computed by the API
            meta=True,
        )
        info = client.series_info("DGS10")
        print(info.title, info.frequency, info.units, info.observation_end)
    print(f"{resp.request_count} request(s), {len(resp.series)} series")

    records = to_records(resp.series, include_meta=True)
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
