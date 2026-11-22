"""Unit tests for analytics/trend.py — pure functions, no I/O."""

from __future__ import annotations

from datetime import date

import pytest

from resp_mcp.analytics.trend import TrendDirection, classify_trend
from resp_mcp.models.common import Signal, WeeklyObservation

# Short aliases for readability in long test signatures
_HOSP = Signal.hospital_admissions
_POS = Signal.test_positivity
_WVAL = Signal.wastewater

# ── Helpers ───────────────────────────────────────────────────────────────────


def _obs_dates(
    values: list[float | None],
    unit: str = "admissions_per_100k",
) -> list[WeeklyObservation]:
    """Build observations with guaranteed distinct Saturday dates."""
    base = date(2026, 1, 3)  # a Saturday
    return [
        WeeklyObservation(
            jurisdiction="GA",
            week_ending=date.fromordinal(base.toordinal() + i * 7),
            value=v,
            unit=unit,
        )
        for i, v in enumerate(values)
    ]


# ── Insufficient data ─────────────────────────────────────────────────────────


def test_fewer_than_4_weeks_is_insufficient():
    result = classify_trend(_obs_dates([1.0, 2.0, 3.0]), _HOSP)
    assert result.direction == TrendDirection.insufficient_data
    assert result.pct_change is None


def test_exactly_4_weeks_is_sufficient():
    result = classify_trend(_obs_dates([1.0, 1.0, 1.0, 1.0]), _HOSP)
    assert result.direction != TrendDirection.insufficient_data


def test_all_nones_is_insufficient():
    result = classify_trend(_obs_dates([None, None, None, None, None]), _HOSP)
    assert result.direction == TrendDirection.insufficient_data


def test_trailing_nones_stripped_to_insufficient():
    # 2 real values + 2 trailing Nones → after stripping only 2 usable
    result = classify_trend(_obs_dates([1.0, 2.0, None, None]), _HOSP)
    assert result.direction == TrendDirection.insufficient_data


def test_missing_latest_values_are_not_backdated():
    result = classify_trend(_obs_dates([1.0, 1.0, 2.0, 2.0, None, None]), _HOSP)
    assert result.direction == TrendDirection.insufficient_data


# ── Hospital admissions ───────────────────────────────────────────────────────


def test_hospital_clear_increase():
    # prior mean = 1.0, recent mean = 2.0 → +100% ≥10% and +1.0 ≥0.1
    result = classify_trend(_obs_dates([1.0, 1.0, 2.0, 2.0]), _HOSP)
    assert result.direction == TrendDirection.increasing
    assert result.abs_change == pytest.approx(1.0)
    assert result.pct_change == pytest.approx(1.0)


def test_hospital_clear_decrease():
    result = classify_trend(_obs_dates([2.0, 2.0, 1.0, 1.0]), _HOSP)
    assert result.direction == TrendDirection.decreasing
    assert result.abs_change == pytest.approx(-1.0)


def test_hospital_stable_small_relative_change():
    # +5% relative, below 10% threshold → stable
    result = classify_trend(_obs_dates([2.0, 2.0, 2.1, 2.1]), _HOSP)
    assert result.direction == TrendDirection.stable


def test_hospital_stable_large_relative_but_small_absolute():
    # +50% relative but abs = 0.05 (below 0.1 threshold) → stable
    result = classify_trend(_obs_dates([0.1, 0.1, 0.15, 0.15]), _HOSP)
    assert result.direction == TrendDirection.stable


def test_hospital_stable_large_absolute_but_small_relative():
    # abs = 5.0, relative = 1.5% (below 10%) → stable
    result = classify_trend(_obs_dates([333.0, 333.0, 338.0, 338.0]), _HOSP)
    assert result.direction == TrendDirection.stable


# ── Test positivity ───────────────────────────────────────────────────────────


def test_positivity_increase_above_threshold():
    # +2 pp ≥ 1.0 → increasing
    obs = _obs_dates([5.0, 5.0, 7.0, 7.0], "percent_positive")
    result = classify_trend(obs, _POS)
    assert result.direction == TrendDirection.increasing
    assert result.abs_change == pytest.approx(2.0)


def test_positivity_decrease_above_threshold():
    obs = _obs_dates([7.0, 7.0, 5.0, 5.0], "percent_positive")
    result = classify_trend(obs, _POS)
    assert result.direction == TrendDirection.decreasing


