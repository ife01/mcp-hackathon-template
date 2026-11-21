"""Deterministic narrative generation from surveillance data.

Pure functions — no I/O, no LLM. Produces 2–4 plain English sentences from
templates. Numbers are rounded to 1 decimal place.

THIS OUTPUT IS A SERVER HEURISTIC, NOT AN OFFICIAL CDC COMMUNICATION.
"""

from __future__ import annotations

from datetime import date

from resp_mcp.analytics.concordance import ConcordanceResult
from resp_mcp.analytics.seasons import SeasonComparison
from resp_mcp.analytics.trend import TrendDirection, TrendResult
from resp_mcp.models.common import Pathogen, Signal


def build_snapshot_narrative(
    jurisdiction: str,
    pathogen: Pathogen,
    signal: Signal,
    latest_value: float | None,
    latest_week_ending: date | None,
    unit: str,
    official_level: str | None,
    trend: TrendResult | None,
    comparison: SeasonComparison | None,
    concordance: ConcordanceResult | None,
) -> str:
    """Build a 2–4 sentence plain-English summary of the current situation.

    Args:
        jurisdiction: Jurisdiction code (e.g. "GA").
        pathogen: Pathogen enum value.
        signal: Signal enum value.
        latest_value: Most recent non-null value (may be None).
        latest_week_ending: Week-ending date of the latest observation.
        unit: Unit string (e.g. "admissions_per_100k").
        official_level: CDC official level string if available (e.g. "Low").
        trend: TrendResult from analytics/trend.py (may be None).
        comparison: SeasonComparison from analytics/seasons.py (may be None).
        concordance: ConcordanceResult from analytics/concordance.py (may be None).

    Returns:
        A 2–4 sentence narrative string. All numbers rounded to 1 decimal place.
    """
    parts: list[str] = []

    # Sentence 1: current level
    parts.append(_current_level_sentence(
        jurisdiction, pathogen, signal, latest_value, latest_week_ending,
        unit, official_level,
    ))

    # Sentence 2: trend
    if trend is not None:
        parts.append(_trend_sentence(signal, trend))

    # Sentence 3: season comparison
    if comparison is not None and comparison.current_value is not None:
        parts.append(_season_sentence(comparison))

    # Sentence 4: concordance (only if multi-signal)
    if concordance is not None and len(concordance.signals_used) >= 2:
        parts.append(_concordance_sentence(concordance))

    return " ".join(parts)


# ── Sentence builders ─────────────────────────────────────────────────────────


def _current_level_sentence(
    jurisdiction: str,
    pathogen: Pathogen,
    signal: Signal,
    value: float | None,
    week_ending: date | None,
    unit: str,
    official_level: str | None,
) -> str:
    pathogen_label = _pathogen_label(pathogen)
    signal_label = _signal_label(signal)
    week_str = week_ending.isoformat() if week_ending else "unknown week"

    if value is None:
        return (
            f"{pathogen_label} {signal_label} in {jurisdiction} "
            f"for the week ending {week_str} is unavailable."
        )

    value_str = f"{round(value, 1)}"
    unit_str = _unit_label(unit)

    base = (
        f"{pathogen_label} {signal_label} in {jurisdiction} "
        f"was {value_str} {unit_str} for the week ending {week_str}."
    )

    if official_level:
        base = base[:-1] + f", classified as {official_level} by CDC."

    return base


def _trend_sentence(signal: Signal, trend: TrendResult) -> str:
    direction = trend.direction

    if direction == TrendDirection.insufficient_data:
        return "Trend direction cannot be determined from available data."

    direction_word = {
        TrendDirection.increasing: "increasing",
        TrendDirection.decreasing: "decreasing",
        TrendDirection.stable: "stable",
    }[direction]

    if trend.pct_change is not None and direction != TrendDirection.stable:
        pct = round(abs(trend.pct_change) * 100, 1)
        return (
            f"The {_signal_label(signal)} trend is {direction_word} "
            f"({pct}% change over the past {trend.window_weeks} weeks; "
            f"server heuristic, not official CDC classification)."
        )

    return (
        f"The {_signal_label(signal)} trend is {direction_word} "
        f"over the past {trend.window_weeks} weeks "
        f"(server heuristic, not official CDC classification)."
    )


def _season_sentence(comparison: SeasonComparison) -> str:
    if comparison.current_value is None:
        return ""

    season = comparison.current_season
    wos = comparison.current_week_of_season

    if comparison.rank_vs_prior == 1:
        return (
            f"At week {wos} of the {season} season, this is the highest "
            f"level compared to the same week in prior seasons."
        )

    if comparison.pct_of_prior_peak is not None:
        pct = round(comparison.pct_of_prior_peak, 1)
        return (
            f"At week {wos} of the {season} season, the current level "
            f"is {pct}% of the highest prior-season value at this week."
        )

    return (
        f"At week {wos} of the {season} season "
        f"(ranked {comparison.rank_vs_prior} vs. prior seasons)."
    )


def _concordance_sentence(concordance: ConcordanceResult) -> str:
    lag_qualifier = ""
    if concordance.temporal_alignment_note:
        lag_qualifier = " (note: signals have differing reporting lags)"

    _early_warning_text = (
        "An early-warning signal is present: at least one indicator "
        "is rising while others remain stable"
    )
    pattern_text = {
        "concordant_increase": "Multiple signals agree on an increasing trend",
        "concordant_decrease": "Multiple signals agree on a decreasing trend",
        "early_warning": _early_warning_text,
        "stable": "Multiple signals agree that activity is stable",
        "mixed": "Signals show mixed trends",
        "insufficient_data": (
            "Concordance cannot be assessed due to insufficient data"
        ),
    }.get(concordance.pattern, "Concordance pattern is unclear")

    return f"{pattern_text}{lag_qualifier}."


# ── Label helpers ─────────────────────────────────────────────────────────────


def _pathogen_label(pathogen: Pathogen) -> str:
    return {
        Pathogen.influenza: "Influenza",
        Pathogen.covid19: "COVID-19",
        Pathogen.rsv: "RSV",
    }[pathogen]


def _signal_label(signal: Signal) -> str:
    return {
        Signal.hospital_admissions: "hospital admissions",
        Signal.wastewater: "wastewater activity",
        Signal.test_positivity: "test positivity",
    }[signal]


def _unit_label(unit: str) -> str:
    return {
        "admissions_per_100k": "admissions per 100k",
        "admissions_count": "total admissions",
        "percent_positive": "% positive",
        "wval": "WVAL",
    }.get(unit, unit)
