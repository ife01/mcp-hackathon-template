"""Trend classification for weekly respiratory surveillance series.

Pure functions — no I/O. All logic documented in docs/METHODS.md.

THIS IS A SERVER HEURISTIC, NOT AN OFFICIAL CDC CLASSIFICATION.
CDC's official levels (from NHSN) are carried in WeeklyObservation.official_level.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date
from enum import Enum
from typing import Literal

from resp_mcp.models.common import Signal, WeeklyObservation

# ── Types ─────────────────────────────────────────────────────────────────────


class TrendDirection(str, Enum):
    increasing = "increasing"
    stable = "stable"
    decreasing = "decreasing"
    insufficient_data = "insufficient_data"


@dataclass
class TrendResult:
    """Outcome of a heuristic trend classification.

    Attributes:
        direction: Classified direction of change.
        pct_change: Relative change from prior window to recent window (may be
            None for insufficient_data or zero-denominator cases).
        abs_change: Absolute change (recent_mean - prior_mean), same units as
            the input series.
        window_weeks: Recent observation slots inspected, at most four.
        method: Machine-readable method identifier.
        basis: Whether the classification is from an official CDC level change
            or the server heuristic.
    """

    direction: TrendDirection
    pct_change: float | None
    abs_change: float | None
    window_weeks: int
    method: str
    basis: Literal["server_heuristic", "official_cdc_level_change"]
    notes: list[str] = field(default_factory=list)


# ── Thresholds ────────────────────────────────────────────────────────────────

# Minimum non-null observations needed to classify
_MIN_WEEKS = 4

# Half-window size (compare latest N vs prior N)
_HALF = 2

# Signal-specific thresholds
_HOSPITAL_REL = 0.10  # ±10% relative
_HOSPITAL_ABS = 0.1  # ≥0.1 per 100k absolute
_POSITIVITY_ABS = 1.0  # ±1.0 percentage point
_WVAL_REL = 0.15  # ±15% relative

# Small-number guard (admissions count): if both window means are below this,
# classify as insufficient_data to avoid spurious % swings.
_SMALL_NUMBER_THRESHOLD = 10.0


# ── Public API ────────────────────────────────────────────────────────────────


def classify_trend(
    observations: list[WeeklyObservation],
    signal: Signal,
    *,
    counts: list[float | None] | None = None,
    reference_date: date | None = None,
) -> TrendResult:
    """Classify trend direction for a weekly surveillance series.

    Args:
        observations: Time-ordered (ascending) WeeklyObservations for one
            signal/jurisdiction/pathogen.  Should already be sorted.
        signal: Which signal this is (determines thresholds).
        counts: Optional parallel list of raw counts (e.g. admission counts)
            used for the small-number guard. Length must match observations.

    Returns:
        TrendResult with direction and supporting statistics.
    """
    # Preserve the requested endpoint and align counts with sorted observations.
    if counts is not None and len(counts) != len(observations):
        raise ValueError("counts must align one-to-one with observations")
    pairs = sorted(
        zip(
            observations,
            counts if counts is not None else [o.raw_count for o in observations],
        ),
        key=lambda pair: pair[0].week_ending,
    )
    # Missing recent observations must not move the trend endpoint backwards.
    window = pairs[-4:]
    values = [o.value for o, _ in window]

    insufficient = TrendResult(
        direction=TrendDirection.insufficient_data,
        pct_change=None,
        abs_change=None,
        window_weeks=len(values),
        method="2w_vs_prior_2w",
        basis="server_heuristic",
        notes=[
            "Four consecutive weekly observations with usable values are "
            "required; missing recent values are not backdated."
        ],
    )

    if len(values) < _MIN_WEEKS:
        return insufficient

    dates = [o.week_ending for o, _ in window]
    if any((b - a).days != 7 for a, b in zip(dates, dates[1:])):
        return insufficient

    if reference_date is not None and (reference_date - dates[-1]).days > 21:
        insufficient.notes.append(
            "Latest observation is more than 21 days before the requested cutoff."
        )
        return insufficient

    # Latest _HALF vs prior _HALF
    recent = values[-_HALF:]
    prior = values[-2 * _HALF : -_HALF]

    if len(recent) < _HALF or len(prior) < _HALF:
        return insufficient

    # None check within windows
    if any(v is None for v in recent) or any(v is None for v in prior):
        return insufficient

    recent_mean = sum(recent) / len(recent)  # type: ignore[arg-type]
    prior_mean = sum(prior) / len(prior)  # type: ignore[arg-type]
    abs_change = recent_mean - prior_mean

    # Small-number guard for hospital admissions
    if signal == Signal.hospital_admissions:
        count_vals = [c for _, c in window]
        if all(c is not None for c in count_vals):
            prior_count_mean = sum(count_vals[:2]) / 2
            recent_count_mean = sum(count_vals[2:]) / 2
            if max(prior_count_mean, recent_count_mean) < _SMALL_NUMBER_THRESHOLD:
                insufficient.notes.append(
                    "Both two-week windows average fewer than 10 admissions."
                )
                return insufficient

    pct_change: float | None = None
    if prior_mean != 0:
        pct_change = abs_change / prior_mean

    notes = []
    if signal == Signal.hospital_admissions and any(c is None for _, c in window):
        notes.append(
            "Admission counts unavailable for part of the window; "
            "small-number guard could not be assessed."
        )
    direction = _classify_direction(
        signal, prior_mean, recent_mean, abs_change, pct_change
    )

    return TrendResult(
        direction=direction,
        pct_change=pct_change,
        abs_change=abs_change,
        window_weeks=len(values),
        method="2w_vs_prior_2w",
        basis="server_heuristic",
        notes=notes,
    )


# ── Helpers ───────────────────────────────────────────────────────────────────


def _classify_direction(
    signal: Signal,
    prior_mean: float,
    recent_mean: float,
    abs_change: float,
    pct_change: float | None,
) -> TrendDirection:
    _up = TrendDirection.increasing
    _dn = TrendDirection.decreasing

    if signal == Signal.hospital_admissions:
        if prior_mean == 0 and abs(abs_change) >= _HOSPITAL_ABS:
            return _up if abs_change > 0 else _dn
        if (
            pct_change is not None
            and abs(pct_change) >= _HOSPITAL_REL
            and abs(abs_change) >= _HOSPITAL_ABS
        ):
            return _up if abs_change > 0 else _dn
        return TrendDirection.stable

    if signal == Signal.test_positivity:
        if abs(abs_change) >= _POSITIVITY_ABS:
            return _up if abs_change > 0 else _dn
        return TrendDirection.stable

    if signal == Signal.wastewater:
        if prior_mean == 0 and recent_mean != 0:
            return TrendDirection.insufficient_data
        if pct_change is not None and abs(pct_change) >= _WVAL_REL:
            return _up if abs_change > 0 else _dn
        return TrendDirection.stable

    return TrendDirection.stable
