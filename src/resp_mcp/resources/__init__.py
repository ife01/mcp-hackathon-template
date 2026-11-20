"""Resources sub-package — static/semi-static data the client can read.

Each resource module exposes a register(mcp) function. Add imports here as
resources are implemented in Phase 3.
"""

from __future__ import annotations

from fastmcp import FastMCP


def register_resources(mcp: FastMCP) -> None:
    """Register all resources with the MCP server. (Phase 3 — currently empty.)"""
    pass


__all__ = ["register_resources"]
