"""Tool I/O models for all four MCP tools.

Defines Pydantic-validated input and output contracts. All inputs have
explicit length/character bounds. All outputs include provenance, caveats,
and summary directly (self-contained for wxO agents that may not read Resources).

Tools:
  1. get_respiratory_snapshot  → SnapshotInput / SnapshotOutput
  2. assess_trend              → TrendInput / TrendOutput
  3. compare_to_prior_seasons  → SeasonInput / SeasonOutput
  4. find_jurisdictions_with_rising_activity  → ScanInput / ScanOutput

wxO Schema Compatibility notes:
  - All string fields use Field(description=...) without large examples arrays.
  - Enum fields serialise as plain strings via str(Enum) inheritance.
  - No complex nested Literal/Enum unions in input schemas.
  - as_of is an optional ISO date string (not a date object) so wxO agents can
    supply "2026-10-31" without confusion.
"""

from __future__ import annotations

from datetime import date
from typing import Annotated, Literal

from pydantic import BaseModel, Field, computed_field

from resp_mcp.models.common import Pathogen, Provenance, Signal, WeeklyObservation

TREND_ATTRIBUTION = (
    "Trend direction is calculated by this application's heuristic from CDC "
    "surveillance data. It is not a CDC trend classification or a CDC-developed "
    "heuristic. Only official_level carries a source-published NHSN level."
)

# ── Shared input constraints ──────────────────────────────────────────────────

_JURISDICTION_FIELD = Field(
    description=(
        "US state code (e.g. 'GA'), territory (e.g. 'PR'), or 'USA'/'national'. "
        "Case-insensitive; common aliases accepted."
    ),
    min_length=1,
    max_length=64,
)

_PATHOGEN_FIELD = Field(
    description=(
        "Respiratory pathogen: 'influenza', 'covid19', or 'rsv'. "
        "Aliases: 'flu' → influenza, 'covid'/'sars-cov-2' → covid19."
    ),
)

_SIGNAL_FIELD = Field(
    description=(
        "Surveillance signal: 'hospital_admissions' (NHSN), "
        "'wastewater' (NWSS), or 'test_positivity' (NREVSS)."
    ),
)

_AS_OF_FIELD = Field(
    default=None,
    description=(
        "ISO date string (YYYY-MM-DD) to restrict analysis to data on or before "
        "this date. Omit to use the most recent available data. "
        "Applied to data retrieved now, not an as-published historical vintage. "
        "Use frozen snapshots for reproducible replay."
    ),
    pattern=r"^\d{4}-\d{2}-\d{2}$",
)

# These annotations are also used on registered tool functions: the client must
# see the same constraints and descriptions that runtime validation enforces.
JurisdictionArg = Annotated[str, _JURISDICTION_FIELD]
PathogenArg = Annotated[
    str, Field(description=_PATHOGEN_FIELD.description, max_length=32)
]
SignalArg = Annotated[str, Field(description=_SIGNAL_FIELD.description, max_length=32)]
AsOfArg = Annotated[
    str | None,
    Field(description=_AS_OF_FIELD.description, pattern=r"^\d{4}-\d{2}-\d{2}$"),
]
LookbackArg = Annotated[
    int,
    Field(
        ge=4,
        le=52,
        description="History to display; trend uses four consecutive weeks.",
    ),
]
PriorSeasonsArg = Annotated[
    int, Field(ge=1, le=5, description="Number of prior seasons requested (1–5).")
]
RegionArg = Annotated[
    int | None,
    Field(ge=1, le=10, description="HHS region, or omit for 50 states and DC."),
]
LimitArg = Annotated[
    int, Field(ge=1, le=56, description="Maximum results returned (1–56).")
]
LevelArg = Literal["Very Low", "Low", "Moderate", "High", "Very High"] | None
PathogensArg = Annotated[
    list[PathogenArg] | None,
    Field(
        min_length=1,
        max_length=3,
        description="Up to three unique pathogens; omit for all. Aliases flu and "
        "covid accepted.",
    ),
]


# ── Shared output components ───────────────────────────────────────────────────


class TrendSummary(BaseModel):
    """Serialisable version of TrendResult for tool outputs."""

    notes: list[str] = Field(default_factory=list)
    attribution: str = TREND_ATTRIBUTION
    direction: str = Field(
        description="increasing | stable | decreasing | insufficient_data"
    )
    pct_change: float | None = Field(
        default=None,
        description="Relative change as a decimal (0.15 = 15%). None when unavailable.",
    )
    abs_change: float | None = Field(
        default=None,
        description="Absolute change in the signal's native unit.",
    )
    window_weeks: int = Field(
        description="Number of recent observation slots inspected (at most four).",
    )
    method: str = Field(description="Method identifier (e.g. '2w_vs_prior_2w').")
    basis: str = Field(
        description=(
            "server_heuristic — NOT an official CDC classification. "
            "Use official_level in WeeklyObservation for authoritative CDC levels."
        ),
    )


