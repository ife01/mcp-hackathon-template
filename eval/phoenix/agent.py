"""RespMcpAgent — LangChain agent connected to the Respiratory MCP server.

Transport: streamable-HTTP (connects to a running server at MCP_SERVER_URL).
Uses the native mcp 2.x Python client to load tools, then wraps them as
LangChain tools — avoiding the fastmcp 4.x (mcp>=2.3) vs
langchain-mcp-adapters (mcp<2.0) mutual exclusion.

Decision logged in docs/DECISIONS.md: langchain-mcp-adapters 0.3.x is
incompatible with mcp 2.x (mcp.server.fastmcp was removed; RequestContext and
mcp.shared.session were renamed/removed). The native mcp client + manual tool
wrapping is the documented replacement.

Start the server before running the agent:
    MCP_TRANSPORT=streamable-http MCP_PORT=8000 uv run python main.py

Usage:
    # Smoke test (requires running server + model credentials)
    python eval/phoenix/agent.py

    # MCP connectivity check only (requires running server)
    python eval/phoenix/agent.py --check-mcp
"""

from __future__ import annotations

import argparse
import asyncio
import logging
import os
import sys
from pathlib import Path
from typing import Any

from dotenv import load_dotenv

load_dotenv()  # walks up from CWD to find .env

logger = logging.getLogger(__name__)

# ── Repo root (two levels up from eval/phoenix/) ──────────────────────────────
REPO_ROOT = str(Path(__file__).resolve().parent.parent.parent)


# ── Native mcp 2.x tool loader ─────────────────────────────────────────────────

async def _load_mcp_tools_http(mcp_url: str) -> list[Any]:
    """
    Connect to the MCP server over streamable-HTTP, fetch the tools/list,
    and return them as LangChain StructuredTool instances.
    Uses the native mcp 2.x client — no langchain-mcp-adapters needed.
    """
    from langchain_core.tools import StructuredTool
    from mcp import ClientSession
    from mcp.client.streamable_http import streamable_http_client

    tools_out = []

    async with streamable_http_client(mcp_url) as (read, write, _):
        async with ClientSession(read, write) as session:
            await session.initialize()
            tools_result = await session.list_tools()

            for tool_def in tools_result.tools:
                # Capture in closure — Python loop variable binding
                _name = tool_def.name
                _description = tool_def.description or _name
                _schema = tool_def.inputSchema or {}

                def _make_tool_fn(name: str):
                    async def _call_tool(**kwargs) -> str:
                        async with streamable_http_client(mcp_url) as (r, w, _):
                            async with ClientSession(r, w) as sess:
                                await sess.initialize()
                                result = await sess.call_tool(name, kwargs)
                                # Return first text content
                                for c in result.content:
                                    if hasattr(c, "text"):
                                        return c.text
                                return str(result.content)

                    return _call_tool

                # Build a synchronous wrapper for LangChain
                _async_fn = _make_tool_fn(_name)

                def _make_sync_fn(afn):
                    def _sync(**kwargs) -> str:
                        return asyncio.run(afn(**kwargs))
                    return _sync

                _sync_fn = _make_sync_fn(_async_fn)
                _sync_fn.__name__ = _name

                lc_tool = StructuredTool.from_function(
                    func=_sync_fn,
                    name=_name,
                    description=_description,
                    args_schema=None,  # Let LangChain infer from the function
                )
                tools_out.append(lc_tool)

    return tools_out


# ── Agent builder ─────────────────────────────────────────────────────────────

def _build_agent(model, tools, system_prompt: str):
    from langchain.agents import AgentExecutor, create_tool_calling_agent
    from langchain_core.prompts import ChatPromptTemplate, MessagesPlaceholder

    prompt = ChatPromptTemplate.from_messages([
        ("system", system_prompt),
        MessagesPlaceholder(variable_name="chat_history", optional=True),
        ("human", "{input}"),
        MessagesPlaceholder(variable_name="agent_scratchpad"),
    ])
    agent = create_tool_calling_agent(model, tools, prompt)
    return AgentExecutor(agent=agent, tools=tools, verbose=False, max_iterations=12)


# ── RespMcpAgent ──────────────────────────────────────────────────────────────

