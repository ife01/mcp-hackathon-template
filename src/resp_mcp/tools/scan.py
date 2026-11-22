"""Find rising jurisdictions without treating missing data as stable activity."""

from __future__ import annotations

from fastmcp import FastMCP

from resp_mcp.analytics.trend import TrendDirection, classify_trend
from resp_mcp.models.common import Signal
from resp_mcp.models.tool_io import (
    AsOfArg,
    LevelArg,
    LimitArg,
    PathogenArg,
    RegionArg,
    ScanInput,
    ScanOutput,
    ScanRow,
    SignalArg,
)
from resp_mcp.reference.jurisdictions import get_all_jurisdictions, get_by_hhs_region
from resp_mcp.sources.bulk import fetch_many
from resp_mcp.tools._helpers import (
    AS_OF_CAVEAT,
    classify_tool_error,
    date_window,
    parse_as_of,
    resolve_pathogen,
    resolve_signal,
    structured_error,
)

_LEVEL_ORDER = {
    name: i
    for i, name in enumerate(["Very Low", "Low", "Moderate", "High", "Very High"])
}


def register(mcp: FastMCP) -> None:
    @mcp.tool(
        annotations={
            "readOnlyHint": True,
            "openWorldHint": True,
            "idempotentHint": True,
        }
    )
    async def find_jurisdictions_with_rising_activity(
        pathogen: PathogenArg,
        signal: SignalArg,
        hhs_region: RegionArg = None,
        min_level: LevelArg = None,
        limit: LimitArg = 10,
        as_of: AsOfArg = None,
    ) -> dict:
        """Find rising states/DC for hospital admissions or wastewater.

        USE WHEN comparing jurisdictions; use assess_trend for one location.
        National-only test positivity cannot support a state scan. Fetches one
        paginated query and reports assessed/missing counts, per-row provenance,
        and caveats. min_level applies only to hospital admissions.
        Results are descriptive heuristics, not validated outbreak predictions.
        """
        try:
            inp = ScanInput(
                pathogen=resolve_pathogen(pathogen),
                signal=resolve_signal(signal),
                hhs_region=hhs_region,
                min_level=min_level,
                limit=limit,
                as_of=as_of,
            )
            if inp.signal == Signal.test_positivity:
                return structured_error(
                    "unsupported_geography",
                    "Test positivity is national-only. Use assess_trend with "
                    "jurisdiction='USA'; state hotspots cannot be inferred.",
                )
            if min_level and inp.signal != Signal.hospital_admissions:
                return structured_error(
                    "invalid_input", "min_level applies only to hospital_admissions."
                )
            start, end = date_window(8, parse_as_of(inp.as_of))
            jurisdictions = (
                get_by_hhs_region(hhs_region) if hhs_region else get_all_jurisdictions()
            )
            jurisdictions = [
                j for j in jurisdictions if j.type in ("state", "district")
            ]
            results = await fetch_many(
                jurisdictions, inp.pathogen, inp.signal, start, end
            )
            return _summarize(inp, jurisdictions, results, start, end)
        except Exception as exc:
            return classify_tool_error(exc)


def _summarize(inp, jurisdictions, results, start, end) -> dict:
    rows, caveats, unavailable = [], [AS_OF_CAVEAT] if inp.as_of else [], []
    insufficient = assessed = 0
    provenances = []
    for jur in jurisdictions:
        result = results.get(jur.code)
        if result is None:
            unavailable.append(jur.code)
            continue
        obs, prov = result
        obs = sorted(
            (o for o in obs if start <= o.week_ending <= end),
            key=lambda o: o.week_ending,
        )
        prov = prov.model_copy(
            update={"latest_week_ending": obs[-1].week_ending if obs else None}
        )
        provenances.append(prov)
        caveats.extend(prov.notes)
        if prov.geography_level == "national" or any(
            o.jurisdiction != jur.code for o in obs
        ):
            insufficient += 1
            caveats.append(f"{jur.code}: incompatible source geography; excluded.")
            continue
        trend = classify_trend(obs, inp.signal, reference_date=end)
        caveats.extend(trend.notes)
        if (
            trend.direction == TrendDirection.insufficient_data
            or not obs
            or (end - obs[-1].week_ending).days > 21
        ):
            insufficient += 1
            continue
        assessed += 1
        latest = obs[-1]
        if (
            inp.min_level
            and _LEVEL_ORDER.get(latest.official_level or "", -1)
            < _LEVEL_ORDER[inp.min_level]
        ):
            continue
        if trend.direction == TrendDirection.increasing:
            rows.append(
                ScanRow(
                    jurisdiction=jur.code,
                    trend_direction=trend.direction.value,
                    latest_value=latest.value,
                    latest_week_ending=latest.week_ending,
                    official_level=latest.official_level,
                    pct_change=trend.pct_change,
                    provenance=prov,
                )
            )
    if len(unavailable) == len(jurisdictions):
        return structured_error(
            "upstream_unavailable",
            "No jurisdictions could be retrieved; no assessment was made.",
            unavailable_jurisdictions=unavailable,
        )
    total = len(rows)
    rows.sort(key=lambda r: (-(r.latest_value or 0), r.jurisdiction))
    status = (
        "insufficient_data"
        if not assessed
        else "partial"
        if insufficient or unavailable
        else "ok"
    )
    if insufficient:
        caveats.append(
            f"{insufficient} jurisdictions lack usable, current, consecutive "
            f"weekly data; no trend inference was made for them."
        )
    if unavailable:
        caveats.append(f"Source unavailable for: {', '.join(unavailable)}.")
    summary = (
        f"{total} rising jurisdiction(s) among {assessed} assessed of "
        f"{len(jurisdictions)} requested. "
        f"Returning {min(total, inp.limit)}; missing jurisdictions are not "
        f"evidence of stable activity."
    )
    if not assessed:
        summary = (
            "Insufficient data to assess rising activity in any requested jurisdiction."
        )
    prov = provenances[0].model_copy(
        update={
            "latest_week_ending": max(
                (p.latest_week_ending for p in provenances if p.latest_week_ending),
                default=None,
            ),
            "notes": [
                "Scan-level provenance; each returned row has "
                "jurisdiction-specific provenance."
            ],
        }
    )
    return ScanOutput(
        pathogen=inp.pathogen,
        signal=inp.signal,
        as_of_week_ending=prov.latest_week_ending,
        rising=rows[: inp.limit],
        provenance=prov,
        n_jurisdictions_scanned=len(jurisdictions),
        n_assessed=assessed,
        n_insufficient_data=insufficient,
        n_unavailable=len(unavailable),
        unavailable_jurisdictions=unavailable,
        n_rising_total=total,
        status=status,
        summary=summary,
        caveats=list(dict.fromkeys(caveats)),
    ).model_dump(mode="json")
