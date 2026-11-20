"""MCP server entry point for the Respiratory Season Situational Awareness server.

Keep this file THIN. It only:
  1. Configures logging to stderr (never stdout).
  2. Creates the FastMCP instance.
  3. Registers tools / prompts / resources / routes from submodules.
  4. Decides which transport to run (stdio locally vs. HTTP when deployed).

All real logic lives in the submodules:
  tools/      one file per tool (each exposes register(mcp))
  prompts/    conversation starters
  resources/  static/semi-static data the client can read directly
  routes.py   HTTP-only infrastructure (health check, version)
  config.py   settings loaded from env vars / .env
  models/     Pydantic models for tool I/O
  clients/    Socrata HTTP client
  sources/    CDC data source adapters
  analytics/  pure-function analytics (no I/O)
  reference/  jurisdiction codes, MMWR helpers
"""

from __future__ import annotations

import os

from fastmcp import FastMCP

from resp_mcp.config import configure_logging, settings
from resp_mcp.prompts import register_prompts
from resp_mcp.resources import register_resources
from resp_mcp.routes import register_routes
from resp_mcp.tools import register_tools

# Configure logging first — before any module emits a log line.
# CRITICAL: all output goes to stderr; stdout is reserved for MCP stdio protocol.
configure_logging()

mcp = FastMCP(
    name="Respiratory Season Situational Awareness",
    instructions=(
        "Provides situational awareness on influenza, COVID-19, and RSV using "
        "public CDC data (NHSN hospital admissions, NWSS wastewater, NREVSS test "
        "positivity). Use the available tools to look up current levels, assess "
        "trends, compare to prior seasons, and identify rising jurisdictions. "
        "Always cite the data source name and week-ending date in your answers. "
        "Never invent numbers — every figure must come from a tool call."
    ),
)

register_tools(mcp)
register_prompts(mcp)
register_resources(mcp)
register_routes(mcp)


def main() -> None:
    """Start the server, choosing a transport based on the environment."""
    platform_port = os.getenv("DATABRICKS_APP_PORT") or os.getenv("PORT")

    if platform_port:
        mcp.run(transport="http", host="0.0.0.0", port=int(platform_port))
    elif settings.mcp_transport == "streamable-http":
        mcp.run(
            transport="streamable-http",
            host=settings.mcp_host,
            port=settings.mcp_port,
        )
    else:
        mcp.run(transport="stdio")


if __name__ == "__main__":
    main()
