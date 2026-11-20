"""Prompts sub-package — reusable conversation starters.

Each prompt module exposes a register(mcp) function. Add imports here as
prompts are implemented in Phase 3.
"""

from __future__ import annotations

from fastmcp import FastMCP


def register_prompts(mcp: FastMCP) -> None:
    """Register all prompts with the MCP server. (Phase 3 — currently empty.)"""
    pass


__all__ = ["register_prompts"]
