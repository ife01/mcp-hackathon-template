"""Prior-season comparison for weekly respiratory surveillance series.

Pure functions — no I/O. Aligns series by week_of_season and computes rank
vs. prior peaks and percentage of prior peak value.

THIS IS A SERVER HEURISTIC, NOT AN OFFICIAL CDC CLASSIFICATION.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date

from resp_mcp.models.common import WeeklyObservation
from resp_mcp.reference.epiweeks import (
    same_week_prior_seasons,
    season_of,
    week_of_season,
)

# Minimum years before NHSN mandatory-reporting transition (2024) that may be
# excluded from comparisons when the caller sets exclude_pre_transition=True.
_NHSN_TRANSITION_YEAR = 2024


@dataclass
class PriorSeasonPoint:
    """A single data-point from a prior season at the equivalent week."""

    season: str         # e.g. "2023-24"
    week_ending: date   # week-ending date of the aligned week
    week_of_season: int # 1-based season week index
    value: float | None
    alignment_note: str | None = None  # set when nearest-week fallback used


@dataclass
class SeasonComparison:
    """Comparison of the current week against equivalent weeks in prior seasons.

    Attributes:
        current_season: Season label (e.g. "2025-26").
        current_week_of_season: 1-based week index within the current season.
        current_value: Most recent non-null value (may be None).
        prior: Per-season aligned data points (one per prior season).
        rank_vs_prior: Rank of current_value among all compared values, with
            1 = highest.  None when current_value is None.
        pct_of_prior_peak: current_value / max(prior_season_peaks) * 100.
            None when current_value or prior peaks are unavailable.
        method: Machine-readable method identifier.
        notes: Any caveats (exclusions, alignment fallbacks, etc.).
    """

    current_season: str
    current_week_of_season: int
    current_value: float | None
    prior: list[PriorSeasonPoint]
    rank_vs_prior: int | None
    pct_of_prior_peak: float | None
    method: str
    notes: list[str] = field(default_factory=list)


def compare_to_prior_seasons(
    observations: list[WeeklyObservation],
    reference_date: date,
    n_seasons: int = 3,
    *,
    exclude_pre_transition_nhsn: bool = False,
) -> SeasonComparison:
    """Compare the current-season value at reference_date to equivalent prior weeks.

    Args:
        observations: Time-ordered (ascending) WeeklyObservations for one
            signal/jurisdiction/pathogen, spanning multiple seasons if available.
        reference_date: The "current" week-ending date to compare from.
        n_seasons: Number of prior seasons to include.
        exclude_pre_transition_nhsn: When True, exclude observations from
            seasons that started before _NHSN_TRANSITION_YEAR (2024) and add
            a provenance note.

    Returns:
        SeasonComparison with aligned prior-season points and ranking.
    """
    # Build a lookup from week_ending date → value
    obs_by_date: dict[date, float | None] = {
        o.week_ending: o.value for o in observations
    }

    current_season = season_of(reference_date)
    current_wos = week_of_season(reference_date)
    current_value = obs_by_date.get(reference_date)
    notes: list[str] = []

    # Get prior-season equivalent dates
    prior_dates = same_week_prior_seasons(reference_date, n_seasons)

    prior_points: list[PriorSeasonPoint] = []
    excluded_seasons: list[str] = []

    for pd in prior_dates:
        ps = season_of(pd)
        ps_start_year = int(ps.split("-")[0])

        if exclude_pre_transition_nhsn and ps_start_year < _NHSN_TRANSITION_YEAR:
            excluded_seasons.append(ps)
            continue

        # Try exact match first, then ±1 week fallback
        value = obs_by_date.get(pd)
        alignment_note: str | None = None

        if value is None:
            # Try neighbours (±1 week = ±7 days)
            for delta in (-7, 7):
                neighbour = date.fromordinal(pd.toordinal() + delta)
                if neighbour in obs_by_date:
                    value = obs_by_date[neighbour]
                    alignment_note = (
                        f"Aligned to nearest available week "
                        f"({neighbour.isoformat()}, ±1 week fallback)."
                    )
                    break

        prior_points.append(
            PriorSeasonPoint(
                season=ps,
                week_ending=pd,
                week_of_season=week_of_season(pd),
                value=value,
                alignment_note=alignment_note,
            )
        )

    if excluded_seasons:
        notes.append(
            f"Season(s) {', '.join(excluded_seasons)} excluded: pre-2024 NHSN "
            "mandatory-reporting transition may affect comparability."
        )

    # Rank current value among all values (current + prior), highest = 1
    rank: int | None = None
    pct_of_prior_peak: float | None = None

    if current_value is not None:
        # Collect only non-None prior values
        prior_values = [p.value for p in prior_points if p.value is not None]

        # Rank = 1 + number of prior values strictly greater than current
        rank = 1 + sum(1 for pv in prior_values if pv > current_value)

        # pct_of_prior_peak: only full prior seasons contribute to peaks
        # (use all available prior data since we're at a specific week)
        if prior_values:
            prior_peak = max(prior_values)
            if prior_peak > 0:
                pct_of_prior_peak = current_value / prior_peak * 100

    return SeasonComparison(
        current_season=current_season,
        current_week_of_season=current_wos,
        current_value=current_value,
        prior=prior_points,
        rank_vs_prior=rank,
        pct_of_prior_peak=pct_of_prior_peak,
        method="week_of_season_aligned",
        notes=notes,
    )
