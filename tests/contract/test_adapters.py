"""Contract tests for source adapters (fixtures only — no network).

These tests load the JSON fixtures recorded in Build 0.3 and verify that:
- Adapters parse them correctly and return the right shapes.
- Hand-checked values from live data match what the adapter produces.
- Edge cases: NWSS low-coverage, NREVSS national-only caveat, registry partial failure.
"""

from __future__ import annotations

import json
from datetime import date, datetime, timezone
from pathlib import Path
from unittest.mock import AsyncMock, patch

import pytest

from resp_mcp.models.common import Pathogen, Signal
from resp_mcp.reference.jurisdictions import resolve_jurisdiction
from resp_mcp.sources import nhsn, nrevss, nwss
from resp_mcp.sources.registry import SignalResult, SignalUnavailable, fetch_all

FIXTURE_DIR = Path("tests/fixtures")

# ── Fixture loader ────────────────────────────────────────────────────────────


def _load(name: str) -> list[dict]:
    files = sorted(FIXTURE_DIR.glob(f"{name}_*.json"))
    if not files:
        pytest.skip(f"No fixture found matching {name}_*.json")
    return json.loads(files[-1].read_text())


# ── NHSN adapter ──────────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_nhsn_ga_flu_returns_observations():
    ga = resolve_jurisdiction("GA")
    rows = _load("nhsn_ga")

    with patch("resp_mcp.sources.nhsn.query", new_callable=AsyncMock) as mock_q:
        mock_q.return_value = rows
        obs, prov = await nhsn.fetch_series(
            ga,
            Pathogen.influenza,
            date(2026, 10, 1),
            date(2026, 11, 14),
        )

    assert len(obs) > 0
    assert all(o.unit == "admissions_per_100k" for o in obs)
    assert all(o.jurisdiction == "GA" for o in obs)
    assert prov.dataset_id == "vdzy-6i9v"
    assert prov.geography_level == "state"


@pytest.mark.asyncio
async def test_nhsn_ga_flu_hand_checked_value():
    """Spot-check: GA flu admissions on 2026-11-14 = 2.47 per 100k."""
    ga = resolve_jurisdiction("GA")
    rows = _load("nhsn_ga")

    with patch("resp_mcp.sources.nhsn.query", new_callable=AsyncMock) as mock_q:
        mock_q.return_value = rows
        obs, _ = await nhsn.fetch_series(
            ga,
            Pathogen.influenza,
            date(2026, 1, 1),
            date(2026, 11, 14),
        )

    latest = max(obs, key=lambda o: o.week_ending)
    assert latest.week_ending == date(2026, 11, 14)
    assert latest.value == pytest.approx(2.47, abs=0.01)
    assert latest.official_level == "Low"


@pytest.mark.asyncio
async def test_nhsn_usa_national_provenance():
    usa = resolve_jurisdiction("USA")
    rows = _load("nhsn_usa")

    with patch("resp_mcp.sources.nhsn.query", new_callable=AsyncMock) as mock_q:
        mock_q.return_value = rows
        _, prov = await nhsn.fetch_series(
            usa,
            Pathogen.covid19,
            date(2026, 10, 1),
            date(2026, 11, 14),
        )

    assert prov.geography_level == "national"


@pytest.mark.asyncio
async def test_nhsn_coverage_attached():
    ga = resolve_jurisdiction("GA")
    rows = _load("nhsn_ga")

    with patch("resp_mcp.sources.nhsn.query", new_callable=AsyncMock) as mock_q:
        mock_q.return_value = rows
        obs, _ = await nhsn.fetch_series(
            ga,
            Pathogen.influenza,
            date(2026, 10, 1),
            date(2026, 11, 14),
        )

    for o in obs:
        if o.coverage is not None:
            assert "n_hospitals" in o.coverage
            break
    else:
        pytest.fail("No observation had coverage attached")


@pytest.mark.asyncio
async def test_nhsn_empty_rows_returns_empty_list():
    ga = resolve_jurisdiction("GA")

    with patch("resp_mcp.sources.nhsn.query", new_callable=AsyncMock) as mock_q:
        mock_q.return_value = []
        obs, prov = await nhsn.fetch_series(
            ga,
            Pathogen.influenza,
            date(2026, 10, 1),
            date(2026, 11, 14),
        )

    assert obs == []
    assert prov.latest_week_ending is None


