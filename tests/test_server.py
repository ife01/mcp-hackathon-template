"""Smoke tests for the Respiratory MCP server.

These verify the server imports and every submodule registers without error.
Functional tests for tools are added in Phase 3 (tests/contract/).
"""

from __future__ import annotations

import pytest
from fastmcp import FastMCP

from resp_mcp.config import settings
from resp_mcp.server import mcp


def test_server_is_importable():
    assert mcp is not None


def test_server_has_name():
    assert mcp.name == "Respiratory Season Situational Awareness"


def test_default_transport_is_stdio():
    """Guard against accidentally shipping with a non-stdio default."""
    assert settings.mcp_transport == "stdio"


def test_tools_register_without_error():
    from resp_mcp.tools import register_tools

    register_tools(FastMCP("test"))  # must not raise


def test_prompts_register_without_error():
    from resp_mcp.prompts import register_prompts

    register_prompts(FastMCP("test"))  # must not raise


def test_resources_register_without_error():
    from resp_mcp.resources import register_resources

    register_resources(FastMCP("test"))  # must not raise


def test_routes_register_without_error():
    from resp_mcp.routes import register_routes

    register_routes(FastMCP("test"))  # must not raise


@pytest.mark.asyncio
async def test_four_tools_registered():
    """Phase 3 — server must have all four tools registered."""
    tools = await mcp.list_tools()
    names = [t.name for t in tools]
    assert len(tools) == 4, f"Expected 4 tools, found: {names}"
    expected = {
        "get_respiratory_snapshot",
        "assess_trend",
        "compare_to_prior_seasons",
        "find_jurisdictions_with_rising_activity",
    }
    assert set(names) == expected, f"Unexpected tools: {set(names) ^ expected}"
