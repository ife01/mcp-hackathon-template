"""Unit tests for analytics/seasons.py — pure functions, no I/O."""

from __future__ import annotations

from datetime import date

import pytest

from resp_mcp.analytics.seasons import (
    SeasonComparison,
    compare_to_prior_seasons,
)
from resp_mcp.models.common import WeeklyObservation
from resp_mcp.reference.epiweeks import week_ending, week_of_season

# ── Helpers ───────────────────────────────────────────────────────────────────


def _make_obs(
    date_value_pairs: list[tuple[date, float | None]],
) -> list[WeeklyObservation]:
    """Build WeeklyObservations from (date, value) pairs."""
    return [
        WeeklyObservation(
            jurisdiction="GA",
            week_ending=d,
            value=v,
            unit="admissions_per_100k",
        )
        for d, v in date_value_pairs
    ]


def _obs_at_equivalent_weeks(
    reference_date: date,
    n_seasons: int,
    base_value: float = 1.0,
) -> list[WeeklyObservation]:
    """Build observations at reference date AND equivalent dates in n prior seasons."""
    from resp_mcp.reference.epiweeks import same_week_prior_seasons
    prior_dates = same_week_prior_seasons(reference_date, n_seasons)
    pairs = [(reference_date, base_value)]
    for i, pd in enumerate(prior_dates):
        pairs.append((pd, base_value + i + 1))  # prior seasons have higher values
    return _make_obs(pairs)


# ── Basic functionality ────────────────────────────────────────────────────────


def test_returns_season_comparison():
    ref = date(2026, 11, 14)  # MMWR week 45/2026, season 2026-27 (wos=19)
    obs = _obs_at_equivalent_weeks(ref, 3)
    result = compare_to_prior_seasons(obs, ref, n_seasons=3)
    assert isinstance(result, SeasonComparison)
    assert result.current_season == "2026-27"
    assert result.method == "week_of_season_aligned"


def test_current_value_returned():
    ref = date(2026, 11, 14)
    obs = _make_obs([(ref, 2.5)])
    result = compare_to_prior_seasons(obs, ref, n_seasons=0)
    assert result.current_value == pytest.approx(2.5)


def test_prior_seasons_count():
    ref = date(2026, 11, 14)
    obs = _obs_at_equivalent_weeks(ref, 3)
    result = compare_to_prior_seasons(obs, ref, n_seasons=3)
    assert len(result.prior) == 3


def test_prior_season_labels():
    ref = date(2026, 11, 14)
    obs = _obs_at_equivalent_weeks(ref, 3)
    result = compare_to_prior_seasons(obs, ref, n_seasons=3)
    seasons = {p.season for p in result.prior}
    assert "2025-26" in seasons
    assert "2024-25" in seasons
    assert "2023-24" in seasons


def test_prior_week_of_season_matches_current():
    """Each prior data point should have the same week_of_season as current."""
    ref = date(2026, 11, 14)
    obs = _obs_at_equivalent_weeks(ref, 3)
    result = compare_to_prior_seasons(obs, ref, n_seasons=3)
    target_wos = week_of_season(ref)
    for p in result.prior:
        assert p.week_of_season == target_wos


# ── Ranking ───────────────────────────────────────────────────────────────────


def test_current_above_all_priors_ranks_1():
    ref = date(2026, 11, 14)
    from resp_mcp.reference.epiweeks import same_week_prior_seasons
    prior_dates = same_week_prior_seasons(ref, 3)
    pairs = [(ref, 10.0)]  # current = 10, highest
    for i, pd in enumerate(prior_dates):
        pairs.append((pd, float(i + 1)))  # prior = 1,2,3
    obs = _make_obs(pairs)
    result = compare_to_prior_seasons(obs, ref, n_seasons=3)
    assert result.rank_vs_prior == 1


def test_current_below_all_priors_ranks_last():
    ref = date(2026, 11, 14)
    from resp_mcp.reference.epiweeks import same_week_prior_seasons
    prior_dates = same_week_prior_seasons(ref, 3)
    pairs = [(ref, 0.1)]  # current = 0.1, lowest
    for i, pd in enumerate(prior_dates):
        pairs.append((pd, float(i + 5)))  # prior = 5,6,7
    obs = _make_obs(pairs)
    result = compare_to_prior_seasons(obs, ref, n_seasons=3)
    assert result.rank_vs_prior == 4  # 1 + 3 prior values above


def test_rank_none_when_current_value_missing():
    ref = date(2026, 11, 14)
    obs = _make_obs([])  # no observations
    result = compare_to_prior_seasons(obs, ref, n_seasons=1)
    assert result.rank_vs_prior is None


# ── pct_of_prior_peak ─────────────────────────────────────────────────────────


def test_pct_of_prior_peak_calculated():
    ref = date(2026, 11, 14)
    from resp_mcp.reference.epiweeks import same_week_prior_seasons
    prior_dates = same_week_prior_seasons(ref, 2)
    # current=5.0, prior=[10.0, 8.0] → peak=10.0 → 50%
    pairs = [(ref, 5.0), (prior_dates[0], 10.0), (prior_dates[1], 8.0)]
    obs = _make_obs(pairs)
    result = compare_to_prior_seasons(obs, ref, n_seasons=2)
    assert result.pct_of_prior_peak == pytest.approx(50.0)


