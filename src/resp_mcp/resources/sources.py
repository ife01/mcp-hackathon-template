"""Resource: resp://sources

Provides a human-readable summary of the three CDC data sources used by this
server, including dataset IDs, URLs, cadence, geographic scope, and key caveats.
"""
# ruff: noqa: E501  — markdown content strings intentionally exceed 88 chars

from __future__ import annotations

from fastmcp import FastMCP

_SOURCES_TEXT = """\
# Respiratory MCP Server — Data Sources

Three public CDC Socrata datasets are used. All data is retrieved read-only
from data.cdc.gov with no authentication required (app token improves rate limits).

---

## 1. NHSN Hospital Admissions
- **Dataset ID**: vdzy-6i9v
- **URL**: https://data.cdc.gov/resource/vdzy-6i9v.json
- **Full name**: Weekly Hospital Respiratory Admission Levels and Rates by Jurisdiction, National Healthcare Safety Network (NHSN)
- **Signal**: hospital_admissions
- **Cadence**: Weekly (Fridays); data through the prior Saturday
- **Geography**: 50 states + DC + Puerto Rico + Virgin Islands + national (USA)
- **Unit**: admissions per 100,000 population (per100k)
- **Official levels**: Very Low / Low / Medium / High / Very High (CDC-assigned per jurisdiction per week)
- **Caveats**:
  - Mandatory reporting began 2024; pre-2024 data may undercount due to voluntary participation.
  - Coverage metric (% hospitals reporting) varies by jurisdiction.

---

## 2. NWSS Wastewater
- **Dataset ID**: atcp-73re
- **URL**: https://data.cdc.gov/resource/atcp-73re.json
- **Full name**: CDC Wastewater Viral Activity Level for SARS-CoV-2, Influenza A and RSV
- **Signal**: wastewater
- **Cadence**: Weekly; typically updated within 1–2 weeks of collection
- **Geography**: Site-level data aggregated to state level by this server
- **Unit**: WVAL (Wastewater Viral Activity Level, a composite index)
- **Official levels**: Very Low / Low / Medium / High / Very High (site_wval_category, CDC-assigned per site)
- **Caveats**:
  - Influenza A only (not influenza B); NREVSS covers A+B combined.
  - Fewer than 2 sites reporting → value set to None (insufficient coverage).
  - Puerto Rico: zero sites → no wastewater signal available.
  - State aggregate = median site_wval; official level = modal site_wval_category.

---

## 3. NREVSS Test Positivity
- **Dataset ID**: seuz-s2cv
- **URL**: https://data.cdc.gov/resource/seuz-s2cv.json
- **Full name**: Percent of Tests Positive for Viral Respiratory Pathogens
- **Signal**: test_positivity
- **Cadence**: Weekly; most recent week may be incomplete (≥90% complete two weeks back)
- **Geography**: National only — no state or HHS region breakdown
- **Unit**: percent positive (%)
- **Caveats**:
  - For state-level queries, the national value is applied with a provenance note.
  - Influenza: combined A+B (not split by subtype).
  - No official CDC level classification for this signal.

---

## Update schedule

All three datasets are retrieved fresh on each tool call (or served from the
in-memory TTL cache, default 1 hour). Cache TTL is configurable via
CACHE_TTL_SECONDS environment variable.
"""


def register(mcp: FastMCP) -> None:
    """Register resp://sources resource."""

    @mcp.resource(
        "resp://sources",
        name="data_sources",
        description=(
            "Overview of the three CDC data sources used by this server: "
            "NHSN hospital admissions (vdzy-6i9v), NWSS wastewater (atcp-73re), "
            "and NREVSS test positivity (seuz-s2cv). "
            "Includes dataset IDs, URLs, cadence, geography, units, and caveats."
        ),
        mime_type="text/markdown",
    )
    def data_sources() -> str:
        return _SOURCES_TEXT
