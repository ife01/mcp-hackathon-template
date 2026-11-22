"""Unit tests for resp_mcp.reference.epiweeks."""

from __future__ import annotations

from datetime import date

from resp_mcp.reference.epiweeks import (
    _weeks_in_mmwr_year,
    mmwr_week,
    same_week_prior_seasons,
    season_of,
    week_ending,
    week_of_season,
)

# ── mmwr_week ─────────────────────────────────────────────────────────────────


def test_mmwr_week_known_date():
    # 2026-11-14 is MMWR week 45 of 2026 (confirmed from epiweeks library)
    yr, wk = mmwr_week(date(2026, 11, 14))
    assert yr == 2026
    assert wk == 45


def test_mmwr_week_start_of_year():
    # Jan 1, 2024 is in MMWR week 1 of 2024
    yr, wk = mmwr_week(date(2024, 1, 1))
    assert yr == 2024
    assert wk == 1


# ── week_ending ───────────────────────────────────────────────────────────────


def test_week_ending_is_saturday():
    d = week_ending(2026, 46)
    assert d.weekday() == 5  # Saturday = 5


def test_week_ending_known_value():
    # MMWR week 45 of 2026 ends 2026-11-14 (confirmed from epiweeks library)
    assert week_ending(2026, 45) == date(2026, 11, 14)


# ── season_of ─────────────────────────────────────────────────────────────────


def test_season_of_in_first_half():
    # Week 46 of 2026 is in the 2026-27 season (after week 27)
    assert season_of(date(2026, 11, 14)) == "2026-27"


def test_season_of_before_week_27():
    # Week 10 of 2026 is in the 2025-26 season (before week 27)
    assert season_of(date(2026, 3, 7)) == "2025-26"


def test_season_of_exactly_week_27():
    # Week 27 is the first week of the new season
    d = week_ending(2026, 27)
    assert season_of(d) == "2026-27"


def test_season_of_exactly_week_26():
    # Week 26 is the last week of the outgoing season
    d = week_ending(2026, 26)
    assert season_of(d) == "2025-26"


# ── week_of_season ────────────────────────────────────────────────────────────


def test_week_of_season_week_27_is_1():
    d = week_ending(2026, 27)
    assert week_of_season(d) == 1


def test_week_of_season_week_28_is_2():
    d = week_ending(2026, 28)
    assert week_of_season(d) == 2


def test_week_of_season_week_26_in_next_year():
    # Week 26 of 2027 is the last week of the 2026-27 season
    d = week_ending(2027, 26)
    wos = week_of_season(d)
    # In a 52-week year, that's week 52; in 53-week year, week 53
    assert wos in (52, 53)


def test_week_of_season_week_1_in_new_year():
    # Week 1 of 2027 is early in the 2026-27 season
    d = week_ending(2027, 1)
    wos = week_of_season(d)
    assert wos > 26  # it's well past week 27 start


# ── 53-week year boundaries ───────────────────────────────────────────────────


def test_weeks_in_52_week_year():
    # 2026 is a 52-week MMWR year
    assert _weeks_in_mmwr_year(2026) == 52


def test_weeks_in_53_week_year():
    # 2020 and 2025 are known 53-week MMWR years
    assert _weeks_in_mmwr_year(2020) == 53
    assert _weeks_in_mmwr_year(2025) == 53


def test_weeks_in_another_52_week_year():
    # 2021 is a 52-week MMWR year
    assert _weeks_in_mmwr_year(2021) == 52


# ── same_week_prior_seasons ───────────────────────────────────────────────────


def test_same_week_prior_seasons_returns_n_dates():
    d = week_ending(2026, 45)
    priors = same_week_prior_seasons(d, 3)
    assert len(priors) == 3


def test_same_week_prior_seasons_all_saturdays():
    d = week_ending(2026, 45)
    priors = same_week_prior_seasons(d, 3)
    for prior in priors:
        assert prior.weekday() == 5, f"{prior} is not a Saturday"


def test_same_week_prior_seasons_one_year_apart():
    d = week_ending(2026, 45)
    priors = same_week_prior_seasons(d, 2)
    # Each prior should be ~52 weeks apart
    diff = abs((d - priors[0]).days)
    assert 350 <= diff <= 380  # 52-53 weeks ≈ 364-371 days, allow margin


def test_same_week_prior_seasons_week_27_rollover():
    # Week 27 is the season boundary — test that it aligns correctly
    d = week_ending(2026, 27)  # wos=1
    priors = same_week_prior_seasons(d, 2)
    # Both priors should also be at wos=1 (week 27)
    for prior in priors:
        _, wk = mmwr_week(prior)
        assert wk == 27


def test_same_week_prior_seasons_53_week_year_handling():
    # Week 45 of 2026 going back to 2020 (a 53-week year)
    d = week_ending(2026, 45)
    priors = same_week_prior_seasons(d, 7)  # goes back through 2020
    assert len(priors) == 7
    for prior in priors:
        assert prior.weekday() == 5  # all Saturdays


def test_week_26_27_season_boundary():
    # Week 26 of 2026 is 2025-26 season
    assert season_of(week_ending(2026, 26)) == "2025-26"
    # Week 27 of 2026 is 2026-27 season
    assert season_of(week_ending(2026, 27)) == "2026-27"
