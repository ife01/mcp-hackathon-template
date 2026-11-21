"""Shared helpers used across all tool modules.

Keeps each tool file under ~60 lines. No I/O here — only orchestration helpers
that compose sources/, analytics/, and models/.
"""

from __future__ import annotations

import logging
from datetime import date

from resp_mcp.analytics.seasons import SeasonComparison
from resp_mcp.analytics.trend import TrendResult
from resp_mcp.clients.socrata import UpstreamRateLimited, UpstreamUnavailable
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

# ── Structured error response ─────────────────────────────────────────────────

_AS_OF_MIN = date(2020, 1, 1)
_AS_OF_MAX_FUTURE_DAYS = 7  # allow at most 1 week into the future


def structured_error(code: str, message: str, **extras) -> dict:
    """Return a structured error dict (instead of raising) for tool outputs."""
    return {"error": code, "message": message, **extras}


def classify_tool_error(exc: Exception) -> dict:
    """Map a caught exception to a structured error dict."""
    from resp_mcp.reference.jurisdictions import (
        UnknownJurisdiction,  # local to avoid circular
    )

    if isinstance(exc, UnknownJurisdiction):
        return structured_error(
            "unknown_jurisdiction",
            str(exc),
            suggestions=exc.suggestions,
        )
    if isinstance(exc, ValueError):
        return structured_error("invalid_input", str(exc))
    if isinstance(exc, UpstreamRateLimited):
        return structured_error(
            "rate_limited",
            "CDC Socrata API rate limit reached. "
            "Retry in a few seconds or set SOCRATA_APP_TOKEN in .env.",
        )
    if isinstance(exc, UpstreamUnavailable):
        return structured_error(
            "upstream_unavailable",
            f"CDC data source temporarily unavailable: {exc}. "
            "Please retry shortly.",
        )
    # Unexpected — log and return generic
    logger.exception("Unexpected tool error: %s", exc)
    return structured_error("internal_error", f"Unexpected error: {exc}")

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
    """Parse the as_of string to a date, validate it is in an acceptable range."""
    if as_of is None:
        return None
    try:
        parsed = date.fromisoformat(as_of)
    except ValueError as exc:
        raise ValueError(
            f"Invalid as_of date {as_of!r}. Expected YYYY-MM-DD."
        ) from exc
    if parsed < _AS_OF_MIN:
        raise ValueError(
            f"as_of date {as_of!r} is before the earliest supported date "
            f"({_AS_OF_MIN.isoformat()}). "
            "CDC NHSN reporting began in 2020."
        )
    today = date.today()
    max_allowed = date.fromordinal(today.toordinal() + _AS_OF_MAX_FUTURE_DAYS)
    if parsed > max_allowed:
        raise ValueError(
            f"as_of date {as_of!r} is too far in the future "
            f"(max: {max_allowed.isoformat()}). "
            "Use today's date or omit as_of to get the latest data."
        )
    return parsed


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
