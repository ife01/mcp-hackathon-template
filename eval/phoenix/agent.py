"""LangChain agent using only a fresh, frozen-data MCP stdio session per case."""

from __future__ import annotations

import argparse
import asyncio
import json
import os
import sys
import threading
import time
import uuid
from pathlib import Path

if __package__ in (None, ""):
    sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

import httpx
from dotenv import load_dotenv
from fastmcp import Client
from fastmcp.client.transports import StdioTransport
from langchain.agents import create_agent
from langchain.mcp import MCPAdapter
from langchain_core.messages import AIMessage, ToolMessage
from langchain_openai import ChatOpenAI

from eval.phoenix.config import MODULE, ROOT, gateway
from eval.phoenix.data import reference_for, source_identity

load_dotenv()
_TRACE_LOCK = threading.Lock()
_TRACING = None


def stdio_config(case_id: str | None = None) -> dict:
    args = [str(MODULE / "frozen_server.py")]
    if case_id:
        reference_for(case_id)  # Reject an unrecorded scenario before spawning.
        args += ["--case-id", case_id]
    return {
        "command": sys.executable,
        "args": args,
        "cwd": str(ROOT),
        "env": {"PYTHONUTF8": "1", "LOG_LEVEL": "ERROR"},
    }


def adapter(case_id: str | None = None) -> MCPAdapter:
    # The skill's legacy adapter requires MCP 1; the installed server uses MCP 2.
    # LangChain's maintained MCPAdapter is the compatible stdio implementation.
    return MCPAdapter(Client(StdioTransport(**stdio_config(case_id))))


def initialize_tracing(project_name: str, endpoint: str):
    global _TRACING
    with _TRACE_LOCK:
        if _TRACING is not None:
            if _TRACING[:2] != (project_name, endpoint):
                raise ValueError(
                    "Tracing is already initialized for another project/endpoint"
                )
            return _TRACING[2]
        from openinference.instrumentation.langchain import LangChainInstrumentor
        from phoenix.otel import register

        provider = register(
            project_name=project_name,
            endpoint=endpoint,
            protocol="http/protobuf",
            batch=False,
            verbose=False,
        )
        LangChainInstrumentor().instrument(tracer_provider=provider)
        _TRACING = (project_name, endpoint, provider)
        return provider


def text_content(content) -> str:
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        return "\n".join(
            block.get("text", "") if isinstance(block, dict) else str(block)
            for block in content
        )
    return str(content)


def capture_messages(messages) -> tuple[str, list[dict]]:
    calls, by_id = [], {}
    for message in messages:
        if isinstance(message, AIMessage):
            for tool in message.tool_calls:
                call = {
                    "id": tool["id"],
                    "name": tool["name"],
                    "arguments": tool["args"],
                    "status": "pending",
                    "output": None,
                }
                by_id[tool["id"]] = call
                calls.append(call)
        elif isinstance(message, ToolMessage):
            call = by_id.get(message.tool_call_id)
            if call is None:
                raise ValueError("Tool result has no matching assistant tool call")
            artifact = message.artifact or {}
            output = (
                artifact.get("structured_content")
                if isinstance(artifact, dict)
                else None
            )
            if output is None:
                try:
                    output = json.loads(text_content(message.content))
                except (ValueError, TypeError):
                    output = {
                        "error": "mcp_protocol_error",
                        "message": text_content(message.content),
                    }
            call.update(
                output=output,
                status="error" if message.status == "error" else "completed",
            )
    assistants = [m for m in messages if isinstance(m, AIMessage)]
    answer = text_content(assistants[-1].content) if assistants else ""
    return answer, calls


