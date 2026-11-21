"""Tool 4: find_jurisdictions_with_rising_activity

Scans all state/district jurisdictions for a pathogen/signal and returns those
with an increasing trend. Optionally filtered to an HHS region.

Design: Fetches all jurisdictions concurrently, groups in memory, runs trend
classification — no per-jurisdiction serial queries.
"""

from __future__ import annotations

import asyncio
import logging

from fastmcp import FastMCP

from resp_mcp.analytics.trend import TrendDirection, classify_trend
from resp_mcp.models.common import Signal
from resp_mcp.models.tool_io import ScanInput, ScanOutput, ScanRow
from resp_mcp.reference.jurisdictions import (
    get_all_jurisdictions,
    get_by_hhs_region,
)
from resp_mcp.sources import nhsn, nrevss, nwss
from resp_mcp.tools._helpers import (
    classify_tool_error,
    date_window,
    parse_as_of,
    resolve_pathogen,
    resolve_signal,
)

logger = logging.getLogger(__name__)

_SCAN_LOOKBACK = 8  # weeks

_ADAPTERS = {
    Signal.hospital_admissions: nhsn.fetch_series,
    Signal.wastewater: nwss.fetch_series,
    Signal.test_positivity: nrevss.fetch_series,
}

# CDC NHSN level ordering (ascending severity)
_LEVEL_ORDER = {
    "Very Low": 0, "Low": 1, "Medium": 2, "High": 3, "Very High": 4,
}


def register(mcp: FastMCP) -> None:
    """Register find_jurisdictions_with_rising_activity with the MCP server."""

    @mcp.tool(
        annotations={
            "readOnlyHint": True,
            "openWorldHint": True,
            "idempotentHint": True,
        },
    )
    async def find_jurisdictions_with_rising_activity(
        pathogen: str,
        signal: str,
        hhs_region: int | None = None,
        min_level: str | None = None,
        limit: int = 10,
        as_of: str | None = None,
    ) -> dict:
        """Find US jurisdictions with currently rising respiratory activity.

        Scans all 50 states + DC (or a single HHS region) for a given pathogen
        and signal, returning those with an increasing trend, ranked by latest
        value (highest first).

        USE WHEN you need a regional hotspot view — which states are rising right
        now? Useful for weekly situation reports covering multiple jurisdictions.

        DO NOT use this tool for a single-jurisdiction question; use
        get_respiratory_snapshot or assess_trend instead.

        Returns: list of rising jurisdictions with trend direction, latest value,
        and CDC level, plus scan provenance and caveats.
        """
        try:
            return await _find_jurisdictions_impl(
                pathogen, signal, hhs_region, min_level, limit, as_of
            )
        except Exception as exc:  # noqa: BLE001
            return classify_tool_error(exc)

    async def _find_jurisdictions_impl(
        pathogen: str,
        signal: str,
        hhs_region: int | None,
        min_level: str | None,
        limit: int,
        as_of: str | None,
    ) -> dict:
        inp = ScanInput(
            pathogen=resolve_pathogen(pathogen),
            signal=resolve_signal(signal),
            hhs_region=hhs_region,
            min_level=min_level,
            limit=limit,
            as_of=as_of,
        )

        as_of_date = parse_as_of(inp.as_of)
        start, end = date_window(_SCAN_LOOKBACK, as_of_date)

        # Determine which jurisdictions to scan
        all_jurs = get_all_jurisdictions()
        if inp.hhs_region is not None:
            scan_jurs = get_by_hhs_region(inp.hhs_region)
        else:
            # Only states + DC (not national, not territories — NHSN covers 50+DC+PR+VI)
            scan_jurs = [
                j for j in all_jurs
                if j.type in ("state", "district")
            ]

        fetch_fn = _ADAPTERS[inp.signal]

        # Fetch all jurisdictions concurrently, absorbing failures
        async def _safe_fetch(jur):
            try:
                obs, prov = await fetch_fn(jur, inp.pathogen, start, end)
                return jur, obs, prov
            except Exception as exc:  # noqa: BLE001
                logger.warning("Scan fetch failed for %s: %s", jur.code, exc)
                return jur, [], None

        fetch_tasks = [_safe_fetch(j) for j in scan_jurs]
        raw_results = await asyncio.gather(*fetch_tasks)

        rows: list[ScanRow] = []
        n_insufficient = 0
        all_prov = None
        all_caveats: list[str] = []

        for jur, obs, prov in raw_results:
            if prov is not None and all_prov is None:
                all_prov = prov  # use first successful provenance as representative
            if prov is not None:
                all_caveats.extend(prov.notes)

            # Apply as_of filter
            if as_of_date:
                obs = [o for o in obs if o.week_ending <= as_of_date]

            if not obs:
                n_insufficient += 1
                continue

            trend = classify_trend(obs, inp.signal)
            if trend.direction == TrendDirection.insufficient_data:
                n_insufficient += 1
                continue

            latest = max(obs, key=lambda o: o.week_ending)

            # min_level filter (hospital admissions only)
            if inp.min_level and inp.signal == Signal.hospital_admissions:
                level_rank = _LEVEL_ORDER.get(latest.official_level or "", -1)
                min_rank = _LEVEL_ORDER.get(inp.min_level, 0)
                if level_rank < min_rank:
                    continue

            if trend.direction == TrendDirection.increasing:
                rows.append(ScanRow(
                    jurisdiction=jur.code,
                    trend_direction=trend.direction.value,
                    latest_value=latest.value,
                    latest_week_ending=latest.week_ending,
                    official_level=latest.official_level,
                    pct_change=trend.pct_change,
                ))

        # Sort by latest_value descending (None last)
        rows.sort(
            key=lambda r: r.latest_value if r.latest_value is not None else -1,
            reverse=True,
        )
        rows = rows[: inp.limit]

        # Build provenance fallback if all fetches failed
        if all_prov is None:
            from datetime import datetime, timezone

            from resp_mcp.models.common import Provenance
            from resp_mcp.sources import nhsn as _nhsn
            all_prov = Provenance(
                dataset_id=_nhsn.DATASET_ID,
                dataset_name=_nhsn.DATASET_NAME,
                url=_nhsn.DATASET_URL,  # type: ignore[arg-type]
                latest_week_ending=None,
                retrieved_at=datetime.now(timezone.utc),
                geography_level="state",
            )

        summary = (
            f"Found {len(rows)} jurisdiction(s) with rising "
            f"{inp.pathogen.value} {inp.signal.value} "
            f"out of {len(scan_jurs)} scanned."
        )

        out = ScanOutput(
            pathogen=inp.pathogen,
            signal=inp.signal,
            as_of_week_ending=as_of_date or end,
            rising=rows,
            provenance=all_prov,
            n_jurisdictions_scanned=len(scan_jurs),
            n_insufficient_data=n_insufficient,
            summary=summary,
            caveats=list(dict.fromkeys(all_caveats)),
        )
        return out.model_dump(mode="json")
