"""Independent examples for misleading geography, missingness, and history."""

import asyncio
import json
from datetime import date, timedelta
from unittest.mock import AsyncMock, patch

import pytest

from resp_mcp.analytics.seasons import compare_to_prior_seasons
from resp_mcp.analytics.trend import classify_trend
from resp_mcp.models.common import Pathogen, Signal, WeeklyObservation
from resp_mcp.reference.epiweeks import week_ending
from resp_mcp.reference.jurisdictions import resolve_jurisdiction
from resp_mcp.server import mcp
from resp_mcp.sources import nhsn, nrevss, nwss
from resp_mcp.sources.bulk import fetch_many


@pytest.mark.asyncio
async def test_query_total_deadline_is_actionable(monkeypatch):
    from resp_mcp.clients import socrata
    from resp_mcp.config import settings

    async def slow(*args, **kwargs):
        await asyncio.sleep(0.05)

    monkeypatch.setattr(settings, "http_total_timeout_seconds", 0.001)
    monkeypatch.setattr(socrata, "_query_impl", slow)
    with pytest.raises(socrata.UpstreamUnavailable, match="deadline exceeded"):
        await socrata.query("vdzy-6i9v")


@pytest.mark.asyncio
async def test_row_cap_never_returns_partial_data(monkeypatch):
    import httpx
    import respx

    from resp_mcp.clients import socrata

    monkeypatch.setattr(socrata, "_MAX_ROWS", 2)
    monkeypatch.setattr(socrata, "_cache", socrata._Cache())
    with respx.mock(assert_all_mocked=True) as router:
        router.get("https://data.cdc.gov/resource/vdzy-6i9v.json").mock(
            return_value=httpx.Response(200, json=[{}, {}])
        )
        with pytest.raises(socrata.UpstreamUnavailable, match="row safety cap"):
            await socrata.query("vdzy-6i9v", limit=2)


def test_methods_resource_matches_documentation():
    from pathlib import Path

    from resp_mcp.resources.methods import _METHODS_TEXT

    root = Path(__file__).resolve().parents[2]
    assert _METHODS_TEXT == (root / "docs/METHODS.md").read_text(encoding="utf-8")


def test_stale_trend_withheld_relative_to_cutoff():
    result = classify_trend(
        observations([1, 1, 2, 2]),
        Signal.hospital_admissions,
        reference_date=date(2026, 12, 1),
    )
    assert result.direction == "insufficient_data"


@pytest.mark.asyncio
async def test_scan_partial_and_unavailable_counts_are_distinct():
    from resp_mcp.models.tool_io import ScanInput
    from resp_mcp.tools.scan import _summarize

    jurisdictions = [resolve_jurisdiction(c) for c in ("GA", "CA", "TX")]
    prov = nhsn.parse_rows([], jurisdictions[0], Pathogen.influenza)[1]
    output = _summarize(
        ScanInput(pathogen="influenza", signal="hospital_admissions"),
        jurisdictions,
        {"GA": (observations([1, 1, 2, 2]), prov), "CA": ([], prov)},
        date(2026, 10, 1),
        date(2026, 10, 31),
    )
    assert output["status"] == "partial"
    assert output["n_assessed"] == 1
    assert output["n_insufficient_data"] == 1
    assert output["n_unavailable"] == 1


def test_nearest_prior_week_returns_actual_date_and_skips_null_neighbour():
    from resp_mcp.reference.epiweeks import same_week_prior_seasons

    ref = date(2026, 10, 31)
    target = same_week_prior_seasons(ref, 1)[0]
    prior = observations([None, None, 7], start=target - timedelta(weeks=1))
    result = compare_to_prior_seasons(prior + observations([5], start=ref), ref, 1)
    assert result.prior[0].week_ending == target + timedelta(weeks=1)
    assert result.prior[0].value == 7


def test_53rd_week_does_not_cross_into_next_prior_season():
    from resp_mcp.reference.epiweeks import same_week_prior_seasons, season_of

    ref = week_ending(2021, 26)  # 2020-21 has 53 season weeks
    previous = same_week_prior_seasons(ref, 1)[0]
    assert season_of(previous) == "2019-20"


def test_missing_admission_counts_are_disclosed():
    result = classify_trend(observations([1, 1, 2, 2]), Signal.hospital_admissions)
    assert any("guard could not be assessed" in note for note in result.notes)


@pytest.mark.asyncio
async def test_snapshot_national_context_cannot_create_local_agreement():
    from datetime import datetime, timezone

    from resp_mcp.models.common import Provenance

    obs = observations([1, 1, 2, 2])
    local = Provenance(
        dataset_id="vdzy-6i9v",
        dataset_name="NHSN",
        url="https://data.cdc.gov/",
        latest_week_ending=date(2026, 10, 31),
        retrieved_at=datetime.now(timezone.utc),
        geography_level="state",
    )
    national = local.model_copy(
        update={"dataset_id": "seuz-s2cv", "geography_level": "national"}
    )
    with (
        patch.object(nhsn, "fetch_series", AsyncMock(return_value=(obs, local))),
        patch.object(nwss, "fetch_series", AsyncMock(return_value=([], local))),
        patch.object(nrevss, "fetch_series", AsyncMock(return_value=(obs, national))),
    ):
        result = await call(
            "get_respiratory_snapshot",
            jurisdiction="GA",
            pathogens=["flu"],
            as_of="2026-10-31",
        )
    assert result["pathogens"][0]["concordance_pattern"] == "insufficient_data"
    assert result["pathogens"][0]["signals"][2]["role"] == "national_context"


