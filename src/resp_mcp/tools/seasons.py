"""Tool 3: compare_to_prior_seasons

Compares the current season's value at the equivalent week to prior seasons.

USE WHEN: You need historical context — is this season worse or better than typical?
"""

from __future__ import annotations

import logging

from fastmcp import FastMCP

from resp_mcp.analytics.seasons import compare_to_prior_seasons as _compare_seasons
from resp_mcp.models.common import Signal
from resp_mcp.models.tool_io import SeasonInput, SeasonOutput
from resp_mcp.reference.jurisdictions import resolve_jurisdiction
from resp_mcp.sources import nhsn, nrevss, nwss
from resp_mcp.tools._helpers import (
    date_window,
    parse_as_of,
    resolve_pathogen,
    resolve_signal,
    season_to_summary,
)

logger = logging.getLogger(__name__)

_SEASON_LOOKBACK = 52 * 4  # 4 seasons worth of weekly data

_ADAPTERS = {
    Signal.hospital_admissions: nhsn.fetch_series,
    Signal.wastewater: nwss.fetch_series,
    Signal.test_positivity: nrevss.fetch_series,
}


def register(mcp: FastMCP) -> None:
    """Register compare_to_prior_seasons with the MCP server."""

    @mcp.tool(
        annotations={
            "readOnlyHint": True,
            "openWorldHint": True,
            "idempotentHint": True,
        },
    )
    async def compare_to_prior_seasons(
        jurisdiction: str,
        pathogen: str,
        signal: str,
        prior_seasons: int = 3,
        as_of: str | None = None,
    ) -> dict:
        """Compare current-season activity to prior seasons at the equivalent week.

        Aligns the current week-of-season to the same week in up to 5 prior
        seasons. Returns rank (1 = highest ever at this week) and percentage of
        the prior peak.

        USE WHEN you need historical context: Is this week worse than typical?
        Has this season peaked yet compared to prior years?

        DO NOT use for current-week levels or trend direction — use
        get_respiratory_snapshot or assess_trend instead.

        Returns: season comparison with prior-season data points, rank, % of
        prior peak, provenance, and caveats.
        """
        inp = SeasonInput(
            jurisdiction=jurisdiction,
            pathogen=resolve_pathogen(pathogen),
            signal=resolve_signal(signal),
            prior_seasons=prior_seasons,
            as_of=as_of,
        )

        jur = resolve_jurisdiction(inp.jurisdiction)
        as_of_date = parse_as_of(inp.as_of)
        start, end = date_window(_SEASON_LOOKBACK, as_of_date)

        fetch_fn = _ADAPTERS[inp.signal]
        obs, prov = await fetch_fn(jur, inp.pathogen, start, end)

        # Apply as_of filter and choose reference date
        if as_of_date:
            obs = [o for o in obs if o.week_ending <= as_of_date]
        ref_date = max((o.week_ending for o in obs), default=end)

        exclude_nhsn = inp.signal == Signal.hospital_admissions
        cmp = _compare_seasons(
            obs,
            reference_date=ref_date,
            n_seasons=inp.prior_seasons,
            exclude_pre_transition_nhsn=exclude_nhsn,
        )
        comparison_summary = season_to_summary(cmp)

        # Build plain-English summary
        wos = cmp.current_week_of_season
        rank = cmp.rank_vs_prior
        pct = cmp.pct_of_prior_peak
        summary = (
            f"{inp.pathogen.value.capitalize()} {inp.signal.value} in {jur.code}, "
            f"week {wos} of the {cmp.current_season} season."
        )
        if rank == 1:
            summary += " This is the highest value at this week vs. prior seasons."
        elif pct is not None:
            pct_str = f"{round(pct, 1)}%"
            summary += f" Current level is {pct_str} of the highest prior-season value."
        all_notes = list(prov.notes) + cmp.notes

        out = SeasonOutput(
            jurisdiction=jur.code,
            pathogen=inp.pathogen,
            signal=inp.signal,
            comparison=comparison_summary,
            provenance=prov,
            summary=summary,
            caveats=list(dict.fromkeys(all_notes)),
        )
        return out.model_dump(mode="json")
