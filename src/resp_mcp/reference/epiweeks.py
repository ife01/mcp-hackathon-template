"""MMWR epiweek helpers for the Respiratory MCP server.

All calculations delegate to the `epiweeks` library (CDC-compliant MMWR weeks).

Season definition (from build plan §1.3):
  MMWR week 27 of year Y through MMWR week 26 of year Y+1.
  Example: 2024-25 season = week 27/2024 → week 26/2025.

Week-ending convention: MMWR weeks end on Saturday.
"""

from __future__ import annotations

from datetime import date, timedelta

from epiweeks import Week


def mmwr_week(d: date) -> tuple[int, int]:
    """Return the (year, week) MMWR tuple for a given date.

    Args:
        d: Any calendar date.

    Returns:
        Tuple of (mmwr_year, mmwr_week_number) where week is 1-53.
    """
    w = Week.fromdate(d, system="CDC")
    return w.year, w.week


def week_ending(year: int, week: int) -> date:
    """Return the Saturday (week-ending date) for a given MMWR week.

    Args:
        year: MMWR year.
        week: MMWR week number (1-53).

    Returns:
        date of the Saturday ending that MMWR week.
    """
    w = Week(year, week, system="CDC")
    # MMWR week ends on Saturday; epiweeks .enddate() returns the last day
    return w.enddate()


def season_of(d: date) -> str:
    """Return the respiratory season label for a date.

    Season runs from MMWR week 27 (year Y) through MMWR week 26 (year Y+1).

    Args:
        d: Any calendar date.

    Returns:
        Season string in the form "YYYY-YY" (e.g. "2024-25").
    """
    yr, wk = mmwr_week(d)
    if wk >= 27:
        return f"{yr}-{str(yr + 1)[-2:]}"
    else:
        return f"{yr - 1}-{str(yr)[-2:]}"


def week_of_season(d: date) -> int:
    """Return the week-within-season index for a date (1-based, week 27 = 1).

    Args:
        d: Any calendar date.

    Returns:
        Integer ≥ 1. Week 27 of the season start year = 1, week 26 of end year
        = 52 (or 53 in a 53-week year).
    """
    yr, wk = mmwr_week(d)
    if wk >= 27:
        return wk - 26  # week 27 → 1, week 52 → 26, week 53 → 27
    else:
        # Need the number of weeks in the prior MMWR year to handle 53-week years
        prior_year_weeks = _weeks_in_mmwr_year(yr - 1)
        return (prior_year_weeks - 26) + wk  # e.g. 52-week year: week 26 → 26


def same_week_prior_seasons(d: date, n: int) -> list[date]:
    """Return the equivalent week-ending dates in n prior seasons.

    Aligns by week_of_season. Handles 53-week years by clamping to the last
    available week of the prior season if the equivalent week doesn't exist.

    Args:
        d: Reference date in the current season.
        n: Number of prior seasons to look back.

    Returns:
        List of up to n week-ending dates (may be shorter if data predates
        the first available season).
    """
    target_wos = week_of_season(d)
    yr, wk = mmwr_week(d)
    # Determine the season start year for d
    if wk >= 27:
        season_start_year = yr
    else:
        season_start_year = yr - 1

    results: list[date] = []
    for i in range(1, n + 1):
        prior_start = season_start_year - i
        first = week_ending(prior_start, 27)
        last = week_ending(prior_start + 1, 26)
        length = (last - first).days // 7 + 1
        results.append(first + timedelta(weeks=min(target_wos, length) - 1))

    return results


def _weeks_in_mmwr_year(year: int) -> int:
    """Return the number of MMWR weeks in a given year (52 or 53).

    Uses the Week(year, 53) probe: if week 53 exists in the given MMWR year
    without raising, the year has 53 weeks; otherwise 52.
    """
    try:
        Week(year, 53, system="CDC")
        return 53
    except Exception:
        return 52