class SeasonPoint(BaseModel):
    """One prior-season data point at the equivalent week."""

    season: str = Field(description="Season label, e.g. '2024-25'.")
    week_ending: date
    week_of_season: int
    value: float | None = None
    alignment_note: str | None = None


class SeasonSummary(BaseModel):
    """Serialisable version of SeasonComparison for tool outputs."""

    current_season: str
    current_week_of_season: int
    current_value: float | None = None
    prior: list[SeasonPoint] = Field(default_factory=list)
    rank_vs_prior: int | None = Field(
        default=None,
        description=(
            "Rank of current value vs. prior seasons at this week (1 = highest)."
        ),
    )
    pct_of_prior_peak: float | None = Field(
        default=None,
        description="Current / highest peak among complete eligible prior seasons * "
        "100; null without full seasons.",
    )
    n_prior_compared: int = 0
    prior_season_peaks: dict[str, float] = Field(default_factory=dict)
    method: str = "week_of_season_aligned"
    notes: list[str] = Field(default_factory=list)


# ── Tool 1: get_respiratory_snapshot ─────────────────────────────────────────


class SnapshotInput(BaseModel):
    """Input for get_respiratory_snapshot.

    Returns the latest week's levels across all three signals for the requested
    pathogens in a single jurisdiction.
    """

    jurisdiction: Annotated[str, _JURISDICTION_FIELD]
    pathogens: list[Pathogen] = Field(
        default_factory=lambda: list(Pathogen),
        min_length=1,
        max_length=3,
        description=(
            "List of pathogens to include. Defaults to all three "
            "('influenza', 'covid19', 'rsv')."
        ),
    )
    as_of: str | None = _AS_OF_FIELD


class SignalReading(BaseModel):
    """Latest reading for one signal within a snapshot."""

    signal: Signal
    status: Literal[
        "ok", "unavailable", "insufficient_coverage", "insufficient_data"
    ] = "ok"
    role: Literal["local", "national_context"] = "local"
    latest: WeeklyObservation | None = None
    trend: TrendSummary | None = None
    provenance: Provenance | None = None
    message: str | None = Field(
        default=None,
        description="Populated when status != ok (e.g. error or caveat text).",
    )


class PathogenSnapshot(BaseModel):
    """All three signal readings for one pathogen within a snapshot."""

    pathogen: Pathogen
    signals: list[SignalReading]
    concordance_pattern: str | None = Field(
        default=None,
        description=(
            "Cross-signal concordance pattern for this pathogen "
            "(concordant_increase | stable | early_warning | mixed | …)."
        ),
    )
    concordance_note: str | None = None


class SnapshotOutput(BaseModel):
    """Output for get_respiratory_snapshot.

    USE WHEN: You need a quick multi-pathogen, multi-signal status overview for
    one jurisdiction.
    """

    jurisdiction: str
    as_of_week_ending: date | None = Field(
        default=None,
        description="Latest week_ending date across all retrieved data.",
    )
    pathogens: list[PathogenSnapshot]
    summary: str = Field(description="1–3 sentence plain-English summary.")
    caveats: list[str] = Field(
        default_factory=list,
        description="Data caveats and limitations from all sources.",
    )


# ── Tool 2: assess_trend ─────────────────────────────────────────────────────


class TrendInput(BaseModel):
    """Input for assess_trend.

    Returns a time series and heuristic trend classification for one
    jurisdiction / pathogen / signal combination.
    """

    jurisdiction: Annotated[str, _JURISDICTION_FIELD]
    pathogen: Pathogen = _PATHOGEN_FIELD
    signal: Signal = _SIGNAL_FIELD
    lookback_weeks: int = Field(
        default=8,
        ge=4,
        le=52,
        description=(
            "Number of weeks of history to retrieve and display (4–52). "
            "Trend uses the most recent 4 of these weeks."
        ),
    )
    as_of: str | None = _AS_OF_FIELD


class TrendOutput(BaseModel):
    """Output for assess_trend.

    USE WHEN: You need to characterise whether a signal is rising, stable, or
    falling over recent weeks. Includes the weekly series so an agent can cite
    specific values.
    """

    jurisdiction: str
    pathogen: Pathogen
    signal: Signal
    series: list[WeeklyObservation] = Field(
        description="Weekly observations in ascending date order.",
    )
    trend: TrendSummary
    provenance: Provenance
    summary: str = Field(description="1–2 sentence plain-English summary.")
    caveats: list[str] = Field(default_factory=list)


# ── Tool 3: compare_to_prior_seasons ─────────────────────────────────────────


