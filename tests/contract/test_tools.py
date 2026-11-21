"""Contract tests for all four MCP tools (fixtures only — no network).

Tests call tool functions directly via the FastMCP instance using
mocked source adapters, verifying I/O shapes and key values.
"""

from __future__ import annotations

import json
from datetime import date, datetime, timezone
from pathlib import Path
from unittest.mock import AsyncMock, patch

import pytest

from resp_mcp.models.common import Provenance, Signal, WeeklyObservation
from resp_mcp.server import mcp

FIXTURE_DIR = Path("tests/fixtures")


def _result_to_dict(result) -> dict:
    """Extract the JSON dict from a FastMCP ToolResult."""
    # FastMCP ToolResult has .content list of TextContent/etc.
    # Try .content[0].text first; fall back to str()
    if hasattr(result, "content") and result.content:
        item = result.content[0]
        text = item.text if hasattr(item, "text") else str(item)
    elif hasattr(result, "structured_content") and result.structured_content:
        return result.structured_content
    else:
        text = str(result)
    return json.loads(text)


# ── Helpers ───────────────────────────────────────────────────────────────────


def _load(name: str) -> list[dict]:
    files = sorted(FIXTURE_DIR.glob(f"{name}_*.json"))
    if not files:
        pytest.skip(f"No fixture found matching {name}_*.json")
    return json.loads(files[-1].read_text())


def _prov(dataset_id: str, geo: str, week: date | None = None) -> Provenance:
    return Provenance(
        dataset_id=dataset_id,
        dataset_name="test",
        url=f"https://data.cdc.gov/resource/{dataset_id}.json",  # type: ignore[arg-type]
        latest_week_ending=week,
        retrieved_at=datetime.now(timezone.utc),
        geography_level=geo,
        notes=[],
    )


def _obs(value: float, week: date, signal: Signal) -> list[WeeklyObservation]:
    """Return 8 synthetic weekly observations with a clear increasing trend."""
    unit = {
        Signal.hospital_admissions: "admissions_per_100k",
        Signal.wastewater: "wval",
        Signal.test_positivity: "percent_positive",
    }[signal]
    obs = []
    for i in range(8):
        obs.append(WeeklyObservation(
            jurisdiction="GA",
            week_ending=date.fromordinal(week.toordinal() - (7 - i) * 7),
            value=round(value * (0.8 + 0.05 * i), 2),
            unit=unit,
            official_level="Low" if i < 4 else "Medium",
        ))
    return obs


# ── Tool 1: get_respiratory_snapshot ─────────────────────────────────────────


@pytest.mark.asyncio
async def test_snapshot_returns_dict_with_jurisdiction():
    ga_obs = _obs(2.5, date(2026, 11, 14), Signal.hospital_admissions)
    prov = _prov("vdzy-6i9v", "state", date(2026, 11, 14))

    with (
        patch("resp_mcp.sources.nhsn.fetch_series", new_callable=AsyncMock,
              return_value=(ga_obs, prov)),
        patch("resp_mcp.sources.nwss.fetch_series", new_callable=AsyncMock,
              return_value=([], _prov("atcp-73re", "site_aggregate"))),
        patch("resp_mcp.sources.nrevss.fetch_series", new_callable=AsyncMock,
              return_value=([], _prov("seuz-s2cv", "national"))),
    ):
        result = await mcp.call_tool("get_respiratory_snapshot", {
            "jurisdiction": "GA",
            "pathogens": ["influenza"],
        })

    # FastMCP returns list of content items; get the text
    data = _result_to_dict(result)

    assert data["jurisdiction"] == "GA"
    assert len(data["pathogens"]) == 1
    assert data["pathogens"][0]["pathogen"] == "influenza"


