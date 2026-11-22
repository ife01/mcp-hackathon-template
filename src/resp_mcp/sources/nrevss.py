"""NREVSS test positivity source adapter.

Dataset: seuz-s2cv
  Percent of Tests Positive for Viral Respiratory Pathogens

Key columns (verified Build 0.3):
  week_end, pathogen, percent_test_positivity

Decisions (from docs/DECISIONS.md):
- National only — no state or HHS region breakdown in this dataset.
- For any non-national jurisdiction, returns USA observations with the national
  value and provenance note: "Test positivity data is only available at the
  national level from this source"
- Pathogen values: "Influenza" (A+B combined), "COVID-19", "RSV"
- Most recent week may be incomplete; >= 90% complete two weeks back.
"""

from __future__ import annotations

import logging
import math
from datetime import date, datetime, timezone

from resp_mcp.clients.socrata import query, soql_and, soql_eq, soql_gte, soql_lte
from resp_mcp.models.common import Pathogen, Provenance, WeeklyObservation
from resp_mcp.reference.jurisdictions import Jurisdiction

logger = logging.getLogger(__name__)

DATASET_ID = "seuz-s2cv"
DATASET_NAME = "Percent of Tests Positive for Viral Respiratory Pathogens"
DATASET_URL = f"https://data.cdc.gov/resource/{DATASET_ID}.json"

_PATHOGEN_MAP: dict[Pathogen, str] = {
    Pathogen.influenza: "Influenza",
    Pathogen.covid19: "COVID-19",
    Pathogen.rsv: "RSV",
}


def _parse_float(val) -> float | None:
    if val is None or val == "":
        return None
    try:
        parsed = float(val)
        return parsed if math.isfinite(parsed) and 0 <= parsed <= 100 else None
    except (ValueError, TypeError):
        return None


async def fetch_series(
    jurisdiction: Jurisdiction,
    pathogen: Pathogen,
    start: date,
    end: date,
) -> tuple[list[WeeklyObservation], Provenance]:
    """Fetch NREVSS test positivity for a jurisdiction/pathogen/window.

    Always returns national data — this dataset has no sub-national breakdown.
    For non-national jurisdictions, the observations carry the national value
    with a provenance note.

    Args:
        jurisdiction: Resolved Jurisdiction.
        pathogen: Pathogen enum value.
        start: Inclusive start date.
        end: Inclusive end date.

    Returns:
        (observations, provenance) sorted by week_ending ascending.
    """
    pathogen_label = _PATHOGEN_MAP[pathogen]

    where = soql_and(
        soql_eq("pathogen", pathogen_label),
        soql_gte("week_end", start.isoformat()),
        soql_lte("week_end", end.isoformat()),
    )
    select = ["week_end", "pathogen", "percent_test_positivity"]

    rows = await query(
        DATASET_ID,
        select=select,
        where=where,
        order="week_end ASC",
        limit=200,
    )

    retrieved_at = datetime.now(timezone.utc)
    observations: list[WeeklyObservation] = []
    latest_week: date | None = None

    for row in rows:
        raw = row.get("week_end", "")
        try:
            wk = date.fromisoformat(raw[:10])
        except (ValueError, TypeError):
            logger.warning("NREVSS: invalid source week date")
            continue

        value = _parse_float(row.get("percent_test_positivity"))

        obs = WeeklyObservation(
            jurisdiction="USA",
            week_ending=wk,
            value=value,
            unit="percent_positive",
            official_level=None,
        )
        observations.append(obs)

        if latest_week is None or wk > latest_week:
            latest_week = wk

    notes: list[str] = [
        "Recent weeks may be incomplete or revised; "
        "a two-week lag does not guarantee finalization."
    ]
    if jurisdiction.type != "national":
        notes.append(
            "Test positivity data is only available at the national level "
            f"from this source; shown as national context for "
            f"{jurisdiction.code}, not a state estimate."
        )
    if pathogen == Pathogen.influenza:
        notes.append("Influenza test positivity includes both influenza A and B.")

    provenance = Provenance(
        dataset_id=DATASET_ID,
        dataset_name=DATASET_NAME,
        url=DATASET_URL,  # type: ignore[arg-type]
        latest_week_ending=latest_week,
        retrieved_at=retrieved_at,
        geography_level="national",
        notes=notes,
    )

    return observations, provenance