def test_positivity_stable_below_threshold():
    # +0.5 pp < 1.0 → stable
    obs = _obs_dates([5.0, 5.0, 5.5, 5.5], "percent_positive")
    result = classify_trend(obs, _POS)
    assert result.direction == TrendDirection.stable


def test_positivity_at_threshold_is_changing():
    # exactly ±1.0 pp
    obs = _obs_dates([5.0, 5.0, 6.0, 6.0], "percent_positive")
    result = classify_trend(obs, _POS)
    assert result.direction == TrendDirection.increasing


# ── Wastewater ────────────────────────────────────────────────────────────────


def test_wval_increase_above_threshold():
    # +20% ≥ 15% → increasing
    result = classify_trend(_obs_dates([1.0, 1.0, 1.2, 1.2], "wval"), _WVAL)
    assert result.direction == TrendDirection.increasing


def test_wval_decrease_above_threshold():
    result = classify_trend(_obs_dates([1.2, 1.2, 1.0, 1.0], "wval"), _WVAL)
    assert result.direction == TrendDirection.decreasing


def test_wval_stable_below_threshold():
    # +10% < 15% → stable
    result = classify_trend(_obs_dates([1.0, 1.0, 1.1, 1.1], "wval"), _WVAL)
    assert result.direction == TrendDirection.stable


def test_wval_at_threshold_is_changing():
    # +16% (above 15% threshold, avoiding float rounding at exact boundary)
    result = classify_trend(_obs_dates([1.0, 1.0, 1.16, 1.16], "wval"), _WVAL)
    assert result.direction == TrendDirection.increasing


# ── Small-number guard ────────────────────────────────────────────────────────


def test_small_number_guard_triggers_insufficient():
    # values look like +100%, but counts < 10 → insufficient_data
    obs = _obs_dates([1.0, 1.0, 2.0, 2.0])
    counts: list[float | None] = [3.0, 3.0, 5.0, 5.0]  # mean = 4.0 < 10
    result = classify_trend(obs, _HOSP, counts=counts)
    assert result.direction == TrendDirection.insufficient_data


def test_small_number_guard_bypassed_when_counts_sufficient():
    obs = _obs_dates([1.0, 1.0, 2.0, 2.0])
    counts: list[float | None] = [50.0, 50.0, 80.0, 80.0]  # mean > 10
    result = classify_trend(obs, _HOSP, counts=counts)
    assert result.direction == TrendDirection.increasing


def test_small_number_guard_not_applied_to_positivity():
    # Counts provided for a positivity signal — guard should not trigger
    obs = _obs_dates([5.0, 5.0, 7.0, 7.0], "percent_positive")
    counts: list[float | None] = [3.0, 3.0, 5.0, 5.0]  # would trigger for NHSN
    result = classify_trend(obs, _POS, counts=counts)
    assert result.direction == TrendDirection.increasing  # guard not applied


# ── window_weeks ──────────────────────────────────────────────────────────────


def test_window_weeks_reflects_non_null_count():
    obs = _obs_dates([1.0, 1.0, 2.0, 2.0, 2.5, 2.5])  # 6 values
    result = classify_trend(obs, _WVAL)
    assert result.window_weeks == 4


def test_window_weeks_after_trailing_none_strip():
    obs = _obs_dates([1.0, 1.0, 2.0, 2.0, None])  # 4 real + 1 None
    result = classify_trend(obs, _WVAL)
    assert result.window_weeks == 4


# ── TrendResult metadata ──────────────────────────────────────────────────────


def test_result_method_is_documented():
    obs = _obs_dates([1.0, 1.0, 1.2, 1.2])
    result = classify_trend(obs, _WVAL)
    assert result.method == "2w_vs_prior_2w"


def test_result_basis_is_server_heuristic():
    obs = _obs_dates([1.0, 1.0, 1.2, 1.2])
    result = classify_trend(obs, _WVAL)
    assert result.basis == "server_heuristic"


def test_zero_denominator_does_not_imply_stable_wastewater():
    result = classify_trend(_obs_dates([0.0, 0.0, 0.5, 0.5], "wval"), _WVAL)
    assert result.pct_change is None
    assert result.direction == TrendDirection.insufficient_data