@pytest.mark.asyncio
async def test_snapshot_pr_returns_ok():
    """Puerto Rico: NWSS returns empty (zero sites) — should still return ok."""
    obs = _obs(1.0, date(2026, 11, 14), Signal.hospital_admissions)
    prov = _prov("vdzy-6i9v", "state", date(2026, 11, 14))
    nwss_prov = _prov("atcp-73re", "site_aggregate")
    nwss_prov.notes.append("No wastewater surveillance sites in Puerto Rico.")

    with (
        patch("resp_mcp.sources.nhsn.fetch_series", new_callable=AsyncMock,
              return_value=(obs, prov)),
        patch("resp_mcp.sources.nwss.fetch_series", new_callable=AsyncMock,
              return_value=([], nwss_prov)),
        patch("resp_mcp.sources.nrevss.fetch_series", new_callable=AsyncMock,
              return_value=([], _prov("seuz-s2cv", "national"))),
    ):
        result = await mcp.call_tool("get_respiratory_snapshot", {
            "jurisdiction": "PR",
            "pathogens": ["influenza"],
        })

    data = _result_to_dict(result)

    assert data["jurisdiction"] == "PR"


@pytest.mark.asyncio
async def test_snapshot_usa_national():
    obs = _obs(1.5, date(2026, 11, 14), Signal.hospital_admissions)
    obs_national = [o.model_copy(update={"jurisdiction": "USA"}) for o in obs]
    prov = _prov("vdzy-6i9v", "national", date(2026, 11, 14))

    with (
        patch("resp_mcp.sources.nhsn.fetch_series", new_callable=AsyncMock,
              return_value=(obs_national, prov)),
        patch("resp_mcp.sources.nwss.fetch_series", new_callable=AsyncMock,
              return_value=([], _prov("atcp-73re", "site_aggregate"))),
        patch("resp_mcp.sources.nrevss.fetch_series", new_callable=AsyncMock,
              return_value=([], _prov("seuz-s2cv", "national"))),
    ):
        result = await mcp.call_tool("get_respiratory_snapshot", {
            "jurisdiction": "USA",
            "pathogens": ["influenza"],
        })

    data = _result_to_dict(result)

    assert data["jurisdiction"] == "USA"


@pytest.mark.asyncio
async def test_snapshot_as_of_filters_data():
    obs = _obs(2.0, date(2026, 11, 14), Signal.hospital_admissions)
    prov = _prov("vdzy-6i9v", "state", date(2026, 11, 14))

    with (
        patch("resp_mcp.sources.nhsn.fetch_series", new_callable=AsyncMock,
              return_value=(obs, prov)),
        patch("resp_mcp.sources.nwss.fetch_series", new_callable=AsyncMock,
              return_value=([], _prov("atcp-73re", "site_aggregate"))),
        patch("resp_mcp.sources.nrevss.fetch_series", new_callable=AsyncMock,
              return_value=([], _prov("seuz-s2cv", "national"))),
    ):
        result = await mcp.call_tool("get_respiratory_snapshot", {
            "jurisdiction": "GA",
            "pathogens": ["influenza"],
            "as_of": "2026-10-31",
        })

    data = _result_to_dict(result)

    # Result should still return OK — just filtered data
    assert data["jurisdiction"] == "GA"


# ── Tool 2: assess_trend ─────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_trend_returns_series_and_direction():
    obs = _obs(2.5, date(2026, 11, 14), Signal.hospital_admissions)
    prov = _prov("vdzy-6i9v", "state", date(2026, 11, 14))

    with patch("resp_mcp.sources.nhsn.fetch_series", new_callable=AsyncMock,
               return_value=(obs, prov)):
        result = await mcp.call_tool("assess_trend", {
            "jurisdiction": "GA",
            "pathogen": "influenza",
            "signal": "hospital_admissions",
        })

    data = _result_to_dict(result)

    assert data["jurisdiction"] == "GA"
    assert data["pathogen"] == "influenza"
    assert data["signal"] == "hospital_admissions"
    assert len(data["series"]) > 0
    assert "direction" in data["trend"]
    assert data["trend"]["basis"] == "server_heuristic"


