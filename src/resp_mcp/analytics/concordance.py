"""Cross-signal concordance with lag guard.

Pure functions — no I/O. Compares trends across NHSN, NWSS, and NREVSS signals
to produce a pattern classification and explanation.

THIS IS A SERVER HEURISTIC, NOT AN OFFICIAL CDC CLASSIFICATION.

Lag Guard (critical): If the spread between the most recent and least recent
latest_week_ending across usable signals exceeds 14 days, concordance is
qualified with a temporal_alignment_note and the explanation is adjusted.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

from resp_mcp.analytics.trend import TrendDirection, TrendResult
from resp_mcp.models.common import Provenance, Signal

_LAG_THRESHOLD_DAYS = 14


ConcordancePattern = Literal[
    "concordant_increase",
    "concordant_decrease",
    "early_warning",
    "stable",
    "mixed",
    "insufficient_data",
]


@dataclass
class SignalTrendInput:
    """Trend result + provenance for one signal, used as concordance input."""

    signal: Signal
    trend: TrendResult
    provenance: Provenance


@dataclass
class ConcordanceResult:
    """Cross-signal concordance classification.

    Attributes:
        pattern: Overall pattern classification.
        signals_used: Which signals contributed to the assessment.
        temporal_alignment_note: Set when signals span >14 days apart; None
            when signals are temporally aligned.
        explanation: 1–2 sentence plain-English explanation.
    """

    pattern: ConcordancePattern
    signals_used: list[Signal]
    temporal_alignment_note: str | None
    explanation: str


def assess_concordance(
    signal_trends: list[SignalTrendInput],
) -> ConcordanceResult:
    """Classify multi-signal concordance with a lag guard.

    Signals with direction=insufficient_data are excluded from pattern
    classification (but noted in explanation).

    Args:
        signal_trends: List of SignalTrendInput objects (1–3 signals).

    Returns:
        ConcordanceResult with pattern and explanation.
    """
    if not signal_trends:
        return ConcordanceResult(
            pattern="insufficient_data",
            signals_used=[],
            temporal_alignment_note=None,
            explanation="No signals available for concordance assessment.",
        )

    # Filter to signals with usable (non-insufficient) data
    usable = [
        st
        for st in signal_trends
        if st.trend.direction != TrendDirection.insufficient_data
    ]
    insufficient_count = len(signal_trends) - len(usable)

    if not usable:
        return ConcordanceResult(
            pattern="insufficient_data",
            signals_used=[],
            temporal_alignment_note=None,
            explanation=(
                "All signals have insufficient data for trend classification."
            ),
        )

    signals_used = [st.signal for st in usable]
    if len(set(signals_used)) < 2:
        return ConcordanceResult(
            pattern="insufficient_data",
            signals_used=signals_used,
            temporal_alignment_note=None,
            explanation="At least two distinct usable signals are required for "
            "concordance.",
        )

    # ── Lag guard ─────────────────────────────────────────────────────────────
    week_endings = [
        st.provenance.latest_week_ending
        for st in usable
        if st.provenance.latest_week_ending is not None
    ]
    lag_note: str | None = None
    if len(week_endings) >= 2:
        spread = (max(week_endings) - min(week_endings)).days
        if spread > _LAG_THRESHOLD_DAYS:
            lag_note = (
                f"Signals span different weeks "
                f"({min(week_endings).isoformat()} to "
                f"{max(week_endings).isoformat()}, "
                f"{spread} days apart); "
                "interpret concordance with caution."
            )

    # ── Pattern classification ─────────────────────────────────────────────────
    _inc = TrendDirection.increasing
    _dec = TrendDirection.decreasing
    _sta = TrendDirection.stable
    n_increasing = sum(1 for st in usable if st.trend.direction == _inc)
    n_decreasing = sum(1 for st in usable if st.trend.direction == _dec)
    n_stable = sum(1 for st in usable if st.trend.direction == _sta)

    # Determine pattern
    pattern: ConcordancePattern
    if n_increasing == len(usable):
        pattern = "concordant_increase"
    elif n_decreasing == len(usable):
        pattern = "concordant_decrease"
    elif n_stable == len(usable):
        pattern = "stable"
    elif n_increasing >= 1 and n_stable >= 1 and n_decreasing == 0:
        # At least one rising, rest stable — early warning signal
        pattern = "early_warning"
    elif n_decreasing >= 1 and n_stable >= 1 and n_increasing == 0:
        # At least one falling, rest stable — could be early recovery
        pattern = "mixed"
    else:
        # Mixed signals across increase/decrease
        pattern = "mixed"

    # ── Explanation ───────────────────────────────────────────────────────────
    explanation = _build_explanation(pattern, usable, insufficient_count, lag_note)

    return ConcordanceResult(
        pattern=pattern,
        signals_used=signals_used,
        temporal_alignment_note=lag_note,
        explanation=explanation,
    )


def _build_explanation(
    pattern: ConcordancePattern,
    usable: list[SignalTrendInput],
    insufficient_count: int,
    lag_note: str | None,
) -> str:
    signal_names = _signal_label_list(usable)
    n = len(usable)

    base: str
    if pattern == "concordant_increase":
        base = f"All {n} available signal(s) ({signal_names}) show an increasing trend."
    elif pattern == "concordant_decrease":
        base = f"All {n} available signal(s) ({signal_names}) show a decreasing trend."
    elif pattern == "stable":
        base = f"All {n} available signal(s) ({signal_names}) show a stable trend."
    elif pattern == "early_warning":
        rising = [
            st.signal.value
            for st in usable
            if st.trend.direction == TrendDirection.increasing
        ]
        base = (
            f"{', '.join(rising)} show(s) an increasing trend while other "
            f"signal(s) remain stable; this may be an early-warning pattern."
        )
    elif pattern == "mixed":
        base = (
            f"Signals show mixed directions ({signal_names}); "
            "no consistent trend across sources."
        )
    else:
        base = "Insufficient data to assess concordance."

    suffix = ""
    if insufficient_count > 0:
        suffix += (
            f" {insufficient_count} signal(s) had insufficient data and were excluded."
        )
    if lag_note:
        suffix += f" Note: {lag_note}"

    return base + suffix


def _signal_label_list(usable: list[SignalTrendInput]) -> str:
    labels = {
        Signal.hospital_admissions: "hospital admissions",
        Signal.wastewater: "wastewater",
        Signal.test_positivity: "test positivity",
    }
    return ", ".join(labels.get(st.signal, st.signal.value) for st in usable)
