"""Check frozen MCP results and prevent a correct total masking a wrong list."""

import json
from pathlib import Path

import pytest

from eval.replay import Replay
from eval.wxo_review import scan_answer_membership, scan_membership_consistent
from resp_mcp.server import mcp


@pytest.mark.asyncio
@pytest.mark.parametrize("region,limit,total", [(None, 56, 43), (4, 3, 8)])
async def test_scan_presentation_uses_only_returned_rising_rows(region, limit, total):
    from resp_mcp.clients import socrata

    socrata._cache = socrata._Cache()
    arguments = {
        "pathogen": "influenza",
        "signal": "hospital_admissions",
        "as_of": "2026-10-31",
        "limit": limit,
        "hhs_region": region,
    }
    with Replay(Path(__file__).resolve().parents[2] / "eval/snapshot_v2"):
        result = await mcp.call_tool(
            "find_jurisdictions_with_rising_activity", arguments
        )
    data = result.structured_content or json.loads(result.content[0].text)
    assert data["n_rising_total"] == total
    assert data["n_returned"] == min(limit, total)
    assert data["rising_jurisdictions"] == [r["jurisdiction"] for r in data["rising"]]
    assert scan_membership_consistent(data)
    assert scan_answer_membership(data["display_text"], data)
    if region is None:
        assert not scan_answer_membership(
            data["display_text"].replace("FL, LA", "FL, AK, LA"), data
        )
        assert not scan_answer_membership(
            data["display_text"].replace("FL, LA", "LA"), data
        )
    assert "not a CDC trend classification" in data["display_text"]


@pytest.mark.asyncio
async def test_trend_explicitly_attributes_the_heuristic_to_the_application():
    from resp_mcp.clients import socrata

    socrata._cache = socrata._Cache()
    with Replay(Path(__file__).resolve().parents[2] / "eval/snapshot_v2"):
        result = await mcp.call_tool(
            "assess_trend",
            {
                "jurisdiction": "GA",
                "pathogen": "influenza",
                "signal": "hospital_admissions",
                "as_of": "2026-10-31",
            },
        )
    data = result.structured_content or json.loads(result.content[0].text)
    assert data["trend"]["direction"] == "increasing"
    assert "this application's heuristic" in data["trend"]["attribution"]
    assert "not a CDC trend classification" in data["trend"]["attribution"]
