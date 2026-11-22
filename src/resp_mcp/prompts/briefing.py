"""Prompts for the Respiratory Season Situational Awareness MCP server.

Two prompts:
  1. weekly_respiratory_briefing(jurisdiction, audience)
  2. regional_hotspot_review(pathogen, hhs_region)
"""

from __future__ import annotations

from fastmcp import FastMCP

_BRIEFING_RULES = """\
You are a respiratory disease situational awareness assistant. Follow these rules:

1. **Always call tools first.** Use get_respiratory_snapshot for the overview, \
assess_trend for trend detail, and compare_to_prior_seasons for historical context. \
Never state numbers before calling a tool.

2. **Cite your sources.** For every number you state, include the dataset name \
and week-ending date from the tool's provenance field \
(e.g., "NHSN, week ending 2026-11-14").

3. **Use official CDC levels.** Report the official_level field \
(Very Low / Low / Moderate / High / Very High) from NHSN hospital admissions \
as the authoritative characterization of severity. \
Trend direction (increasing/stable/decreasing) is a server heuristic — \
always label it as such.

4. **State caveats.** Include any caveats from the tool's caveats list, \
especially:
   - NREVSS test positivity is national only (no state breakdown).
   - Wastewater tracks influenza A only.
   - Pre-2024 NHSN data may undercount due to voluntary reporting.

5. **Never invent numbers.** Every figure in your answer must appear in a \
tool output. If data is unavailable, say so explicitly.

6. **End with a limitation statement** noting that all trend classifications \
are server heuristics and not official CDC determinations.
"""

_HOTSPOT_RULES = """\
You are a respiratory disease situational awareness assistant scanning for \
regional hotspots. Follow these rules:

1. Use find_jurisdictions_with_rising_activity to identify rising jurisdictions.
2. For the top 3–5 rising states, call assess_trend to confirm and add detail.
3. Report CDC official_level alongside trend direction for hospital admissions.
4. Note that wastewater tracks influenza A only; test positivity is national.
5. Cite dataset name and week-ending date for every figure.
6. Never invent numbers — all figures must come from tool calls.
7. End with: "Trend classifications are server heuristics, not official CDC \
determinations."
"""


def register(mcp: FastMCP) -> None:
    """Register both prompts with the MCP server."""

    @mcp.prompt(
        name="weekly_respiratory_briefing",
        description=(
            "Generates a structured prompt for a weekly respiratory situation "
            "update for one jurisdiction. Instructs the agent to call tools in "
            "the correct order, cite sources, use CDC official levels, state "
            "caveats, and never invent numbers. "
            "audience: 'epi' (technical) or 'public' (plain language)."
        ),
    )
    def weekly_respiratory_briefing(
        jurisdiction: str,
        audience: str = "epi",
    ) -> str:
        """Weekly respiratory briefing for a single jurisdiction.

        Args:
            jurisdiction: State code (e.g. 'GA'), 'USA', or full name.
            audience: 'epi' for epidemiologist-level detail, 'public' for
                plain-language summary suitable for a general audience.
        """
        audience_note = (
            "Write for an epidemiologist audience: include rates, percentages, "
            "MMWR week references, and technical caveats."
            if audience.lower() == "epi"
            else "Write for a general public audience: use plain language, avoid "
            "jargon, "
            "and explain what the data means in practical terms."
        )

        return (
            f"{_BRIEFING_RULES}\n\n"
            f"---\n\n"
            f"**Task**: Write a weekly respiratory situation update for "
            f"**{jurisdiction}**.\n\n"
            f"**Audience guidance**: {audience_note}\n\n"
            f"**Structure your response as follows**:\n"
            f"1. Current activity levels for influenza, COVID-19, and RSV "
            f"(hospital admissions, wastewater, test positivity).\n"
            f"2. Trend direction for each pathogen signal "
            f"(with server-heuristic label).\n"
            f"3. Historical context: how does this week compare to prior seasons?\n"
            f"4. Key caveats and data limitations.\n"
            f"5. One-sentence bottom line.\n"
        )

    @mcp.prompt(
        name="regional_hotspot_review",
        description=(
            "Generates a structured prompt for identifying which states in an "
            "HHS region (or nationally) are showing rising respiratory activity. "
            "Instructs the agent to use find_jurisdictions_with_rising_activity "
            "and then drill into the top results with assess_trend."
        ),
    )
    def regional_hotspot_review(
        pathogen: str = "influenza",
        hhs_region: int | None = None,
    ) -> str:
        """Regional hotspot review for one pathogen.

        Args:
            pathogen: 'influenza', 'covid19', or 'rsv'.
            hhs_region: HHS region number (1–10), or None for national scan.
        """
        region_scope = (
            f"HHS Region {hhs_region}"
            if hhs_region is not None
            else "all 50 states and DC (national scan)"
        )

        return (
            f"{_HOTSPOT_RULES}\n\n"
            f"---\n\n"
            f"**Task**: Identify jurisdictions with rising **{pathogen}** "
            f"activity across {region_scope}.\n\n"
            f"**Steps**:\n"
            f"1. Call find_jurisdictions_with_rising_activity with "
            f"pathogen='{pathogen}', signal='hospital_admissions'"
            + (f", hhs_region={hhs_region}" if hhs_region else "")
            + ".\n"
            "2. Also call with signal='wastewater' for the same scope.\n"
            "3. For the top 3–5 rising states, call assess_trend "
            "(hospital_admissions) for a weekly series.\n"
            "4. Summarise: which states are rising, what CDC level are they at, "
            "and is wastewater confirming the hospital signal?\n"
            "5. Note any states where signals disagree (mixed concordance).\n"
        )
