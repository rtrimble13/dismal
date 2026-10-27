"""Client-side filtering of observations (date ranges, frequencies, latest only).

The API's ``Year`` parameter is the only time filter it understands, so
month- and quarter-level bounds are applied locally after fetching (see
``docs/adr/0007-client-side-filtering.md``).
"""

from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass

from dismal.bea.models import Observation, Series
from dismal.bea.periods import Frequency, YearMonth, period_in_range


@dataclass(frozen=True)
class ObservationFilter:
    start: YearMonth | None = None
    end: YearMonth | None = None
    frequencies: frozenset[Frequency] | None = None
    only_latest: bool = False

    def matches(self, obs: Observation) -> bool:
        info = obs.period_info
        if self.frequencies is not None and info.frequency not in self.frequencies:
            return False
        return period_in_range(info, self.start, self.end)

    def apply(self, series: Iterable[Series]) -> list[Series]:
        out: list[Series] = []
        for s in series:
            kept = [o for o in s.data if self.matches(o)]
            if self.only_latest and kept:
                kept = kept[-1:]
            out.append(
                Series(series_id=s.series_id, title=s.title, data=kept, attributes=s.attributes)
            )
        return out

    @property
    def is_noop(self) -> bool:
        return (
            self.start is None
            and self.end is None
            and self.frequencies is None
            and not self.only_latest
        )
