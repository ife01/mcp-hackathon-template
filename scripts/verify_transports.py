"""Verify stdio subprocess and in-process HTTP MCP handshakes without CDC calls."""

from __future__ import annotations

import asyncio
import json
import sys
from pathlib import Path

import httpx
from fastmcp import Client
from fastmcp.client.transports import StdioTransport

from resp_mcp.server import mcp


async def verify():
    root = Path(__file__).resolve().parents[1]
    transport = StdioTransport(
        command=sys.executable,
        args=[str(root / "main.py")],
        cwd=str(root),
        env={"MCP_TRANSPORT": "stdio", "LOG_LEVEL": "ERROR"},
    )
    async with Client(transport) as client:
        assert len(await client.list_tools()) == 4
        assert len(await client.list_resources()) == 3
        assert len(await client.list_prompts()) == 2
        result = await client.call_tool(
            "get_respiratory_snapshot", {"jurisdiction": "Georgai"}
        )
        assert json.loads(result.content[0].text)["error"] == "unknown_jurisdiction"
        methods = await client.read_resource("resp://methods")
        assert "national_context" in methods[0].text
    print(
        "stdio subprocess: initialize, list tools/resources/prompts, "
        "call, read resource PASS"
    )

    app = mcp.http_app(json_response=True, stateless_http=True)
    async with app.router.lifespan_context(app):
        async with httpx.AsyncClient(
            transport=httpx.ASGITransport(app=app),
            base_url="http://testserver",
            headers={"Accept": "application/json, text/event-stream"},
        ) as client:
            response = await client.post(
                "/mcp",
                json={
                    "jsonrpc": "2.0",
                    "id": 1,
                    "method": "initialize",
                    "params": {
                        "protocolVersion": "2025-03-26",
                        "capabilities": {},
                        "clientInfo": {"name": "verification", "version": "1"},
                    },
                },
            )
            assert response.status_code == 200, response.text
            response = await client.post(
                "/mcp",
                json={"jsonrpc": "2.0", "id": 2, "method": "tools/list", "params": {}},
            )
            assert len(response.json()["result"]["tools"]) == 4
            response = await client.post(
                "/mcp",
                json={
                    "jsonrpc": "2.0",
                    "id": 3,
                    "method": "tools/call",
                    "params": {
                        "name": "get_respiratory_snapshot",
                        "arguments": {"jurisdiction": "Georgai"},
                    },
                },
            )
            output = json.loads(response.json()["result"]["content"][0]["text"])
            assert output["error"] == "unknown_jurisdiction"
            response = await client.get("/health")
            assert response.status_code == 200
    print("HTTP ASGI: initialize, list tools, call, health PASS")
    print("No CDC calls, wxO session, external deployment, or Docker engine tested.")


if __name__ == "__main__":
    asyncio.run(verify())
