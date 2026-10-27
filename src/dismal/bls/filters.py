"""Client-side filtering of observations (date ranges, frequencies, annual averages).

The API only understands whole years, so finer-grained filters are applied
locally after fetching (see ``docs/adr/0007-client-side-filtering.md``).
"""

from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass

from dismal.bls.models import Observation, Series
from dismal.bls.periods import Frequency, YearMonth, period_in_range


@dataclass(frozen=True)
class ObservationFilter:
    start: YearMonth | None = None
    end: YearMonth | None = None
    frequencies: frozenset[Frequency] | None = None
    include_annual_average: bool = True
    only_latest: bool = False

    def matches(self, obs: Observation) -> bool:
        info = obs.period_info
        if not self.include_annual_average and info.annual_average:
            return False
        if self.frequencies is not None and info.frequency not in self.frequencies:
            return False
        if self.only_latest and not obs.latest:
            return False
        return period_in_range(obs.year, info, self.start, self.end)

    def apply(self, series: Iterable[Series]) -> list[Series]:
        out: list[Series] = []
        for s in series:
            kept = [o for o in s.data if self.matches(o)]
            out.append(Series(series_id=s.series_id, data=kept, catalog=s.catalog))
        return out

    @property
    def is_noop(self) -> bool:
        return (
            self.start is None
            and self.end is None
            and self.frequencies is None
            and self.include_annual_average
            and not self.only_latest
        )
