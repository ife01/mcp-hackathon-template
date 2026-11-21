"""Trend classification for weekly respiratory surveillance series.

Pure functions — no I/O. All logic documented in docs/METHODS.md.

THIS IS A SERVER HEURISTIC, NOT AN OFFICIAL CDC CLASSIFICATION.
CDC's official levels (from NHSN) are carried in WeeklyObservation.official_level.
"""

from __future__ import annotations

from dataclasses import dataclass
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
        window_weeks: Total weeks consumed (recent + prior), after trailing
            None-stripping.
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


# ── Thresholds ────────────────────────────────────────────────────────────────

# Minimum non-null observations needed to classify
_MIN_WEEKS = 4

# Half-window size (compare latest N vs prior N)
_HALF = 2

# Signal-specific thresholds
_HOSPITAL_REL = 0.10   # ±10% relative
_HOSPITAL_ABS = 0.1    # ≥0.1 per 100k absolute
_POSITIVITY_ABS = 1.0  # ±1.0 percentage point
_WVAL_REL = 0.15       # ±15% relative

# Small-number guard (admissions count): if both window means are below this,
# classify as insufficient_data to avoid spurious % swings.
_SMALL_NUMBER_THRESHOLD = 10.0


# ── Public API ────────────────────────────────────────────────────────────────


def classify_trend(
    observations: list[WeeklyObservation],
    signal: Signal,
    *,
    counts: list[float | None] | None = None,
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
    # Extract non-null values, dropping trailing Nones
    values = [o.value for o in observations]
    values = _strip_trailing_nones(values)

    insufficient = TrendResult(
        direction=TrendDirection.insufficient_data,
        pct_change=None,
        abs_change=None,
        window_weeks=len(values),
        method="2w_vs_prior_2w",
        basis="server_heuristic",
    )

    if len(values) < _MIN_WEEKS:
        return insufficient

    # Latest _HALF vs prior _HALF
    recent = values[-_HALF:]
    prior = values[-2 * _HALF: -_HALF]

    if len(recent) < _HALF or len(prior) < _HALF:
        return insufficient

    # None check within windows
    if any(v is None for v in recent) or any(v is None for v in prior):
        return insufficient

    recent_mean = sum(recent) / len(recent)  # type: ignore[arg-type]
    prior_mean = sum(prior) / len(prior)      # type: ignore[arg-type]
    abs_change = recent_mean - prior_mean

    # Small-number guard for hospital admissions
    if signal == Signal.hospital_admissions and counts is not None:
        count_vals = _strip_trailing_nones(counts)
        if len(count_vals) >= 2 * _HALF:
            recent_counts = count_vals[-_HALF:]
            prior_counts = count_vals[-2 * _HALF: -_HALF]
            both = [c for c in recent_counts + prior_counts if c is not None]
            if both and sum(both) / len(both) < _SMALL_NUMBER_THRESHOLD:
                return insufficient

    pct_change: float | None = None
    if prior_mean != 0:
        pct_change = abs_change / prior_mean

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
    )


# ── Helpers ───────────────────────────────────────────────────────────────────


def _strip_trailing_nones(values: list) -> list:
    """Remove trailing None entries from a list."""
    idx = len(values)
    while idx > 0 and values[idx - 1] is None:
        idx -= 1
    return values[:idx]


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
        if pct_change is not None and abs(pct_change) >= _WVAL_REL:
            return _up if abs_change > 0 else _dn
        return TrendDirection.stable

    return TrendDirection.stable