def test_pct_of_prior_peak_none_when_no_prior_data():
    ref = date(2026, 11, 14)
    obs = _make_obs([(ref, 5.0)])
    result = compare_to_prior_seasons(obs, ref, n_seasons=2)
    # No prior observations in obs → no prior_values → None
    assert result.pct_of_prior_peak is None


# ── Missing prior week (±1 week fallback) ─────────────────────────────────────


def test_missing_prior_week_uses_plus_one_fallback():
    ref = date(2026, 11, 14)
    from resp_mcp.reference.epiweeks import same_week_prior_seasons
    prior_dates = same_week_prior_seasons(ref, 1)
    exact_date = prior_dates[0]
    # Provide value one week later instead of on exact date
    fallback_date = date.fromordinal(exact_date.toordinal() + 7)
    obs = _make_obs([(ref, 2.0), (fallback_date, 3.0)])
    result = compare_to_prior_seasons(obs, ref, n_seasons=1)
    assert len(result.prior) == 1
    assert result.prior[0].value == pytest.approx(3.0)
    assert result.prior[0].alignment_note is not None
    assert "fallback" in result.prior[0].alignment_note.lower()


def test_missing_prior_week_uses_minus_one_fallback():
    ref = date(2026, 11, 14)
    from resp_mcp.reference.epiweeks import same_week_prior_seasons
    prior_dates = same_week_prior_seasons(ref, 1)
    exact_date = prior_dates[0]
    # Provide value one week earlier
    fallback_date = date.fromordinal(exact_date.toordinal() - 7)
    obs = _make_obs([(ref, 2.0), (fallback_date, 3.5)])
    result = compare_to_prior_seasons(obs, ref, n_seasons=1)
    assert result.prior[0].value == pytest.approx(3.5)
    assert result.prior[0].alignment_note is not None


def test_prior_point_value_none_when_no_data_at_all():
    ref = date(2026, 11, 14)
    obs = _make_obs([(ref, 2.0)])  # no prior data at all
    result = compare_to_prior_seasons(obs, ref, n_seasons=1)
    assert result.prior[0].value is None
    assert result.prior[0].alignment_note is None


# ── 53-week year alignment ────────────────────────────────────────────────────


def test_53_week_year_alignment():
    """2025-26 starts with MMWR week 27 of 2025 (a 53-week year).
    Reference date in week 27 of 2025 should align back to week 27 of 2024.
    """
    # week 27, 2025 starts the 2025-26 season
    ref = week_ending(2025, 27)  # wos = 1
    from resp_mcp.reference.epiweeks import same_week_prior_seasons
    prior_dates = same_week_prior_seasons(ref, 1)
    # Should land on week 27 of 2024 (start of 2024-25 season)
    expected = week_ending(2024, 27)
    assert prior_dates[0] == expected


def test_season_comparison_handles_53_week_year():
    """Build observations for a 53-week year scenario and verify no crash."""
    ref = week_ending(2025, 27)
    from resp_mcp.reference.epiweeks import same_week_prior_seasons
    prior_dates = same_week_prior_seasons(ref, 2)
    pairs = [(ref, 1.0)] + [(pd, float(i + 2)) for i, pd in enumerate(prior_dates)]
    obs = _make_obs(pairs)
    result = compare_to_prior_seasons(obs, ref, n_seasons=2)
    assert len(result.prior) == 2
    assert result.rank_vs_prior is not None


# ── NHSN pre-transition exclusion ─────────────────────────────────────────────


def test_pre_transition_seasons_excluded_when_flag_set():
    ref = date(2026, 11, 14)
    obs = _obs_at_equivalent_weeks(ref, 3)
    # Seasons 2023-24 and earlier should be excluded
    result = compare_to_prior_seasons(
        obs, ref, n_seasons=3, exclude_pre_transition_nhsn=True
    )
    seasons = {p.season for p in result.prior}
    assert "2023-24" not in seasons
    assert "2025-26" in seasons
    assert "2024-25" in seasons
    assert any("excluded" in n.lower() or "2024" in n for n in result.notes)


def test_pre_transition_flag_false_includes_all_seasons():
    ref = date(2026, 11, 14)
    obs = _obs_at_equivalent_weeks(ref, 3)
    result = compare_to_prior_seasons(
        obs, ref, n_seasons=3, exclude_pre_transition_nhsn=False
    )
    assert len(result.prior) == 3


# ── Mid-history source start ───────────────────────────────────────────────────


def test_mid_history_no_data_for_one_prior_season():
    """If a prior season has no data (new source), value=None, no crash."""
    ref = date(2026, 11, 14)
    from resp_mcp.reference.epiweeks import same_week_prior_seasons
    prior_dates = same_week_prior_seasons(ref, 3)
    # Only provide current and 2 of 3 prior seasons
    pairs = [(ref, 5.0), (prior_dates[0], 4.0), (prior_dates[1], 6.0)]
    # prior_dates[2] has no data
    obs = _make_obs(pairs)
    result = compare_to_prior_seasons(obs, ref, n_seasons=3)
    assert len(result.prior) == 3
    # Third prior should have value None (and no fallback found)
    no_data = [p for p in result.prior if p.value is None]
    assert len(no_data) >= 1


# ── current_week_of_season ────────────────────────────────────────────────────


def test_current_week_of_season_correct():
    # Week 45 of 2026 → wos = 45 - 26 = 19
    ref = date(2026, 11, 14)
    obs = _make_obs([(ref, 1.0)])
    result = compare_to_prior_seasons(obs, ref, n_seasons=0)
    assert result.current_week_of_season == week_of_season(ref)
