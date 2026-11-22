"""Credential-free scripted graph and judge verification; not a model benchmark."""

from __future__ import annotations

import argparse
import asyncio
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from langchain_core.language_models.chat_models import BaseChatModel
from langchain_core.messages import AIMessage, ToolMessage
from langchain_core.outputs import ChatGeneration, ChatResult

from eval.phoenix.agent import RespiratoryAgent, adapter, text_content
from eval.phoenix.data import load_dataset, reference_for


class ScriptedModel(BaseChatModel):
    @property
    def _llm_type(self):
        return "scripted-protocol-verification"

    def bind_tools(self, tools, **kwargs):
        assert len(tools) == 4
        return self

    def _generate(self, messages, stop=None, run_manager=None, **kwargs):
        if not any(isinstance(m, ToolMessage) for m in messages):
            response = AIMessage(
                content="",
                tool_calls=[
                    {
                        "name": "assess_trend",
                        "args": {
                            "jurisdiction": code,
                            "pathogen": "influenza",
                            "signal": "hospital_admissions",
                            "as_of": "2026-10-31",
                        },
                        "id": f"verification-{code}",
                        "type": "tool_call",
                    }
                    for code in ("GA", "CA")
                ],
            )
        else:
            response = AIMessage(
                content="Answer: "
                + reference_for("P01")["answer"]
                + "\nScripted harness verification only; not a real agent answer."
            )
        return ChatResult(generations=[ChatGeneration(message=response)])


class ScriptedJudge:
    model = "scripted-verification-judge"

    def generate_classification(self, **kwargs):
        assert kwargs["temperature"] == 0
        return {
            "label": "correct",
            "explanation": "Scripted evaluator API verification only.",
        }


async def main(collector_endpoint=None):
    rows, _ = load_dataset("respiratory-eval-0")
    row = next(r for r in rows if r["case_id"] == "P01")
    agent = RespiratoryAgent(
        trace=bool(collector_endpoint),
        model_factory=ScriptedModel,
        project_name="respiratory-harness-verification",
        phoenix_endpoint=collector_endpoint,
    )
    result = await agent.run(row["query"], "P01")
    assert result["verification_only"]
    assert len(result["tool_calls"]) == 2
    for call in result["tool_calls"]:
        assert call["status"] == "completed"
        assert call["output"]["series"][-1]["week_ending"] == "2026-10-31"
    print(
        "LangChain graph -> frozen MCP subprocess -> two "
        "tool results -> final message PASS"
    )
    async with adapter("P11") as bridge:
        tool = next(
            t for t in await bridge.list_tools() if t.name == "get_respiratory_snapshot"
        )
        raw = await tool.ainvoke(
            {"jurisdiction": "GA", "pathogens": ["influenza"], "as_of": "2026-10-31"}
        )
        assert json.loads(text_content(raw))["error"] == "upstream_unavailable"
    print("Per-case outage isolation and graceful source failure PASS")

    from phoenix.evals import ClassificationEvaluator

    evaluator = ClassificationEvaluator(
        name="verification",
        llm=ScriptedJudge(),
        prompt_template="Question: {input}\nAnswer: {output}\nReference: {reference}",
        choices={"correct": 1, "incorrect": 0},
        temperature=0,
    )
    scores = evaluator.evaluate(
        {"input": "test", "output": "test", "reference": "test"}
    )
    assert len(scores) == 1 and scores[0].score == 1 and scores[0].label == "correct"
    print("Phoenix ClassificationEvaluator templating and Score contract PASS")
    from phoenix.client import Client

    from eval.phoenix.judges import (
        check_answer_scope,
        check_public_health,
        match_expected_response,
    )

    assert all(
        callable(x)
        for x in (
            Client,
            check_answer_scope,
            check_public_health,
            match_expected_response,
        )
    )
    print("Phoenix client and all three judge modules import PASS")
    if collector_endpoint:
        from eval.phoenix.agent import _TRACING

        assert _TRACING and _TRACING[2].force_flush()
        base = collector_endpoint.removesuffix("/v1/traces")
        storage = Client(base_url=base)
        for _ in range(10):
            frame = storage.spans.get_spans_dataframe(
                project_identifier="respiratory-harness-verification"
            )
            if len(frame):
                break
            await asyncio.sleep(0.2)
        assert len(frame) > 0
        print(
            f"Phoenix OTLP trace export and persisted span "
            f"readback PASS ({len(frame)} spans)"
        )
    print("No model gateway calls, model scores, or wxO session were used.")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--collector-endpoint")
    args = parser.parse_args()
    if args.collector_endpoint:
        from urllib.parse import urlsplit

        if urlsplit(args.collector_endpoint).hostname not in (
            "127.0.0.1",
            "localhost",
            "::1",
        ) or not args.collector_endpoint.endswith("/v1/traces"):
            raise ValueError(
                "Verification traces may only target a loopback Phoenix collector."
            )
    asyncio.run(main(args.collector_endpoint))