# ── NWSS adapter ──────────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_nwss_georgia_flu_aggregates_sites():
    ga = resolve_jurisdiction("GA")
    rows = _load("nwss_georgia")
    # Filter to flu + recent weeks for speed
    flu_rows = [
        r
        for r in rows
        if r.get("pathogen_target") == "Influenza A virus"
        and r.get("week_end", "")[:10] >= "2026-10-01"
    ]

    with patch("resp_mcp.sources.nwss.query", new_callable=AsyncMock) as mock_q:
        mock_q.return_value = flu_rows
        obs, prov = await nwss.fetch_series(
            ga,
            Pathogen.influenza,
            date(2026, 10, 1),
            date(2026, 11, 14),
        )

    assert len(obs) > 0
    assert all(o.unit == "wval" for o in obs)
    assert all(o.coverage is not None for o in obs)
    assert prov.geography_level == "site_aggregate"
    # Influenza note present (case-insensitive)
    assert any("influenza a" in n.lower() for n in prov.notes)


@pytest.mark.asyncio
async def test_nwss_low_coverage_returns_none_value():
    """Single site → value should be None with coverage note."""
    ga = resolve_jurisdiction("GA")
    single_site_rows = [
        {
            "state_territory": "Georgia",
            "week_end": "2026-11-14",
            "site": "ID:999",
            "site_wval": "3.5",
            "site_wval_category": "Low",
            "population_served": "50000",
        }
    ]

    with patch("resp_mcp.sources.nwss.query", new_callable=AsyncMock) as mock_q:
        mock_q.return_value = single_site_rows
        obs, prov = await nwss.fetch_series(
            ga,
            Pathogen.influenza,
            date(2026, 11, 14),
            date(2026, 11, 14),
        )

    assert len(obs) == 1
    assert obs[0].value is None
    assert any("insufficient" in n.lower() for n in prov.notes)


@pytest.mark.asyncio
async def test_nwss_median_calculation():
    """3 sites with wvals 1.0, 2.0, 3.0 → median = 2.0."""
    ga = resolve_jurisdiction("GA")
    three_sites = [
        {
            "state_territory": "Georgia",
            "week_end": "2026-11-14",
            "site": f"ID:{i}",
            "site_wval": str(float(i)),
            "site_wval_category": "Low",
        }
        for i in [1, 2, 3]
    ]

    with patch("resp_mcp.sources.nwss.query", new_callable=AsyncMock) as mock_q:
        mock_q.return_value = three_sites
        obs, _ = await nwss.fetch_series(
            ga,
            Pathogen.covid19,
            date(2026, 11, 14),
            date(2026, 11, 14),
        )

    assert obs[0].value == pytest.approx(2.0)


@pytest.mark.asyncio
async def test_nwss_modal_category():
    """3 Very Low + 1 Low → official_level = Very Low."""
    ga = resolve_jurisdiction("GA")
    rows = [
        {
            "state_territory": "Georgia",
            "week_end": "2026-11-14",
            "site": f"ID:{i}",
            "site_wval": "1.5",
            "site_wval_category": "Very Low",
        }
        for i in range(3)
    ] + [
        {
            "state_territory": "Georgia",
            "week_end": "2026-11-14",
            "site": "ID:99",
            "site_wval": "3.0",
            "site_wval_category": "Low",
        },
    ]

    with patch("resp_mcp.sources.nwss.query", new_callable=AsyncMock) as mock_q:
        mock_q.return_value = rows
        obs, _ = await nwss.fetch_series(
            ga,
            Pathogen.rsv,
            date(2026, 11, 14),
            date(2026, 11, 14),
        )

    assert obs[0].official_level is None
    assert obs[0].derived_level == "Very Low"


@pytest.mark.asyncio
async def test_nwss_pr_no_coverage_note():
    pr = resolve_jurisdiction("PR")

    with patch("resp_mcp.sources.nwss.query", new_callable=AsyncMock) as mock_q:
        mock_q.return_value = []  # PR has no rows
        obs, prov = await nwss.fetch_series(
            pr,
            Pathogen.influenza,
            date(2026, 10, 1),
            date(2026, 11, 14),
        )

    assert obs == []
    assert any("Puerto Rico" in n for n in prov.notes)


# ── NREVSS adapter ────────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_nrevss_national_flu_returns_observations():
    usa = resolve_jurisdiction("USA")
    rows = _load("nrevss_national_positivity")

    # Filter to flu rows for the test window
    flu_rows = [
        r
        for r in rows
        if r.get("pathogen") == "Influenza"
        and r.get("week_end", "")[:10] >= "2026-10-01"
    ]

    with patch("resp_mcp.sources.nrevss.query", new_callable=AsyncMock) as mock_q:
        mock_q.return_value = flu_rows
        obs, prov = await nrevss.fetch_series(
            usa,
            Pathogen.influenza,
            date(2026, 10, 1),
            date(2026, 11, 14),
        )

    assert len(obs) > 0
    assert all(o.unit == "percent_positive" for o in obs)
    assert prov.geography_level == "national"
    assert prov.dataset_id == "seuz-s2cv"


