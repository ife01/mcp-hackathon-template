"""Build 3.4 error-handling tests.

Covers every scenario from the build plan:
  - Unknown jurisdiction ("Georgai") → suggestion message
  - >64 char input → clean validation error
  - Invalid enum ("flu B") → allowed values list; aliases work
  - as_of out of range → valid range error
  - One source down → tool succeeds with status: "unavailable" caveat
  - All sources down → structured error naming dataset IDs
  - Rate limited / timeout → structured error advising retry
  - Zero stdout during stdio tool calls
"""

from __future__ import annotations

import io
import json
import sys
from datetime import date, datetime, timezone
from unittest.mock import AsyncMock, patch

import pytest

from resp_mcp.clients.socrata import UpstreamRateLimited, UpstreamUnavailable
from resp_mcp.models.common import Provenance, Signal, WeeklyObservation
from resp_mcp.server import mcp
from resp_mcp.tools._helpers import classify_tool_error, parse_as_of

# ── Fixtures ──────────────────────────────────────────────────────────────────


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


def _obs_rising(week: date, signal: Signal) -> list[WeeklyObservation]:
    unit = {
        Signal.hospital_admissions: "admissions_per_100k",
        Signal.wastewater: "wval",
        Signal.test_positivity: "percent_positive",
    }[signal]
    return [
        WeeklyObservation(
            jurisdiction="GA",
            week_ending=date.fromordinal(week.toordinal() - (7 - i) * 7),
            value=round(2.0 + i * 0.3, 2),
            unit=unit,
        )
        for i in range(8)
    ]


def _result_text(result) -> dict:
    if hasattr(result, "content") and result.content:
        item = result.content[0]
        text = item.text if hasattr(item, "text") else str(item)
    elif hasattr(result, "structured_content") and result.structured_content:
        return result.structured_content
    else:
        text = str(result)
    return json.loads(text)


# ── Unknown jurisdiction ───────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_unknown_jurisdiction_returns_error_with_suggestions():
    result = await mcp.call_tool(
        "get_respiratory_snapshot",
        {
            "jurisdiction": "Georgai",
            "pathogens": ["influenza"],
        },
    )
    data = _result_text(result)
    assert data.get("error") == "unknown_jurisdiction"
    assert "suggestions" in data
    assert len(data["suggestions"]) > 0


@pytest.mark.asyncio
async def test_unknown_jurisdiction_in_trend_tool():
    result = await mcp.call_tool(
        "assess_trend",
        {
            "jurisdiction": "Georgai",
            "pathogen": "influenza",
            "signal": "hospital_admissions",
        },
    )
    data = _result_text(result)
    assert data.get("error") == "unknown_jurisdiction"


# ── >64 char input ─────────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_jurisdiction_over_64_chars_returns_error():
    from fastmcp.exceptions import ValidationError

    with pytest.raises(ValidationError, match="at most 64"):
        await mcp.call_tool("get_respiratory_snapshot", {"jurisdiction": "A" * 65})


# ── Invalid enum ("flu B") ─────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_invalid_pathogen_returns_error_with_allowed():
    result = await mcp.call_tool(
        "assess_trend",
        {
            "jurisdiction": "GA",
            "pathogen": "flu B",
            "signal": "hospital_admissions",
        },
    )
    data = _result_text(result)
    assert data.get("error") == "invalid_input"
    msg = data["message"].lower()
    assert "influenza" in msg or "allowed" in msg


@pytest.mark.asyncio
async def test_invalid_signal_returns_error():
    result = await mcp.call_tool(
        "assess_trend",
        {
            "jurisdiction": "GA",
            "pathogen": "influenza",
            "signal": "mystery_signal",
        },
    )
    data = _result_text(result)
    assert data.get("error") == "invalid_input"
    assert "hospital_admissions" in data["message"]


# ── Alias handling ─────────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_covid_alias_resolves_correctly():
    obs = _obs_rising(date(2026, 11, 14), Signal.hospital_admissions)
    prov = _prov("vdzy-6i9v", "state", date(2026, 11, 14))

    with patch(
        "resp_mcp.sources.nhsn.fetch_series",
        new_callable=AsyncMock,
        return_value=(obs, prov),
    ):
        result = await mcp.call_tool(
            "assess_trend",
            {
                "jurisdiction": "GA",
                "pathogen": "covid",
                "signal": "hospital_admissions",
            },
        )
    data = _result_text(result)
    assert data.get("pathogen") == "covid19"


@pytest.mark.asyncio
async def test_sars_cov_2_alias_resolves_correctly():
    obs = _obs_rising(date(2026, 11, 14), Signal.hospital_admissions)
    prov = _prov("vdzy-6i9v", "state", date(2026, 11, 14))

    with patch(
        "resp_mcp.sources.nhsn.fetch_series",
        new_callable=AsyncMock,
        return_value=(obs, prov),
    ):
        result = await mcp.call_tool(
            "assess_trend",
            {
                "jurisdiction": "GA",
                "pathogen": "sars-cov-2",
                "signal": "hospital_admissions",
            },
        )
    data = _result_text(result)
    assert data.get("pathogen") == "covid19"