@pytest.mark.asyncio
async def test_trend_flu_alias():
    obs = _obs(2.5, date(2026, 11, 14), Signal.hospital_admissions)
    prov = _prov("vdzy-6i9v", "state", date(2026, 11, 14))

    with patch("resp_mcp.sources.nhsn.fetch_series", new_callable=AsyncMock,
               return_value=(obs, prov)):
        # 'flu' alias should resolve to 'influenza'
        result = await mcp.call_tool("assess_trend", {
            "jurisdiction": "GA",
            "pathogen": "flu",
            "signal": "hospital_admissions",
        })

    data = _result_to_dict(result)

    assert data["pathogen"] == "influenza"


@pytest.mark.asyncio
async def test_trend_provenance_attached():
    obs = _obs(2.5, date(2026, 11, 14), Signal.hospital_admissions)
    prov = _prov("vdzy-6i9v", "state", date(2026, 11, 14))

    with patch("resp_mcp.sources.nhsn.fetch_series", new_callable=AsyncMock,
               return_value=(obs, prov)):
        result = await mcp.call_tool("assess_trend", {
            "jurisdiction": "GA",
            "pathogen": "influenza",
            "signal": "hospital_admissions",
        })

    data = _result_to_dict(result)

    assert "provenance" in data
    assert data["provenance"]["dataset_id"] == "vdzy-6i9v"


# ── Tool 3: compare_to_prior_seasons ─────────────────────────────────────────


@pytest.mark.asyncio
async def test_season_returns_comparison():
    prov = _prov("vdzy-6i9v", "state", date(2026, 11, 14))

    with patch("resp_mcp.sources.nhsn.fetch_series", new_callable=AsyncMock) as mock:
        mock.return_value = ([], prov)
        # (Empty series → comparison with no prior data, still a valid response)
        result = await mcp.call_tool("compare_to_prior_seasons", {
            "jurisdiction": "GA",
            "pathogen": "influenza",
            "signal": "hospital_admissions",
            "prior_seasons": 2,
        })

    data = _result_to_dict(result)

    assert data["jurisdiction"] == "GA"
    assert "comparison" in data
    assert "current_season" in data["comparison"]


# ── Tool 4: find_jurisdictions_with_rising_activity ──────────────────────────


@pytest.mark.asyncio
async def test_scan_returns_scan_output():
    # Mock all state fetches to return a consistent set of data
    obs = _obs(2.5, date(2026, 11, 14), Signal.hospital_admissions)
    prov = _prov("vdzy-6i9v", "state", date(2026, 11, 14))

    with patch("resp_mcp.sources.nhsn.fetch_series", new_callable=AsyncMock,
               return_value=(obs, prov)):
        result = await mcp.call_tool("find_jurisdictions_with_rising_activity", {
            "pathogen": "influenza",
            "signal": "hospital_admissions",
            "hhs_region": 4,  # Just region 4 to keep the test fast
            "limit": 5,
        })

    data = _result_to_dict(result)

    assert data["pathogen"] == "influenza"
    assert data["signal"] == "hospital_admissions"
    assert "rising" in data
    assert "n_jurisdictions_scanned" in data
    assert isinstance(data["rising"], list)


@pytest.mark.asyncio
async def test_scan_all_stable_returns_empty_rising():
    # Flat (stable) data → no rising jurisdictions
    # Constant value across all 8 weeks → trend is stable → rising = []
    obs = [WeeklyObservation(
        jurisdiction="GA",
        week_ending=date.fromordinal(date(2026, 11, 14).toordinal() - i * 7),
        value=2.0,  # constant → stable
        unit="admissions_per_100k",
    ) for i in range(8)]
    prov = _prov("vdzy-6i9v", "state", date(2026, 11, 14))

    stable_fetch = AsyncMock(return_value=(obs, prov))
    # Patch through the scan module's _ADAPTERS dict, which holds direct refs
    import resp_mcp.tools.scan as _scan_mod
    from resp_mcp.models.common import Signal as _Signal
    with patch.dict(_scan_mod._ADAPTERS, {_Signal.hospital_admissions: stable_fetch}):
        result = await mcp.call_tool("find_jurisdictions_with_rising_activity", {
            "pathogen": "influenza",
            "signal": "hospital_admissions",
            "hhs_region": 4,
        })

    data = _result_to_dict(result)
    assert data["rising"] == []
