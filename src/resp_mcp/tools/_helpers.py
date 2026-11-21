"""Shared helpers used across all tool modules.

Keeps each tool file under ~60 lines. No I/O here — only orchestration helpers
that compose sources/, analytics/, and models/.
"""

from __future__ import annotations

import logging
from datetime import date

from resp_mcp.analytics.seasons import SeasonComparison
from resp_mcp.analytics.trend import TrendResult
from resp_mcp.models.common import (
    Pathogen,
    Provenance,
    Signal,
)
from resp_mcp.models.tool_io import (
    SeasonPoint,
    SeasonSummary,
    TrendSummary,
)

logger = logging.getLogger(__name__)

# ── Pathogen / signal alias resolution ───────────────────────────────────────

_PATHOGEN_ALIASES: dict[str, Pathogen] = {
    "flu": Pathogen.influenza,
    "influenza": Pathogen.influenza,
    "covid": Pathogen.covid19,
    "covid19": Pathogen.covid19,
    "covid-19": Pathogen.covid19,
    "sars-cov-2": Pathogen.covid19,
    "sars_cov_2": Pathogen.covid19,
    "rsv": Pathogen.rsv,
}


def resolve_pathogen(text: str) -> Pathogen:
    """Resolve a pathogen string (with alias support) to a Pathogen enum value."""
    normalised = text.strip().lower().replace(" ", "").replace("-", "")
    # Try direct enum lookup first
    try:
        return Pathogen(normalised)
    except ValueError:
        pass
    # Try alias map
    alias_key = text.strip().lower()
    if alias_key in _PATHOGEN_ALIASES:
        return _PATHOGEN_ALIASES[alias_key]
    normalised_key = normalised
    if normalised_key in _PATHOGEN_ALIASES:
        return _PATHOGEN_ALIASES[normalised_key]
    allowed = ", ".join(p.value for p in Pathogen)
    raise ValueError(f"Unknown pathogen {text!r}. Allowed: {allowed}")


_SIGNAL_ALIASES: dict[str, Signal] = {
    "hospital_admissions": Signal.hospital_admissions,
    "hospitaladmissions": Signal.hospital_admissions,
    "nhsn": Signal.hospital_admissions,
    "wastewater": Signal.wastewater,
    "ww": Signal.wastewater,
    "nwss": Signal.wastewater,
    "test_positivity": Signal.test_positivity,
    "testpositivity": Signal.test_positivity,
    "positivity": Signal.test_positivity,
    "nrevss": Signal.test_positivity,
}


def resolve_signal(text: str) -> Signal:
    """Resolve a signal string (with alias support) to a Signal enum value."""
    normalised = text.strip().lower()
    try:
        return Signal(normalised)
    except ValueError:
        pass
    if normalised in _SIGNAL_ALIASES:
        return _SIGNAL_ALIASES[normalised]
    allowed = ", ".join(s.value for s in Signal)
    raise ValueError(f"Unknown signal {text!r}. Allowed: {allowed}")


# ── as_of parsing ─────────────────────────────────────────────────────────────


def parse_as_of(as_of: str | None) -> date | None:
    """Parse the as_of string to a date, or return None."""
    if as_of is None:
        return None
    try:
        return date.fromisoformat(as_of)
    except ValueError as exc:
        raise ValueError(
            f"Invalid as_of date {as_of!r}. Expected YYYY-MM-DD."
        ) from exc


# ── TrendSummary conversion ────────────────────────────────────────────────────


def trend_to_summary(trend: TrendResult) -> TrendSummary:
    """Convert an analytics TrendResult dataclass to a Pydantic TrendSummary."""
    return TrendSummary(
        direction=trend.direction.value,
        pct_change=trend.pct_change,
        abs_change=trend.abs_change,
        window_weeks=trend.window_weeks,
        method=trend.method,
        basis=trend.basis,
    )


# ── SeasonComparison conversion ───────────────────────────────────────────────


def season_to_summary(cmp: SeasonComparison) -> SeasonSummary:
    """Convert an analytics SeasonComparison to a Pydantic SeasonSummary."""
    return SeasonSummary(
        current_season=cmp.current_season,
        current_week_of_season=cmp.current_week_of_season,
        current_value=cmp.current_value,
        prior=[
            SeasonPoint(
                season=p.season,
                week_ending=p.week_ending,
                week_of_season=p.week_of_season,
                value=p.value,
                alignment_note=p.alignment_note,
            )
            for p in cmp.prior
        ],
        rank_vs_prior=cmp.rank_vs_prior,
        pct_of_prior_peak=cmp.pct_of_prior_peak,
        method=cmp.method,
        notes=cmp.notes,
    )


# ── Date window calculation ───────────────────────────────────────────────────


def date_window(lookback_weeks: int, as_of: date | None) -> tuple[date, date]:
    """Return (start, end) dates for a lookback window ending on as_of."""

    end = as_of or date.today()
    start = date.fromordinal(end.toordinal() - lookback_weeks * 7 + 1)
    return start, end


# ── Collect all caveats from provenance objects ───────────────────────────────


def collect_caveats(provenance_list: list[Provenance]) -> list[str]:
    """Deduplicate and return all provenance notes as caveats."""
    seen: set[str] = set()
    out: list[str] = []
    for prov in provenance_list:
        for note in prov.notes:
            if note not in seen:
                seen.add(note)
                out.append(note)
    return out