def observations(values, *, start=date(2026, 10, 10), count=None):
    return [
        WeeklyObservation(
            jurisdiction="GA",
            week_ending=start + timedelta(weeks=i),
            value=value,
            unit="admissions_per_100k",
            raw_count=count,
        )
        for i, value in enumerate(values)
    ]


async def call(name, **kwargs):
    result = await mcp.call_tool(name, kwargs)
    return json.loads(result.content[0].text)


def test_no_prior_values_cannot_rank_first():
    result = compare_to_prior_seasons(observations([5]), date(2026, 10, 10))
    assert result.rank_vs_prior is None
    assert result.n_prior_compared == 0


def test_complete_season_peak_uses_all_weeks_not_aligned_week():
    first, last = week_ending(2025, 27), week_ending(2026, 26)
    previous = observations([2] * ((last - first).days // 7 + 1), start=first)
    previous[30].value = 20
    result = compare_to_prior_seasons(
        previous + observations([5], start=date(2026, 10, 10)), date(2026, 10, 10), 1
    )
    assert result.pct_of_prior_peak == 25
    assert result.prior_season_peaks == {"2025-26": 20}


def test_partial_season_cannot_supply_peak():
    result = compare_to_prior_seasons(
        observations([5]) + observations([10], start=date(2025, 10, 11)),
        date(2026, 10, 10),
        1,
    )
    assert result.rank_vs_prior == 2
    assert result.pct_of_prior_peak is None


def test_gaps_cannot_be_reported_as_four_week_trend():
    obs = observations([1, 1, 2, 2])
    obs[0].week_ending -= timedelta(weeks=4)
    assert (
        classify_trend(obs, Signal.hospital_admissions).direction == "insufficient_data"
    )


def test_trend_window_is_four_and_missing_endpoint_is_not_backdated():
    assert (
        classify_trend(observations([1] * 6), Signal.hospital_admissions).window_weeks
        == 4
    )
    assert (
        classify_trend(
            observations([1, 1, 2, 2, None]), Signal.hospital_admissions
        ).direction
        == "insufficient_data"
    )


def test_small_count_guard_applies_without_explicit_counts_argument():
    assert (
        classify_trend(
            observations([1, 1, 2, 2], count=2), Signal.hospital_admissions
        ).direction
        == "insufficient_data"
    )


def test_small_count_guard_requires_both_window_means_low():
    result = classify_trend(
        observations([1, 1, 2, 2]), Signal.hospital_admissions, counts=[1, 1, 12, 12]
    )
    assert result.direction == "increasing"


@pytest.mark.asyncio
async def test_nhsn_counts_survive_adapter():
    with patch.object(
        nhsn,
        "query",
        AsyncMock(
            return_value=[
                {
                    "weekendingdate": "2026-10-31",
                    "totalconfflunewadmper100k": "1.2",
                    "totalconfflunewadm": "4",
                }
            ]
        ),
    ):
        obs, _ = await nhsn.fetch_series(
            resolve_jurisdiction("GA"),
            Pathogen.influenza,
            date(2026, 10, 1),
            date(2026, 10, 31),
        )
    assert obs[0].raw_count == 4


@pytest.mark.asyncio
async def test_national_context_keeps_national_geography():
    with patch.object(
        nrevss,
        "query",
        AsyncMock(
            return_value=[{"week_end": "2026-10-31", "percent_test_positivity": "5"}]
        ),
    ):
        obs, prov = await nrevss.fetch_series(
            resolve_jurisdiction("GA"),
            Pathogen.influenza,
            date(2026, 10, 1),
            date(2026, 10, 31),
        )
    assert obs[0].jurisdiction == "USA"
    assert prov.geography_level == "national"


@pytest.mark.asyncio
async def test_duplicate_and_null_sites_cannot_satisfy_coverage():
    row = {
        "week_end": "2026-10-31",
        "site": "A",
        "site_wval": "2",
        "site_wval_category": "Low",
    }
    with patch.object(
        nwss,
        "query",
        AsyncMock(return_value=[row, row, {**row, "site": "B", "site_wval": None}]),
    ):
        obs, _ = await nwss.fetch_series(
            resolve_jurisdiction("GA"),
            Pathogen.influenza,
            date(2026, 10, 1),
            date(2026, 10, 31),
        )
    assert obs[0].coverage["n_sites"] == 1
    assert obs[0].value is None
    assert obs[0].official_level is None


@pytest.mark.asyncio
async def test_scan_rejects_national_positivity_without_querying():
    with patch("resp_mcp.tools.scan.fetch_many", AsyncMock()) as fetch:
        result = await call(
            "find_jurisdictions_with_rising_activity",
            pathogen="influenza",
            signal="test_positivity",
        )
    assert result["error"] == "unsupported_geography"
    fetch.assert_not_called()


@pytest.mark.asyncio
async def test_failed_scan_does_not_claim_zero_rising():
    with patch(
        "resp_mcp.tools.scan.fetch_many",
        AsyncMock(side_effect=RuntimeError("secret body")),
    ):
        result = await call(
            "find_jurisdictions_with_rising_activity",
            pathogen="influenza",
            signal="hospital_admissions",
        )
    assert "error" in result
    assert "Found 0" not in json.dumps(result)
    assert "secret body" not in json.dumps(result)


@pytest.mark.asyncio
async def test_empty_scan_is_insufficient_not_stable():
    async def empty(jurs, pathogen, signal, start, end):
        return {j.code: nhsn.parse_rows([], j, pathogen) for j in jurs}

    with patch("resp_mcp.tools.scan.fetch_many", side_effect=empty):
        result = await call(
            "find_jurisdictions_with_rising_activity",
            pathogen="influenza",
            signal="hospital_admissions",
        )
    assert result["status"] == "insufficient_data"
    assert result["n_assessed"] == 0
    assert result["n_insufficient_data"] == 51


@pytest.mark.asyncio
async def test_bulk_scan_groups_one_source_query():
    rows = [
        {
            "jurisdiction": code,
            "weekendingdate": "2026-10-31",
            "totalconfflunewadmper100k": str(value),
        }
        for code, value in [("GA", 1), ("CA", 5)]
    ]
    with patch("resp_mcp.sources.bulk.query", AsyncMock(return_value=rows)) as query:
        result = await fetch_many(
            [resolve_jurisdiction(c) for c in ["GA", "CA"]],
            Pathogen.influenza,
            Signal.hospital_admissions,
            date(2026, 10, 1),
            date(2026, 10, 31),
        )
    query.assert_awaited_once()
    assert result["GA"][0][0].value == 1
    assert result["CA"][0][0].value == 5


@pytest.mark.asyncio
async def test_all_snapshot_sources_down_returns_error():
    with (
        patch.object(nhsn, "fetch_series", AsyncMock(side_effect=RuntimeError())),
        patch.object(nwss, "fetch_series", AsyncMock(side_effect=RuntimeError())),
        patch.object(nrevss, "fetch_series", AsyncMock(side_effect=RuntimeError())),
    ):
        result = await call(
            "get_respiratory_snapshot", jurisdiction="GA", pathogens=["flu"]
        )
    assert result["error"] == "upstream_unavailable"
    assert len(result["dataset_ids"]) == 3


@pytest.mark.asyncio
async def test_empty_snapshot_signals_not_ok():
    with (
        patch.object(nhsn, "query", AsyncMock(return_value=[])),
        patch.object(nwss, "query", AsyncMock(return_value=[])),
        patch.object(nrevss, "query", AsyncMock(return_value=[])),
    ):
        result = await call(
            "get_respiratory_snapshot", jurisdiction="GA", pathogens=["flu"]
        )
    assert all(
        s["status"] == "insufficient_data" for s in result["pathogens"][0]["signals"]
    )


@pytest.mark.asyncio
async def test_actual_tool_schema_exposes_constraints():
    tools = {t.name: t for t in await mcp.list_tools()}
    props = tools["assess_trend"].parameters["properties"]
    assert props["jurisdiction"]["maxLength"] == 64
    assert props["lookback_weeks"]["maximum"] == 52
    assert "hospital_admissions" in props["signal"]["description"]


@pytest.mark.parametrize("source", [nhsn, nwss, nrevss])
@pytest.mark.parametrize("value", ["NaN", "Infinity", "-1"])
def test_invalid_source_numbers_are_missing(source, value):
    assert source._parse_float(value) is None


def test_positivity_above_100_is_missing():
    assert nrevss._parse_float("100.1") is None


def test_wastewater_mode_ties_are_not_arbitrarily_labeled():
    assert nwss._modal_category(["Low", "High"]) is None


def test_scan_uses_published_moderate_level():
    from resp_mcp.models.tool_io import ScanInput
    from resp_mcp.tools.scan import _summarize

    jur = resolve_jurisdiction("GA")
    obs = observations([1, 1, 2, 2])
    obs[-1].official_level = "Moderate"
    prov = nhsn.parse_rows([], jur, Pathogen.influenza)[1]
    result = _summarize(
        ScanInput(
            pathogen="influenza", signal="hospital_admissions", min_level="Moderate"
        ),
        [jur],
        {"GA": (obs, prov)},
        date(2026, 10, 1),
        date(2026, 10, 31),
    )
    assert result["n_rising_total"] == 1