class RespiratoryAgent:
    def __init__(
        self,
        system_prompt_version="v2",
        project_name="respiratory-eval",
        phoenix_endpoint=None,
        trace=True,
        model_factory=None,
    ):
        if system_prompt_version not in ("v1", "v2"):
            raise ValueError("Unknown prompt version")
        self.prompt_version = system_prompt_version
        self.project_name = project_name
        self.endpoint = phoenix_endpoint or os.getenv(
            "PHOENIX_COLLECTOR_ENDPOINT", "http://localhost:6006/v1/traces"
        )
        self.trace = trace
        self.model_factory = (
            model_factory  # For credential-free protocol/graph tests only.
        )
        self._initialized = False
        self._task_limit = threading.BoundedSemaphore(1)

    def initialize(self):
        if self._initialized:
            return
        if self.model_factory is None:
            gateway("agent")
        if self.trace:
            initialize_tracing(self.project_name, self.endpoint)
        self.identity = source_identity()
        self._initialized = True

    async def run(self, query: str, case_id: str) -> dict:
        self.initialize()
        # Case ID configures only frozen-data/outage isolation, never an answer.
        reference_for(case_id)
        start = time.perf_counter()
        os.environ["LANGSMITH_TRACING"] = "false"
        async with adapter(case_id) as mcp_adapter:
            tools = await mcp_adapter.list_tools()
            if len(tools) != 4:
                raise ValueError("Expected four respiratory tools")
            if self.model_factory:
                result = await self._invoke(self.model_factory(), tools, query)
                model_name = "scripted-verification-model"
            else:
                cfg = gateway("agent")
                # A new HTTP client per asyncio.run avoids reusing a closed loop.
                async with httpx.AsyncClient(
                    trust_env=False, timeout=cfg.timeout
                ) as client:
                    model = ChatOpenAI(
                        model=cfg.model,
                        base_url=cfg.base_url,
                        api_key=cfg.api_key,
                        temperature=0,
                        timeout=cfg.timeout,
                        max_retries=1,
                        max_completion_tokens=1536,
                        use_responses_api=False,
                        http_async_client=client,
                    )
                    result = await self._invoke(model, tools, query)
                model_name = cfg.model
        answer, calls = capture_messages(result["messages"])
        output = {
            "answer": answer,
            "tool_calls": calls,
            "case_id": case_id,
            "elapsed_seconds": time.perf_counter() - start,
            "prompt_version": self.prompt_version,
            "agent_model": model_name,
            "verification_only": self.model_factory is not None,
            **self.identity,
        }
        folder = MODULE / "runs"
        folder.mkdir(exist_ok=True)
        (folder / f"{case_id}-{uuid.uuid4().hex}.json").write_text(
            json.dumps(output, indent=2) + "\n", encoding="utf-8"
        )
        return output

    async def _invoke(self, model, tools, query):
        prompt = (
            MODULE / "prompts" / f"system_prompt_{self.prompt_version}.txt"
        ).read_text(encoding="utf-8")
        graph = create_agent(model=model, tools=tools, system_prompt=prompt)
        async with asyncio.timeout(
            float(os.getenv("AGENT_RUN_TIMEOUT_SECONDS", "180"))
        ):
            return await graph.ainvoke(
                {"messages": [{"role": "user", "content": query}]},
                config={"recursion_limit": 24, "metadata": self.identity},
            )

    def create_experiment_task(self):
        def task(example):
            inputs = example.input if hasattr(example, "input") else example["input"]
            try:
                with self._task_limit:
                    return asyncio.run(self.run(inputs["query"], inputs["case_id"]))
            except Exception as exc:
                # SDK/provider exceptions may contain credentials or response bodies.
                raise RuntimeError(
                    f"Agent execution failed ({type(exc).__name__}); "
                    f"no answer was scored."
                ) from None

        return task


async def check_mcp():
    identity = source_identity()
    async with adapter("P01") as mcp_adapter:
        tools = await mcp_adapter.list_tools()
        assert len(tools) == 4
        tool = next(t for t in tools if t.name == "assess_trend")
        result = await tool.ainvoke(
            {
                "jurisdiction": "GA",
                "pathogen": "influenza",
                "signal": "hospital_admissions",
                "as_of": "2026-10-31",
            }
        )
        text = text_content(result)
        assert "admissions_per_100k" in text, text
    print(
        json.dumps(
            {"mcp_check": "passed", "tools": 4, "frozen_stdio": True, **identity},
            indent=2,
        )
    )


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--check-mcp", action="store_true")
    parser.add_argument("--case-id", default="P01")
    args = parser.parse_args()
    if args.check_mcp:
        asyncio.run(check_mcp())
    else:
        from eval.phoenix.data import load_dataset

        row = next(
            r
            for r in load_dataset("respiratory-eval-0")[0]
            if r["case_id"] == args.case_id
        )
        print(
            json.dumps(
                asyncio.run(RespiratoryAgent().run(row["query"], args.case_id)),
                indent=2,
            )
        )
