"""Prompts sub-package — reusable conversation starters.

Two prompts are registered:
  weekly_respiratory_briefing(jurisdiction, audience)
  regional_hotspot_review(pathogen, hhs_region)
"""

from __future__ import annotations

from fastmcp import FastMCP

from resp_mcp.prompts import briefing


def register_prompts(mcp: FastMCP) -> None:
    """Register both prompts with the MCP server."""
    briefing.register(mcp)


__all__ = ["register_prompts"]