class RespMcpAgent:
    """Agent that calls the Respiratory MCP server and is evaluated by Phoenix."""

    def __init__(
        self,
        system_prompt_version: str = "v2",
        project_name: str = "respiratory-mcp-eval",
        phoenix_endpoint: str = "http://localhost:6006",
        mcp_url: str | None = None,
    ) -> None:
        self.system_prompt_version = system_prompt_version
        self.project_name = project_name
        self.phoenix_endpoint = phoenix_endpoint
        self.mcp_url = mcp_url or os.getenv("MCP_SERVER_URL", "http://localhost:8000/mcp")
        self._executor = None
        self._initialized = False

    def _load_system_prompt(self) -> str:
        prompt_file = (
            Path(__file__).parent
            / "prompts"
            / f"system_prompt_{self.system_prompt_version}.txt"
        )
        if not prompt_file.exists():
            raise FileNotFoundError(f"System prompt not found: {prompt_file}")
        return prompt_file.read_text()

    async def initialize(self) -> None:
        if self._initialized:
            return

        # Phoenix OTEL instrumentation
        from openinference.instrumentation.langchain import LangChainInstrumentor
        from phoenix.otel import register

        tracer_provider = register(
            project_name=self.project_name,
            endpoint=f"{self.phoenix_endpoint}/v1/traces",
        )
        LangChainInstrumentor().instrument(tracer_provider=tracer_provider)

        # Load tools from the MCP server via native mcp 2.x HTTP client
        tools = await _load_mcp_tools_http(self.mcp_url)
        logger.info("MCP tools loaded: %s", [t.name for t in tools])

        # LangChain model (OpenAI-compatible)
        from langchain_openai import ChatOpenAI

        base_url = os.environ["USAI_BASE_URL"].rstrip("/")
        if not base_url.endswith("/api/v1"):
            base_url = f"{base_url}/api/v1"

        model = ChatOpenAI(
            model=os.environ["AGENT_MODEL"],
            openai_api_key=os.environ["USAI_API_KEY"],
            openai_api_base=base_url,
            temperature=0,
            max_retries=2,
        )

        self._executor = _build_agent(model, tools, self._load_system_prompt())
        self._initialized = True
        logger.info("RespMcpAgent initialized (prompt=%s)", self.system_prompt_version)

    async def run(self, query: str) -> str:
        if not self._initialized:
            await self.initialize()
        result = await self._executor.ainvoke({"input": query})
        return result.get("output", "")

    async def close(self) -> None:
        pass  # HTTP transport — no persistent connection to close

    def create_experiment_task(self):
        """Return a synchronous task function for Phoenix run_experiment."""
        agent = self

        def task(example) -> str:
            query = example.input.get("query", "")
            return asyncio.run(agent.run(query))

        return task


# ── CLI ───────────────────────────────────────────────────────────────────────


async def _check_mcp_only() -> None:
    """Verify MCP server is running and returns tools (no model needed).

    Requires the server to be running:
        MCP_TRANSPORT=streamable-http MCP_PORT=8000 uv run python main.py
    """
    from mcp import ClientSession
    from mcp.client.streamable_http import streamable_http_client

    mcp_url = os.getenv("MCP_SERVER_URL", "http://localhost:8000/mcp")
    async with streamable_http_client(mcp_url) as (read, write, _):
        async with ClientSession(read, write) as session:
            await session.initialize()
            tools_result = await session.list_tools()
            tools = tools_result.tools
            print(f"MCP server responded — {len(tools)} tools registered:")
            for t in tools:
                print(f"  {t.name}: {(t.description or '')[:60]}")


async def _smoke_test() -> None:
    agent = RespMcpAgent(system_prompt_version="v2")
    await agent.initialize()
    q = (
        "What was the influenza hospital admission rate in Georgia "
        "for the week ending October 31 2026?"
    )
    print(f"\nQuery: {q}")
    answer = await agent.run(q)
    print(f"Answer: {answer}")
    await agent.close()


def main() -> None:
    logging.basicConfig(level=logging.INFO, stream=sys.stderr)
    parser = argparse.ArgumentParser(description="RespMcpAgent CLI")
    parser.add_argument(
        "--check-mcp", action="store_true",
        help="Check that the MCP server is running and tools load (no model needed)"
    )
    args = parser.parse_args()

    if args.check_mcp:
        asyncio.run(_check_mcp_only())
    else:
        asyncio.run(_smoke_test())


if __name__ == "__main__":
    main()
