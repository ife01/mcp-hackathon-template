"""Tool 2: assess_trend

Returns a weekly time series and heuristic trend classification for one
jurisdiction / pathogen / signal.

USE WHEN: You need to characterise whether a signal is rising, stable, or falling.
"""

from __future__ import annotations

import logging

from fastmcp import FastMCP

from resp_mcp.analytics.trend import classify_trend
from resp_mcp.models.common import Signal
from resp_mcp.models.tool_io import TrendInput, TrendOutput
from resp_mcp.reference.jurisdictions import resolve_jurisdiction
from resp_mcp.sources import nhsn, nrevss, nwss
from resp_mcp.tools._helpers import (
    classify_tool_error,
    date_window,
    parse_as_of,
    resolve_pathogen,
    resolve_signal,
    trend_to_summary,
)

logger = logging.getLogger(__name__)

_ADAPTERS = {
    Signal.hospital_admissions: nhsn.fetch_series,
    Signal.wastewater: nwss.fetch_series,
    Signal.test_positivity: nrevss.fetch_series,
}


def register(mcp: FastMCP) -> None:
    """Register assess_trend with the MCP server."""

    @mcp.tool(
        annotations={
            "readOnlyHint": True,
            "openWorldHint": True,
            "idempotentHint": True,
        },
    )
    async def assess_trend(
        jurisdiction: str,
        pathogen: str,
        signal: str,
        lookback_weeks: int = 8,
        as_of: str | None = None,
    ) -> dict:
        """Assess the recent trend for one respiratory signal in a jurisdiction.

        Returns a weekly time series and a heuristic trend classification
        (increasing / stable / decreasing / insufficient_data) for one
        combination of jurisdiction, pathogen, and signal.

        USE WHEN you want to characterise the direction of change for a specific
        signal over recent weeks. Includes the weekly series so values can be cited.

        DO NOT use for multi-pathogen overviews — use get_respiratory_snapshot.
        DO NOT use for prior-season comparison — use compare_to_prior_seasons.

        Returns: weekly series, trend direction, % change, provenance, and caveats.
        """
        try:
            return await _assess_trend_impl(
                jurisdiction, pathogen, signal, lookback_weeks, as_of
            )
        except Exception as exc:  # noqa: BLE001
            return classify_tool_error(exc)

    async def _assess_trend_impl(
        jurisdiction: str,
        pathogen: str,
        signal: str,
        lookback_weeks: int,
        as_of: str | None,
    ) -> dict:
        inp = TrendInput(
            jurisdiction=jurisdiction,
            pathogen=resolve_pathogen(pathogen),
            signal=resolve_signal(signal),
            lookback_weeks=lookback_weeks,
            as_of=as_of,
        )

        jur = resolve_jurisdiction(inp.jurisdiction)
        as_of_date = parse_as_of(inp.as_of)
        start, end = date_window(inp.lookback_weeks, as_of_date)

        fetch_fn = _ADAPTERS[inp.signal]
        obs, prov = await fetch_fn(jur, inp.pathogen, start, end)

        # Apply as_of filter
        if as_of_date:
            obs = [o for o in obs if o.week_ending <= as_of_date]

        trend_result = classify_trend(obs, inp.signal)
        trend_summary = trend_to_summary(trend_result)

        # Build plain-English summary
        direction = trend_result.direction.value
        unit = obs[0].unit if obs else "units"
        latest_val = obs[-1].value if obs else None
        summary = (
            f"{inp.pathogen.value.capitalize()} {inp.signal.value} "
            f"in {jur.code} is {direction}."
        )
        if latest_val is not None:
            summary += f" Latest value: {round(latest_val, 1)} {unit}."
        summary += (
            " Trend is a server heuristic; "
            "see official_level for authoritative CDC classification."
        )

        out = TrendOutput(
            jurisdiction=jur.code,
            pathogen=inp.pathogen,
            signal=inp.signal,
            series=obs,
            trend=trend_summary,
            provenance=prov,
            summary=summary,
            caveats=prov.notes,
        )
        return out.model_dump(mode="json")
