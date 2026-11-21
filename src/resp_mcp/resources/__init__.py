"""Resources sub-package — static/semi-static data the client can read directly.

Three resources are registered:
  resp://sources        — Overview of the three CDC datasets
  resp://methods        — Analytic methods and disclaimers
  resp://jurisdictions  — JSON list of all supported jurisdiction codes
"""

from __future__ import annotations

from fastmcp import FastMCP

from resp_mcp.resources import jurisdictions, methods, sources


def register_resources(mcp: FastMCP) -> None:
    """Register all three resources with the MCP server."""
    sources.register(mcp)
    methods.register(mcp)
    jurisdictions.register(mcp)


__all__ = ["register_resources"]
