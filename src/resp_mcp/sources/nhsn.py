"""NHSN hospital admissions source adapter.

Dataset: vdzy-6i9v
  Weekly Hospital Respiratory Admission Levels and Rates by Jurisdiction,
  National Healthcare Safety Network (NHSN)

Key columns (verified Build 0.3):
  jurisdiction, weekendingdate,
  totalconfflunewadmper100k, totalconfc19newadmper100k, totalconfrsvnewadmper100k,
  totalconfflunewadm, totalconfc19newadm, totalconfrsvnewadm,
  totalconfflunewadmper100klevel, totalconfc19newadmper100klevel,
  totalconfrsvnewadmper100klevel, totalconfflunewadmhosprep,
  totalconfflunewadmperchosprep
"""

from __future__ import annotations

import logging
import math
from datetime import date, datetime, timezone

from resp_mcp.clients.socrata import query, soql_and, soql_eq, soql_gte, soql_lte
from resp_mcp.models.common import Pathogen, Provenance, WeeklyObservation
from resp_mcp.reference.jurisdictions import Jurisdiction

logger = logging.getLogger(__name__)

DATASET_ID = "vdzy-6i9v"
DATASET_NAME = (
    "Weekly Hospital Respiratory Admission Levels and Rates by Jurisdiction, "
    "National Healthcare Safety Network (NHSN)"
)
DATASET_URL = f"https://data.cdc.gov/resource/{DATASET_ID}.json"

# Column mapping: Pathogen â†’ (rate_col, count_col, level_col)
_COLS: dict[Pathogen, tuple[str, str, str]] = {
    Pathogen.influenza: (
        "totalconfflunewadmper100k",
        "totalconfflunewadm",
        "totalconfflunewadmper100klevel",
    ),
    Pathogen.covid19: (
        "totalconfc19newadmper100k",
        "totalconfc19newadm",
        "totalconfc19newadmper100klevel",
    ),
    Pathogen.rsv: (
        "totalconfrsvnewadmper100k",
        "totalconfrsvnewadm",
        "totalconfrsvnewadmper100klevel",
    ),
}


def _parse_float(val: str | None) -> float | None:
    """Parse a Socrata numeric string to float, returning None on failure."""
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
    """Fetch NHSN hospital admission rates for a jurisdiction/pathogen/window.

    Args:
        jurisdiction: Resolved Jurisdiction (uses jurisdiction.code).
        pathogen: Pathogen enum value.
        start: Inclusive start week_ending date.
        end: Inclusive end week_ending date.

    Returns:
        (observations, provenance) sorted by week_ending ascending.
        observations is an empty list when no data is available.
    """
    rate_col, count_col, level_col = _COLS[pathogen]

    where = soql_and(
        soql_eq("jurisdiction", jurisdiction.code),
        soql_gte("weekendingdate", start.isoformat()),
        soql_lte("weekendingdate", end.isoformat()),
    )
    select = [
        "jurisdiction",
        "weekendingdate",
        rate_col,
        count_col,
        level_col,
        count_col + "hosprep",
        count_col + "perchosprep",
    ]

    rows = await query(
        DATASET_ID,
        select=select,
        where=where,
        order="weekendingdate ASC",
        limit=200,
    )

    return parse_rows(rows, jurisdiction, pathogen)


def parse_rows(
    rows: list[dict], jurisdiction: Jurisdiction, pathogen: Pathogen
) -> tuple[list[WeeklyObservation], Provenance]:
    """Parse one jurisdiction's rows without network access."""
    rate_col, count_col, level_col = _COLS[pathogen]
    retrieved_at = datetime.now(timezone.utc)
    observations: list[WeeklyObservation] = []
    latest_week: date | None = None

    for row in rows:
        raw_date = row.get("weekendingdate", "")
        try:
            week_dt = date.fromisoformat(raw_date[:10])
        except (ValueError, TypeError):
            logger.warning("NHSN: invalid source week date")
            continue

        value = _parse_float(row.get(rate_col))

        # Preserve the requested pathogen's own reporting coverage.
        n_reporting = _parse_float(row.get(count_col + "hosprep"))
        pct_reporting = _parse_float(row.get(count_col + "perchosprep"))
        coverage: dict[str, float | int] | None = None
        if n_reporting is not None:
            coverage = {"n_hospitals": int(n_reporting)}
            if pct_reporting is not None:
                coverage["pct_hospitals"] = pct_reporting

        obs = WeeklyObservation(
            jurisdiction=jurisdiction.code,
            week_ending=week_dt,
            value=value,
            raw_count=_parse_float(row.get(count_col)),
            unit="admissions_per_100k",
            official_level=row.get(level_col) or None,
            coverage=coverage,
        )
        observations.append(obs)

        if latest_week is None or week_dt > latest_week:
            latest_week = week_dt

    notes: list[str] = []
    if latest_week and latest_week.year < 2024:
        notes.append(
            "Data predates the 2024 NHSN mandatory-reporting transition; "
            "season comparisons should note potential coverage differences."
        )

    provenance = Provenance(
        dataset_id=DATASET_ID,
        dataset_name=DATASET_NAME,
        url=DATASET_URL,  # type: ignore[arg-type]
        latest_week_ending=latest_week,
        retrieved_at=retrieved_at,
        geography_level="state" if jurisdiction.type != "national" else "national",
        notes=notes,
    )

    return observations, provenance
