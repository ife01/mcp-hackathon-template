"""Resource: resp://methods

Documents the analytic methods used by this server: trend classification,
season comparison, and concordance. All are server heuristics, not official
CDC classifications.
"""

from __future__ import annotations

from fastmcp import FastMCP

_METHODS_TEXT = """\
# Respiratory MCP Server — Analytic Methods

## ⚠️ Disclaimer

**All analytics produced by this server are heuristics for situational-awareness
only. They are NOT official CDC classifications and must NOT be cited as such.**
Official CDC activity levels (from NHSN) are carried in `official_level` fields
in every tool output. Use those for authoritative characterizations.

---

## 1. Trend Classification

**Method**: "2w vs prior 2w" — mean of latest 2 weeks vs. mean of prior 2 weeks.

| Signal | Classification threshold |
|--------|--------------------------|
| hospital_admissions | ≥10% relative change AND ≥0.1 per 100k absolute |
| test_positivity | ≥1.0 percentage-point absolute change |
| wastewater | ≥15% relative change |

**Rules**:
- Trailing None values are stripped before windowing.
- Fewer than 4 non-null observations → `insufficient_data`.
- **Small-number guard** (hospital admissions only): if the mean admission count
  across both windows is below 10, the result is downgraded to `insufficient_data`
  to avoid spurious percentage swings in low-count jurisdictions.
- Zero prior-window mean → `pct_change = None`; wastewater and hospital defaults
  to stable; test positivity uses absolute threshold directly.

**Output basis**: always `server_heuristic` — never `official_cdc_level_change`.

---

## 2. Season Comparison

**Method**: `week_of_season_aligned` — align by MMWR week-of-season (1 = week 27).

- Week 27 of the start year = week 1 of the season.
- If the exact prior-season date has no data, the nearest available week (±1 week)
  is used and noted in `alignment_note`.
- 53-week MMWR years (e.g. 2020, 2025) are handled without clipping.
- Pre-2024 NHSN seasons can be excluded (see `exclude_pre_transition_nhsn` flag)
  due to the 2024 mandatory-reporting transition.

**rank_vs_prior**: 1 = highest value at this week compared to prior seasons.
**pct_of_prior_peak**: current_value / max(prior week values) × 100.

---

## 3. Cross-Signal Concordance

| Pattern | Condition |
|---------|-----------|
| `concordant_increase` | All usable signals increasing |
| `concordant_decrease` | All usable signals decreasing |
| `stable` | All usable signals stable |
| `early_warning` | ≥1 signal increasing, rest stable, none decreasing |
| `mixed` | Mix of increasing/decreasing, or decreasing+stable |
| `insufficient_data` | No usable signals |

**Lag Guard**: If `max(latest_week_ending) − min(latest_week_ending) > 14 days`
across signals, `temporal_alignment_note` is set and the explanation qualifies
the concordance with "interpret with caution."

---

## 4. Season Definition

MMWR week 27 through week 26 of the following calendar year.
Example: 2025-26 season = MMWR week 27/2025 → week 26/2026.

Calculations use the `epiweeks` library (CDC-compliant MMWR week numbering).

---

## 5. Narrative Generation

Deterministic 2–4 plain-English sentences from templates. No LLM is used.
Numbers are rounded to 1 decimal place. Output always includes a disclaimer
that trend direction is a server heuristic.
"""


def register(mcp: FastMCP) -> None:
    """Register resp://methods resource."""

    @mcp.resource(
        "resp://methods",
        name="analytic_methods",
        description=(
            "Documents the trend classification, season comparison, and "
            "concordance methods used by this server. All are server heuristics, "
            "not official CDC classifications. Read this before interpreting "
            "trend direction or concordance pattern fields in tool output."
        ),
        mime_type="text/markdown",
    )
    def analytic_methods() -> str:
        return _METHODS_TEXT
