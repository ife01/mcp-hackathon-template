"""NWSS wastewater source adapter.

Dataset: atcp-73re
  CDC Wastewater Viral Activity Level for SARS-CoV-2, Influenza A and RSV

Key columns (verified Build 0.3):
  state_territory, week_end, site, population_served, source,
  site_wval, site_wval_category, pathogen_target, date_updated

Decisions (from docs/DECISIONS.md):
- Site-level data aggregated to state level using median site_wval.
- derived_level = unique modal site category; official_level is never fabricated.
- state_territory uses full English names (mapped from 2-letter codes).
- Empty results indicate missing observations, not absence of surveillance.
- Fewer than 2 sites → value=None + provenance note.
- Influenza = pathogen_target='Influenza A virus' (A only; note in provenance).
"""

from __future__ import annotations

import logging
import math
import statistics
from collections import Counter
from datetime import date, datetime, timezone

from resp_mcp.clients.socrata import query, soql_and, soql_eq, soql_gte, soql_lte
from resp_mcp.models.common import Pathogen, Provenance, WeeklyObservation
from resp_mcp.reference.jurisdictions import Jurisdiction, jurisdiction_full_name

logger = logging.getLogger(__name__)

DATASET_ID = "atcp-73re"
DATASET_NAME = "CDC Wastewater Viral Activity Level for SARS-CoV-2, Influenza A and RSV"
DATASET_URL = f"https://data.cdc.gov/resource/{DATASET_ID}.json"

_PATHOGEN_MAP: dict[Pathogen, str] = {
    Pathogen.influenza: "Influenza A virus",
    Pathogen.covid19: "SARS-CoV-2",
    Pathogen.rsv: "RSV",
}

_LEVEL_ORDER = ["Very Low", "Low", "Moderate", "High", "Very High"]


def _modal_category(categories: list[str]) -> str | None:
    """Return the most common category string, or None if list is empty."""
    if not categories:
        return None
    ranked = Counter(categories).most_common()
    return ranked[0][0] if len(ranked) == 1 or ranked[0][1] > ranked[1][1] else None


def _parse_float(val) -> float | None:
    if val is None or val == "":
        return None
    try:
        parsed = float(val)
        return parsed if math.isfinite(parsed) and parsed >= 0 else None
    except (ValueError, TypeError):
        return None


async def fetch_series(
    jurisdiction: Jurisdiction,
    pathogen: Pathogen,
    start: date,
    end: date,
) -> tuple[list[WeeklyObservation], Provenance]:
    """Fetch NWSS wastewater activity for a jurisdiction/pathogen/window.

    Aggregates site-level rows to weekly state-level observations:
    - value = median site_wval across reporting sites
    - derived_level = unique modal site_wval_category (not official)

    Args:
        jurisdiction: Resolved Jurisdiction (maps code to full state name).
        pathogen: Pathogen enum value.
        start: Inclusive start date.
        end: Inclusive end date.

    Returns:
        (observations, provenance) sorted by week_ending ascending.
    """
    pathogen_target = _PATHOGEN_MAP[pathogen]
    full_name = jurisdiction_full_name(jurisdiction.code)

    where = soql_and(
        soql_eq("state_territory", full_name)
        if jurisdiction.type != "national"
        else "",
        soql_eq("pathogen_target", pathogen_target),
        soql_gte("week_end", start.isoformat()),
        soql_lte("week_end", end.isoformat()),
    )
    select = [
        "state_territory",
        "week_end",
        "site",
        "site_wval",
        "site_wval_category",
        "population_served",
    ]

    rows = await query(
        DATASET_ID,
        select=select,
        where=where,
        order="week_end ASC, state_territory ASC, site ASC",
        limit=5000,
    )

    return parse_rows(rows, jurisdiction, pathogen)


def parse_rows(
    rows: list[dict], jurisdiction: Jurisdiction, pathogen: Pathogen
) -> tuple[list[WeeklyObservation], Provenance]:
    """Parse one jurisdiction's rows without network access."""
    full_name = jurisdiction_full_name(jurisdiction.code)
    retrieved_at = datetime.now(timezone.utc)

    # Group rows by week_end
    by_week: dict[date, list[dict]] = {}
    for row in rows:
        raw = row.get("week_end", "")
        try:
            wk = date.fromisoformat(raw[:10])
        except (ValueError, TypeError):
            continue
        by_week.setdefault(wk, []).append(row)

    observations: list[WeeklyObservation] = []
    latest_week: date | None = None
    notes: list[str] = []

    notes.append(
        "Site aggregate is server-derived, not an official CDC "
        "jurisdiction classification."
    )
    notes.append(
        "Population coverage fraction is unknown; two valid sites do not "
        "establish representativeness."
    )
    if pathogen == Pathogen.influenza:
        notes.append("Wastewater measures influenza A (Influenza A virus) only.")

    for wk in sorted(by_week):
        # Use one record per identified site. A duplicated site must not inflate
        # coverage or overweight the median. Conflicting duplicates are excluded.
        grouped: dict[str, list[dict]] = {}
        for row in by_week[wk]:
            if row.get("site"):
                key = f"{row.get('state_territory', '')}:{row['site']}"
                grouped.setdefault(key, []).append(row)
        site_rows = []
        for records in grouped.values():
            signatures = {
                (_parse_float(r.get("site_wval")), r.get("site_wval_category"))
                for r in records
            }
            if len(signatures) == 1:
                site_rows.append(records[0])
            else:
                notes.append("Conflicting duplicate site/week records excluded.")
        site_rows = [
            r for r in site_rows if _parse_float(r.get("site_wval")) is not None
        ]
        wvals = [
            _parse_float(r.get("site_wval"))
            for r in site_rows
            if _parse_float(r.get("site_wval")) is not None
        ]
        categories = [
            r["site_wval_category"] for r in site_rows if r.get("site_wval_category")
        ]
        n_sites = len(site_rows)

        if n_sites < 2:
            value: float | None = None
            if "insufficient wastewater coverage" not in notes:
                notes.append("insufficient wastewater coverage (< 2 sites reporting)")
        else:
            value = statistics.median(wvals) if wvals else None

        obs = WeeklyObservation(
            jurisdiction=jurisdiction.code,
            week_ending=wk,
            value=value,
            unit="wval",
            official_level=None,
            derived_level=_modal_category(categories) if value is not None else None,
            aggregation_method=(
                "median_distinct_valid_sites; category=modal_site_category"
            ),
            coverage={"n_sites": n_sites},
        )
        observations.append(obs)
        if latest_week is None or wk > latest_week:
            latest_week = wk

    if not observations and full_name == jurisdiction_full_name(jurisdiction.code):
        # No rows returned — check if this is a known no-coverage jurisdiction
        if jurisdiction.code == "PR":
            notes.append(
                "No wastewater rows returned for Puerto Rico in the requested "
                "window; coverage cannot be inferred."
            )

    provenance = Provenance(
        dataset_id=DATASET_ID,
        dataset_name=DATASET_NAME,
        url=DATASET_URL,  # type: ignore[arg-type]
        latest_week_ending=latest_week,
        retrieved_at=retrieved_at,
        geography_level="national"
        if jurisdiction.type == "national"
        else "site_aggregate",
        notes=notes,
    )

    return observations, provenance
