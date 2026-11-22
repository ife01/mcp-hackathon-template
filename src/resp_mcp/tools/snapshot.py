"""Tool 1: get_respiratory_snapshot

Returns the latest week's respiratory activity levels across all three signals
for the requested pathogens in a single jurisdiction.

USE WHEN: You need a quick multi-pathogen, multi-signal status overview.
"""

from __future__ import annotations

import asyncio
import logging
from datetime import date

from fastmcp import FastMCP

from resp_mcp.analytics.concordance import SignalTrendInput, assess_concordance
from resp_mcp.analytics.trend import classify_trend
from resp_mcp.models.common import Pathogen
from resp_mcp.models.tool_io import (
    AsOfArg,
    JurisdictionArg,
    PathogensArg,
    PathogenSnapshot,
    SignalReading,
    SnapshotInput,
    SnapshotOutput,
)
from resp_mcp.reference.jurisdictions import resolve_jurisdiction
from resp_mcp.sources.registry import SignalUnavailable, fetch_all
from resp_mcp.tools._helpers import (
    AS_OF_CAVEAT,
    classify_tool_error,
    date_window,
    parse_as_of,
    resolve_pathogen,
    trend_to_summary,
)

logger = logging.getLogger(__name__)

_SNAPSHOT_LOOKBACK = 8  # weeks of data fetched for trend classification


