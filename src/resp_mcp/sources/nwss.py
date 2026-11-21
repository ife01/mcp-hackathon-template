"""NWSS wastewater source adapter.

Dataset: atcp-73re
  CDC Wastewater Viral Activity Level for SARS-CoV-2, Influenza A and RSV

Key columns (verified Build 0.3):
  state_territory, week_end, site, population_served, source,
  site_wval, site_wval_category, pathogen_target, date_updated

Decisions (from docs/DECISIONS.md):
- Site-level data aggregated to state level using median site_wval.
- official_level = modal site_wval_category across reporting sites.
- state_territory uses full English names (mapped from 2-letter codes).
- Puerto Rico: zero rows → status insufficient_coverage.
- Fewer than 2 sites → value=None + provenance note.
- Influenza = pathogen_target='Influenza A virus' (A only; note in provenance).
"""

from __future__ import annotations

import logging
import statistics
from collections import Counter
from datetime import date, datetime, timezone

from resp_mcp.clients.socrata import query, soql_and, soql_eq, soql_gte, soql_lte
from resp_mcp.models.common import Pathogen, Provenance, WeeklyObservation
from resp_mcp.reference.jurisdictions import Jurisdiction, jurisdiction_full_name

logger = logging.getLogger(__name__)

DATASET_ID = "atcp-73re"
DATASET_NAME = (
    "CDC Wastewater Viral Activity Level for SARS-CoV-2, Influenza A and RSV"
)
DATASET_URL = f"https://data.cdc.gov/resource/{DATASET_ID}.json"

_PATHOGEN_MAP: dict[Pathogen, str] = {
    Pathogen.influenza: "Influenza A virus",
    Pathogen.covid19: "SARS-CoV-2",
    Pathogen.rsv: "RSV",
}

_LEVEL_ORDER = ["Very Low", "Low", "Medium", "High", "Very High"]


def _modal_category(categories: list[str]) -> str | None:
    """Return the most common category string, or None if list is empty."""
    if not categories:
        return None
    return Counter(categories).most_common(1)[0][0]


def _parse_float(val) -> float | None:
    if val is None or val == "":
        return None
    try:
        return float(val)
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
    - official_level = modal site_wval_category

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
        soql_eq("state_territory", full_name),
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
        order="week_end ASC",
        limit=5000,
    )

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

    if pathogen == Pathogen.influenza:
        notes.append("Wastewater measures influenza A (Influenza A virus) only.")

    for wk in sorted(by_week):
        site_rows = by_week[wk]
        wvals = [
            _parse_float(r.get("site_wval"))
            for r in site_rows
            if _parse_float(r.get("site_wval")) is not None
        ]
        categories = [
            r["site_wval_category"]
            for r in site_rows
            if r.get("site_wval_category")
        ]
        n_sites = len(site_rows)

        if n_sites < 2:
            value: float | None = None
            if "insufficient wastewater coverage" not in notes:
                notes.append(
                    "insufficient wastewater coverage (< 2 sites reporting)"
                )
        else:
            value = statistics.median(wvals) if wvals else None

        obs = WeeklyObservation(
            jurisdiction=jurisdiction.code,
            week_ending=wk,
            value=value,
            unit="wval",
            official_level=_modal_category(categories),
            coverage={"n_sites": n_sites},
        )
        observations.append(obs)
        if latest_week is None or wk > latest_week:
            latest_week = wk

    if not observations and full_name == jurisdiction_full_name(jurisdiction.code):
        # No rows returned — check if this is a known no-coverage jurisdiction
        if jurisdiction.code == "PR":
            notes.append(
                "No wastewater surveillance sites in Puerto Rico."
            )

    provenance = Provenance(
        dataset_id=DATASET_ID,
        dataset_name=DATASET_NAME,
        url=DATASET_URL,  # type: ignore[arg-type]
        latest_week_ending=latest_week,
        retrieved_at=retrieved_at,
        geography_level="site_aggregate",
        notes=notes,
    )

    return observations, provenance
