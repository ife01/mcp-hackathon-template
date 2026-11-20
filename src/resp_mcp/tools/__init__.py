"""Tools sub-package — one file per tool.

Each tool module exposes a register(mcp) function. Add imports here as tools
are implemented in Phase 3.
"""

from __future__ import annotations

from fastmcp import FastMCP


def register_tools(mcp: FastMCP) -> None:
    """Register all tools with the MCP server. (Phase 3 — currently empty.)"""
    pass


__all__ = ["register_tools"]