def register(mcp: FastMCP) -> None:
    """Register get_respiratory_snapshot with the MCP server."""

    @mcp.tool(
        annotations={
            "readOnlyHint": True,
            "openWorldHint": True,
            "idempotentHint": True,
        },
    )
    async def get_respiratory_snapshot(
        jurisdiction: JurisdictionArg,
        pathogens: PathogensArg = None,
        as_of: AsOfArg = None,
    ) -> dict:
        """Get the current respiratory activity snapshot for a jurisdiction.

        Returns the latest week's levels for influenza, COVID-19, and/or RSV
        across three signals: hospital admissions (NHSN), wastewater (NWSS),
        and test positivity (NREVSS).

        USE WHEN you want a quick overview of all pathogens and signals for one
        location. Each signal includes the latest value, CDC official level (if
        available), and a heuristic trend direction.

        DO NOT use this tool for detailed weekly series or multi-season comparison
        — use assess_trend or compare_to_prior_seasons instead.

        Returns: jurisdiction, latest week-ending date, per-pathogen signal
        readings, cross-signal concordance pattern, and caveats.
        """
        try:
            return await _get_respiratory_snapshot_impl(jurisdiction, pathogens, as_of)
        except Exception as exc:  # noqa: BLE001
            return classify_tool_error(exc)

    async def _get_respiratory_snapshot_impl(
        jurisdiction: JurisdictionArg,
        pathogens: PathogensArg,
        as_of: AsOfArg,
    ) -> dict:
        inp = SnapshotInput(
            jurisdiction=jurisdiction,
            pathogens=[resolve_pathogen(p) for p in (pathogens or list(Pathogen))],
            as_of=as_of,
        )

        jur = resolve_jurisdiction(inp.jurisdiction)
        inp.pathogens = list(dict.fromkeys(inp.pathogens))
        as_of_date = parse_as_of(inp.as_of)
        end = as_of_date or date.today()
        start, _ = date_window(_SNAPSHOT_LOOKBACK, end)

        pathogen_snapshots: list[PathogenSnapshot] = []
        all_latest_dates: list[date] = []
        all_caveats: list[str] = [AS_OF_CAVEAT] if as_of_date else []
        failed_datasets: set[str] = set()

        all_results = await asyncio.gather(
            *(fetch_all(jur, p, start, end) for p in inp.pathogens)
        )
        for pathogen, results in zip(inp.pathogens, all_results):
            readings: list[SignalReading] = []
            concordance_inputs: list[SignalTrendInput] = []

            for result in results:
                if isinstance(result, SignalUnavailable):
                    failed_datasets.add(result.dataset_id)
                    all_caveats.append(
                        f"{result.signal.value}: source {result.dataset_id} "
                        f"unavailable."
                    )
                    readings.append(
                        SignalReading(
                            signal=result.signal,
                            status="unavailable",
                            message=(
                                f"Source {result.dataset_id} unavailable; retry later."
                            ),
                        )
                    )
                    continue

                # SignalResult — classify trend over the window
                obs = sorted(
                    (o for o in result.observations if start <= o.week_ending <= end),
                    key=lambda o: o.week_ending,
                )
                latest = max(obs, key=lambda o: o.week_ending) if obs else None
                if latest and as_of_date:
                    # Restrict to as_of
                    obs_filtered = [o for o in obs if o.week_ending <= as_of_date]
                    latest = (
                        max(obs_filtered, key=lambda o: o.week_ending)
                        if obs_filtered
                        else None
                    )
                    obs = obs_filtered

                is_context = (
                    jur.type != "national"
                    and result.provenance.geography_level == "national"
                )
                if is_context:
                    all_caveats.append(
                        "National test positivity is context only "
                        "and excluded from local "
                        "concordance."
                    )
                prov = result.provenance.model_copy(
                    update={
                        "latest_week_ending": latest.week_ending if latest else None,
                    }
                )
                status = "ok"
                message = None
                if latest is None:
                    status = "insufficient_data"
                    message = "No observations in the requested date window."
                elif latest.value is None:
                    status = (
                        "insufficient_coverage"
                        if result.signal.value == "wastewater"
                        else "insufficient_data"
                    )
                    message = "Latest observation has no usable value."
                elif (end - latest.week_ending).days > 21:
                    status = "insufficient_data"
                    message = (
                        "Latest observation is more than 21 days before the requested "
                        "cutoff."
                    )
                if message:
                    all_caveats.append(f"{result.signal.value}: {message}")
                trend_result = classify_trend(obs, result.signal, reference_date=end)
                trend_summary = trend_to_summary(trend_result) if trend_result else None

                if status == "ok" and not is_context and prov.latest_week_ending:
                    concordance_inputs.append(
                        SignalTrendInput(
                            signal=result.signal,
                            trend=trend_result,
                            provenance=prov,
                        )
                    )

                if prov.latest_week_ending:
                    all_latest_dates.append(prov.latest_week_ending)
                all_caveats.extend(result.provenance.notes)

                readings.append(
                    SignalReading(
                        signal=result.signal,
                        status=status,
                        role="national_context" if is_context else "local",
                        message=message,
                        latest=latest,
                        trend=trend_summary,
                        provenance=prov,
                    )
                )

            concordance = (
                assess_concordance(concordance_inputs) if concordance_inputs else None
            )

            pathogen_snapshots.append(
                PathogenSnapshot(
                    pathogen=pathogen,
                    signals=readings,
                    concordance_pattern=concordance.pattern if concordance else None,
                    concordance_note=concordance.explanation if concordance else None,
                )
            )

        as_of_week = max(all_latest_dates) if all_latest_dates else None
        readings_flat = [r for ps in pathogen_snapshots for r in ps.signals]
        if readings_flat and all(r.status == "unavailable" for r in readings_flat):
            return {
                "error": "upstream_unavailable",
                "message": "All requested CDC sources are unavailable; "
                "no assessment was "
                "made.",
                "dataset_ids": sorted(failed_datasets),
                "caveats": list(dict.fromkeys(all_caveats)),
            }
        # Build a simple summary
        rising = [
            ps.pathogen.value
            for ps in pathogen_snapshots
            if ps.concordance_pattern == "concordant_increase"
        ]
        summary_parts = [f"Respiratory snapshot for {jur.name} ({jur.code})."]
        if rising:
            summary_parts.append(f"Rising signals: {', '.join(rising)}.")
        if as_of_week:
            summary_parts.append(f"Data through {as_of_week.isoformat()}.")
        summary_parts.append(
            "Trends and site aggregates are server heuristics; "
            "use official_level for authoritative CDC levels."
        )

        out = SnapshotOutput(
            jurisdiction=jur.code,
            as_of_week_ending=as_of_week,
            pathogens=pathogen_snapshots,
            summary=" ".join(summary_parts),
            caveats=list(dict.fromkeys(all_caveats)),  # deduplicate, preserve order
        )
        return out.model_dump(mode="json")