class SeasonInput(BaseModel):
    """Input for compare_to_prior_seasons.

    Compares the current season's value at the equivalent week to prior seasons.
    """

    jurisdiction: Annotated[str, _JURISDICTION_FIELD]
    pathogen: Pathogen = _PATHOGEN_FIELD
    signal: Signal = _SIGNAL_FIELD
    prior_seasons: int = Field(
        default=3,
        ge=1,
        le=5,
        description="Number of prior seasons to compare against (1–5).",
    )
    as_of: str | None = _AS_OF_FIELD


class SeasonOutput(BaseModel):
    """Output for compare_to_prior_seasons.

    USE WHEN: You need historical context — is this season worse or better than
    typical? Includes prior-season data points for citation.
    """

    jurisdiction: str
    pathogen: Pathogen
    signal: Signal
    comparison: SeasonSummary
    provenance: Provenance
    summary: str = Field(description="1–2 sentence plain-English summary.")
    caveats: list[str] = Field(default_factory=list)


# ── Tool 4: find_jurisdictions_with_rising_activity ──────────────────────────


class ScanInput(BaseModel):
    """Input for find_jurisdictions_with_rising_activity.

    Scans all jurisdictions for a pathogen/signal and returns those with a
    rising trend, optionally filtered to an HHS region.
    """

    pathogen: Pathogen = _PATHOGEN_FIELD
    signal: Signal = _SIGNAL_FIELD
    hhs_region: int | None = Field(
        default=None,
        ge=1,
        le=10,
        description=(
            "Filter to a specific HHS region (1–10). Omit to scan all 50 states + DC."
        ),
    )
    min_level: LevelArg = Field(
        default=None,
        description=(
            "Minimum CDC official level to include "
            "(Very Low | Low | Moderate | High | Very High). "
            "Applies only to hospital_admissions signal."
        ),
    )
    limit: int = Field(
        default=10,
        ge=1,
        le=56,
        description="Maximum number of jurisdictions to return (1–56).",
    )
    as_of: str | None = _AS_OF_FIELD


class ScanRow(BaseModel):
    """One jurisdiction result from a national scan."""

    jurisdiction: str
    trend_direction: str
    latest_value: float | None = None
    latest_week_ending: date | None = None
    official_level: str | None = None
    pct_change: float | None = None
    provenance: Provenance | None = None


class ScanOutput(BaseModel):
    """Output for find_jurisdictions_with_rising_activity.

    USE WHEN: You need to identify which states/territories are currently
    experiencing rising activity — for regional hotspot analysis.
    DO NOT use for a single-jurisdiction question; use get_respiratory_snapshot
    or assess_trend instead.
    """

    pathogen: Pathogen
    signal: Signal
    hhs_region: int | None = None
    trend_attribution: str = TREND_ATTRIBUTION
    as_of_week_ending: date | None = None
    rising: list[ScanRow] = Field(
        description=(
            "Jurisdictions with increasing trend, ranked by latest_value descending."
        ),
    )
    provenance: Provenance
    n_jurisdictions_scanned: int
    status: Literal["ok", "partial", "insufficient_data"] = "ok"
    n_assessed: int = 0
    n_unavailable: int = 0
    n_rising_total: int = 0
    unavailable_jurisdictions: list[str] = Field(default_factory=list)
    n_insufficient_data: int = Field(
        description="Jurisdictions excluded due to insufficient data.",
    )
    summary: str = Field(description="1–2 sentence plain-English summary.")
    caveats: list[str] = Field(default_factory=list)

    @computed_field
    @property
    def rising_jurisdictions(self) -> list[str]:
        """Membership of the returned rows, after any requested result limit."""
        return [row.jurisdiction for row in self.rising]

    @computed_field
    @property
    def n_returned(self) -> int:
        return len(self.rising)

    @computed_field
    @property
    def display_text(self) -> str:
        """A copyable list and counts derived from this response, not LLM recall."""
        codes = ", ".join(self.rising_jurisdictions) or "none returned"
        scope = (
            f"HHS Region {self.hhs_region}" if self.hhs_region else "US states and DC"
        )
        return (
            f"Scope: {scope}. Signal: {self.pathogen.value} {self.signal.value}. "
            f"Latest observation week ending: {self.as_of_week_ending}.\n"
            f"Returned rising jurisdictions ({self.n_returned}): {codes}.\n"
            f"Total rising before result limit: {self.n_rising_total}. "
            f"Assessed: {self.n_assessed}. Requested: {self.n_jurisdictions_scanned}. "
            f"Insufficient data: {self.n_insufficient_data}. "
            f"Unavailable: {self.n_unavailable}. Status: {self.status}.\n"
            f"{self.trend_attribution} "
            "Missing or insufficient data is not evidence of stable activity."
        )
