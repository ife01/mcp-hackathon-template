"""Tools sub-package — one file per tool.

Each tool module exposes a register(mcp) function that decorates its tool
function with @mcp.tool(...) and registers it with the FastMCP instance.
"""

from __future__ import annotations

from fastmcp import FastMCP

from resp_mcp.tools import scan, seasons, snapshot, trend


def register_tools(mcp: FastMCP) -> None:
    """Register all four tools with the MCP server."""
    snapshot.register(mcp)
    trend.register(mcp)
    seasons.register(mcp)
    scan.register(mcp)


__all__ = ["register_tools"]