@pytest.mark.asyncio
async def test_nrevss_state_jurisdiction_adds_national_caveat():
    ga = resolve_jurisdiction("GA")
    rows = [
        {
            "week_end": "2026-11-14T00:00:00.000",
            "pathogen": "Influenza",
            "percent_test_positivity": "11.8",
        },
    ]

    with patch("resp_mcp.sources.nrevss.query", new_callable=AsyncMock) as mock_q:
        mock_q.return_value = rows
        obs, prov = await nrevss.fetch_series(
            ga,
            Pathogen.influenza,
            date(2026, 11, 14),
            date(2026, 11, 14),
        )

    assert len(obs) == 1
    assert obs[0].jurisdiction == "USA"
    assert any("national level" in n for n in prov.notes)


@pytest.mark.asyncio
async def test_nrevss_flu_note_about_a_and_b():
    usa = resolve_jurisdiction("USA")
    rows = [
        {
            "week_end": "2026-11-14T00:00:00.000",
            "pathogen": "Influenza",
            "percent_test_positivity": "11.8",
        }
    ]

    with patch("resp_mcp.sources.nrevss.query", new_callable=AsyncMock) as mock_q:
        mock_q.return_value = rows
        _, prov = await nrevss.fetch_series(
            usa,
            Pathogen.influenza,
            date(2026, 11, 14),
            date(2026, 11, 14),
        )

    assert any("influenza A and B" in n for n in prov.notes)


# ── Registry partial failure ──────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_registry_partial_failure_returns_unavailable():
    """NWSS fails → registry returns SignalUnavailable without crashing."""
    ga = resolve_jurisdiction("GA")

    async def good_nhsn(*args, **kwargs):
        return [], nrevss.Provenance(  # just reuse a placeholder
            dataset_id="vdzy-6i9v",
            dataset_name="NHSN",
            url="https://data.cdc.gov/resource/vdzy-6i9v.json",
            latest_week_ending=None,
            retrieved_at=datetime.now(timezone.utc),
            geography_level="state",
        ) if False else (_ for _ in ()).throw(Exception("NWSS down"))

    with (
        patch(
            "resp_mcp.sources.nhsn.fetch_series",
            new_callable=AsyncMock,
            return_value=([], _make_prov("vdzy-6i9v", "state")),
        ),
        patch(
            "resp_mcp.sources.nwss.fetch_series",
            new_callable=AsyncMock,
            side_effect=Exception("NWSS connection failed"),
        ),
        patch(
            "resp_mcp.sources.nrevss.fetch_series",
            new_callable=AsyncMock,
            return_value=([], _make_prov("seuz-s2cv", "national")),
        ),
    ):
        results = await fetch_all(
            ga,
            Pathogen.influenza,
            date(2026, 10, 1),
            date(2026, 11, 14),
        )

    signals = {type(r).__name__ for r in results}
    assert "SignalUnavailable" in signals
    assert "SignalResult" in signals

    unavailable = [r for r in results if isinstance(r, SignalUnavailable)]
    assert any(r.signal == Signal.wastewater for r in unavailable)
    assert any(
        r.dataset_id == "atcp-73re" and "source unavailable" in r.error
        for r in unavailable
    )


def _make_prov(dataset_id: str, geo_level: str):
    from resp_mcp.models.common import Provenance

    return Provenance(
        dataset_id=dataset_id,
        dataset_name="test",
        url=f"https://data.cdc.gov/resource/{dataset_id}.json",
        latest_week_ending=None,
        retrieved_at=datetime.now(timezone.utc),
        geography_level=geo_level,
    )


@pytest.mark.asyncio
async def test_registry_all_succeed_returns_three_signal_results():
    ga = resolve_jurisdiction("GA")
    prov_nhsn = _make_prov("vdzy-6i9v", "state")
    prov_nwss = _make_prov("atcp-73re", "site_aggregate")
    prov_nrevss = _make_prov("seuz-s2cv", "national")

    with (
        patch(
            "resp_mcp.sources.nhsn.fetch_series",
            new_callable=AsyncMock,
            return_value=([], prov_nhsn),
        ),
        patch(
            "resp_mcp.sources.nwss.fetch_series",
            new_callable=AsyncMock,
            return_value=([], prov_nwss),
        ),
        patch(
            "resp_mcp.sources.nrevss.fetch_series",
            new_callable=AsyncMock,
            return_value=([], prov_nrevss),
        ),
    ):
        results = await fetch_all(
            ga,
            Pathogen.influenza,
            date(2026, 10, 1),
            date(2026, 11, 14),
        )

    assert len(results) == 3
    assert all(isinstance(r, SignalResult) for r in results)
