"""Custom HTTP routes for the MCP server.

Only active when the server runs over HTTP (streamable-http or platform port).
"""

from __future__ import annotations

from fastmcp import FastMCP
from starlette.requests import Request
from starlette.responses import JSONResponse

from resp_mcp import __version__


def register_routes(mcp: FastMCP) -> None:
    """Register custom HTTP routes with the server."""

    @mcp.custom_route("/health", methods=["GET"])
    async def health_check(request: Request) -> JSONResponse:
        return JSONResponse({"status": "healthy", "service": "respiratory-mcp-server"})

    @mcp.custom_route("/version", methods=["GET"])
    async def version(request: Request) -> JSONResponse:
        return JSONResponse({"version": __version__})
