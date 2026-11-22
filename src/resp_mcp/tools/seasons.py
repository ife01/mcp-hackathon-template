"""Tool 3: compare_to_prior_seasons

Compares the current season's value at the equivalent week to prior seasons.

USE WHEN: You need historical context — is this season worse or better than typical?
"""

from __future__ import annotations

import logging
from datetime import date

from fastmcp import FastMCP

from resp_mcp.analytics.seasons import compare_to_prior_seasons as _compare_seasons
from resp_mcp.models.common import Signal
from resp_mcp.models.tool_io import (
    AsOfArg,
    JurisdictionArg,
    PathogenArg,
    PriorSeasonsArg,
    SeasonInput,
    SeasonOutput,
    SignalArg,
)
from resp_mcp.reference.jurisdictions import resolve_jurisdiction
from resp_mcp.sources import nhsn, nrevss, nwss
from resp_mcp.tools._helpers import (
    AS_OF_CAVEAT,
    classify_tool_error,
    parse_as_of,
    resolve_pathogen,
    resolve_signal,
    season_to_summary,
)

logger = logging.getLogger(__name__)

_SEASON_LOOKBACK = 52 * 4  # 4 seasons worth of weekly data

_ADAPTERS = {
    Signal.hospital_admissions: lambda *args: nhsn.fetch_series(*args),
    Signal.wastewater: lambda *args: nwss.fetch_series(*args),
    Signal.test_positivity: lambda *args: nrevss.fetch_series(*args),
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
        jurisdiction: JurisdictionArg,
        pathogen: PathogenArg,
        signal: SignalArg,
        prior_seasons: PriorSeasonsArg = 3,
        as_of: AsOfArg = None,
    ) -> dict:
        """Compare current-season activity to prior seasons at the equivalent week.

        Aligns the current week-of-season to the same week in up to 5 prior
        seasons. Returns rank among available prior-week comparisons and percentage of
        the prior peak.

        USE WHEN you need historical context: Is this week worse than typical?
        How does this week compare with available prior weeks and complete-season peaks?

        DO NOT use for current-week levels or trend direction — use
        get_respiratory_snapshot or assess_trend instead.

        Returns: season comparison with prior-season data points, rank, % of
        prior peak, provenance, and caveats.
        """
        try:
            return await _compare_to_prior_seasons_impl(
                jurisdiction, pathogen, signal, prior_seasons, as_of
            )
        except Exception as exc:  # noqa: BLE001
            return classify_tool_error(exc)

    async def _compare_to_prior_seasons_impl(
        jurisdiction: JurisdictionArg,
        pathogen: PathogenArg,
        signal: SignalArg,
        prior_seasons: PriorSeasonsArg,
        as_of: AsOfArg,
    ) -> dict:
        inp = SeasonInput(
            jurisdiction=jurisdiction,
            pathogen=resolve_pathogen(pathogen),
            signal=resolve_signal(signal),
            prior_seasons=prior_seasons,
            as_of=as_of,
        )

        jur = resolve_jurisdiction(inp.jurisdiction)
        as_of_date = parse_as_of(inp.as_of)
        # Fetch from the first requested season boundary, not a fixed four years.
        from resp_mcp.reference.epiweeks import season_of, week_ending

        end = as_of_date or date.today()
        season_year = int(season_of(end).split("-")[0])
        start = week_ending(season_year - inp.prior_seasons, 27)

        fetch_fn = _ADAPTERS[inp.signal]
        obs, prov = await fetch_fn(jur, inp.pathogen, start, end)

        # Apply as_of filter and choose reference date
        obs = sorted(
            (o for o in obs if start <= o.week_ending <= end),
            key=lambda o: o.week_ending,
        )
        prov = prov.model_copy(
            update={"latest_week_ending": obs[-1].week_ending if obs else None}
        )
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
            f"{inp.pathogen.value.capitalize()} {inp.signal.value} in "
            f"{obs[-1].jurisdiction if obs else jur.code}, "
            f"week {wos} of the {cmp.current_season} season."
        )
        if rank == 1:
            summary += (
                f" Highest among {cmp.n_prior_compared} available prior-week "
                f"comparisons."
            )
        elif rank is None:
            summary += " No usable historical rank is available."
        elif pct is not None:
            pct_str = f"{round(pct, 1)}%"
            summary += (
                f" Current level is {pct_str} of the highest complete prior-season "
                f"peak."
            )
        all_notes = (
            list(prov.notes) + cmp.notes + ([AS_OF_CAVEAT] if as_of_date else [])
        )

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
