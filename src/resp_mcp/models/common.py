"""Shared domain models for the Respiratory MCP server.

Design note (from build plan §1.3):
  To prevent LLM context-window bloat in assess_trend (52 weekly rows) and
  find_jurisdictions_with_rising_activity (56 jurisdictions), Provenance is NOT
  nested inside every WeeklyObservation. It is attached once per signal/series
  on the parent container (TrendOutput, SeasonOutput, ScanOutput, etc.).
"""

from __future__ import annotations

from datetime import date, datetime
from enum import Enum
from typing import Literal

from pydantic import BaseModel, HttpUrl

# ── Enums ─────────────────────────────────────────────────────────────────────


class Pathogen(str, Enum):
    """The three respiratory pathogens tracked by this server."""

    influenza = "influenza"
    # NOTE: NWSS wastewater measures influenza A only. NREVSS seuz-s2cv
    # reports combined flu A+B. Source adapters must note this in Provenance.
    covid19 = "covid19"
    rsv = "rsv"


class Signal(str, Enum):
    """The three surveillance signal types available."""

    hospital_admissions = "hospital_admissions"
    # Source: NHSN vdzy-6i9v — rates per 100k + official CDC levels
    wastewater = "wastewater"
    # Source: NWSS atcp-73re — site_wval + site_wval_category
    test_positivity = "test_positivity"
    # Source: NREVSS seuz-s2cv — national percent positive


# ── Provenance ────────────────────────────────────────────────────────────────


class Provenance(BaseModel):
    """Data lineage for a single signal/series.

    Attached once per series (not per row) to keep tool outputs compact.
    """

    dataset_id: str
    dataset_name: str
    url: HttpUrl
    latest_week_ending: date | None
    retrieved_at: datetime
    source_last_updated: datetime | None = None
    geography_level: Literal["national", "state", "hhs_region", "site_aggregate"]
    notes: list[str] = []


# ── Observation ───────────────────────────────────────────────────────────────


class WeeklyObservation(BaseModel):
    """A single weekly data point for a jurisdiction/pathogen/signal combination.

    Provenance is NOT embedded here — it lives on the parent container.
    """

    jurisdiction: str
    week_ending: date
    value: float | None
    unit: Literal["admissions_per_100k", "admissions_count", "percent_positive", "wval"]
    # Official CDC level label when available (Very Low/Low/Moderate/High/Very High)
    official_level: str | None = None
    derived_level: str | None = None
    aggregation_method: str | None = None
    # Preserve counts alongside rates so the small-number guard runs in production.
    raw_count: float | None = None
    # Source-specific coverage metadata (e.g. {"n_sites": 4} or {"pct_hospitals": 68.1})
    coverage: dict[str, float | int] | None = None
