"""Source registry — coordinates concurrent fetching across all adapters.

Runs NHSN, NWSS, and NREVSS adapters concurrently. A failed source returns
a SignalUnavailable entry (with error message) instead of crashing the call.
"""

from __future__ import annotations

import asyncio
import logging
from dataclasses import dataclass
from datetime import date

from resp_mcp.models.common import (
    Pathogen,
    Provenance,
    Signal,
    WeeklyObservation,
)
from resp_mcp.reference.jurisdictions import Jurisdiction

logger = logging.getLogger(__name__)


@dataclass
class SignalResult:
    """Successful result from a source adapter."""

    signal: Signal
    pathogen: Pathogen
    observations: list[WeeklyObservation]
    provenance: Provenance


@dataclass
class SignalUnavailable:
    """Failed result from a source adapter — does not crash the registry."""

    signal: Signal
    pathogen: Pathogen
    error: str
    dataset_id: str


FetchResult = SignalResult | SignalUnavailable


async def fetch_all(
    jurisdiction: Jurisdiction,
    pathogen: Pathogen,
    start: date,
    end: date,
) -> list[FetchResult]:
    """Fetch all three signals concurrently for a jurisdiction/pathogen/window.

    Uses asyncio.gather with return_exceptions=True so a failure in one source
    does not cancel the others. Failed sources are returned as SignalUnavailable.

    Args:
        jurisdiction: Resolved Jurisdiction object.
        pathogen: One of Pathogen.influenza / .covid19 / .rsv.
        start: Inclusive start date (week_ending >= start).
        end: Inclusive end date (week_ending <= end).

    Returns:
        List of FetchResult (mix of SignalResult and SignalUnavailable).
    """
    # Import here to avoid circular imports at module load time
    from resp_mcp.sources import nhsn, nrevss, nwss

    adapters = [
        (Signal.hospital_admissions, nhsn.fetch_series),
        (Signal.wastewater, nwss.fetch_series),
        (Signal.test_positivity, nrevss.fetch_series),
    ]

    async def _safe_fetch(signal: Signal, fetch_fn) -> FetchResult:
        try:
            obs, prov = await fetch_fn(jurisdiction, pathogen, start, end)
            return SignalResult(
                signal=signal,
                pathogen=pathogen,
                observations=obs,
                provenance=prov,
            )
        except Exception as exc:  # noqa: BLE001
            logger.warning(
                "Source adapter failed for %s/%s/%s: %s",
                signal.value,
                pathogen.value,
                jurisdiction.code,
                type(exc).__name__,
            )
            # Try to get dataset_id from the adapter module
            try:
                from resp_mcp.sources import nhsn as _nhsn
                from resp_mcp.sources import nrevss as _nrevss
                from resp_mcp.sources import nwss as _nwss

                _map = {
                    Signal.hospital_admissions: _nhsn.DATASET_ID,
                    Signal.wastewater: _nwss.DATASET_ID,
                    Signal.test_positivity: _nrevss.DATASET_ID,
                }
                did = _map.get(signal, "unknown")
            except Exception:
                did = "unknown"
            return SignalUnavailable(
                signal=signal,
                pathogen=pathogen,
                error=f"{signal.value} source unavailable ({type(exc).__name__}).",
                dataset_id=did,
            )

    tasks = [_safe_fetch(signal, fn) for signal, fn in adapters]
    results = await asyncio.gather(*tasks)
    return list(results)