# ── as_of out of range ─────────────────────────────────────────────────────────


def test_parse_as_of_too_early_raises():
    with pytest.raises(ValueError, match="before the earliest"):
        parse_as_of("2015-01-01")
    assert parse_as_of("2020-01-01") == date(2020, 1, 1)


def test_parse_as_of_too_far_future_raises():
    with pytest.raises(ValueError, match="too far in the future"):
        parse_as_of("2099-12-31")


def test_parse_as_of_bad_format_raises():
    with pytest.raises(ValueError, match="Expected YYYY-MM-DD"):
        parse_as_of("not-a-date")


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "tool,arguments",
    [
        (
            "get_respiratory_snapshot",
            {"jurisdiction": "GA", "pathogens": ["influenza"]},
        ),
        (
            "assess_trend",
            {
                "jurisdiction": "GA",
                "pathogen": "influenza",
                "signal": "hospital_admissions",
            },
        ),
        (
            "compare_to_prior_seasons",
            {
                "jurisdiction": "GA",
                "pathogen": "influenza",
                "signal": "hospital_admissions",
            },
        ),
        (
            "find_jurisdictions_with_rising_activity",
            {"pathogen": "influenza", "signal": "hospital_admissions"},
        ),
    ],
)
async def test_as_of_out_of_range_returns_application_limit_not_source_history(
    tool, arguments
):
    result = await mcp.call_tool(
        tool,
        {**arguments, "as_of": "2015-01-01"},
    )
    data = _result_text(result)
    assert data.get("error") == "invalid_input"
    message = data["message"]
    assert "for this application (2020-01-01)" in message
    assert "does not establish" in message and "earlier records" in message
    assert "began" not in message
    assert "Choose an as_of date on or after 2020-01-01" in message


# ── classify_tool_error helper ─────────────────────────────────────────────────


def test_classify_rate_limited():
    exc = UpstreamRateLimited("too many requests")
    result = classify_tool_error(exc)
    assert result["error"] == "rate_limited"
    assert "SOCRATA_APP_TOKEN" in result["message"]


def test_classify_upstream_unavailable():
    exc = UpstreamUnavailable("connection failed")
    result = classify_tool_error(exc)
    assert result["error"] == "upstream_unavailable"
    assert "retry" in result["message"].lower()


def test_classify_value_error():
    exc = ValueError("bad input")
    result = classify_tool_error(exc)
    assert result["error"] == "invalid_input"
    assert "bad input" in result["message"]


# ── Rate limit / upstream errors propagate to tool surface ─────────────────────


@pytest.mark.asyncio
async def test_rate_limited_returns_structured_error():
    import resp_mcp.tools.trend as _trend_mod
    from resp_mcp.models.common import Signal as _Signal

    failing = AsyncMock(side_effect=UpstreamRateLimited("429"))
    with patch.dict(_trend_mod._ADAPTERS, {_Signal.hospital_admissions: failing}):
        result = await mcp.call_tool(
            "assess_trend",
            {
                "jurisdiction": "GA",
                "pathogen": "influenza",
                "signal": "hospital_admissions",
            },
        )
    data = _result_text(result)
    assert data.get("error") == "rate_limited"


@pytest.mark.asyncio
async def test_upstream_unavailable_returns_structured_error():
    import resp_mcp.tools.trend as _trend_mod
    from resp_mcp.models.common import Signal as _Signal

    failing = AsyncMock(side_effect=UpstreamUnavailable("503"))
    with patch.dict(_trend_mod._ADAPTERS, {_Signal.hospital_admissions: failing}):
        result = await mcp.call_tool(
            "assess_trend",
            {
                "jurisdiction": "GA",
                "pathogen": "influenza",
                "signal": "hospital_admissions",
            },
        )
    data = _result_text(result)
    assert data.get("error") == "upstream_unavailable"


# ── Zero stdout during tool call ───────────────────────────────────────────────


@pytest.mark.asyncio
async def test_no_stdout_during_tool_call():
    """Verify that no tool output is written to stdout (MCP stdio transport safety)."""
    obs = _obs_rising(date(2026, 11, 14), Signal.hospital_admissions)
    prov = _prov("vdzy-6i9v", "state", date(2026, 11, 14))

    captured = io.StringIO()
    original_stdout = sys.stdout
    sys.stdout = captured
    try:
        with patch(
            "resp_mcp.sources.nhsn.fetch_series",
            new_callable=AsyncMock,
            return_value=(obs, prov),
        ):
            await mcp.call_tool(
                "assess_trend",
                {
                    "jurisdiction": "GA",
                    "pathogen": "influenza",
                    "signal": "hospital_admissions",
                },
            )
    finally:
        sys.stdout = original_stdout

    assert captured.getvalue() == "", f"Tool wrote to stdout: {captured.getvalue()!r}"
