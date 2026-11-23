"""Validate model settings; --live checks synthetic tool and judge requests."""

from __future__ import annotations

import argparse
import asyncio
import json
import logging
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from eval.phoenix.config import gateway, validate_models


async def smoke():
    from langchain_core.messages import HumanMessage, ToolMessage

    from eval.phoenix.digital_gateway import agent_model
    from eval.phoenix.judges.common import evaluator

    cfg = gateway("agent")
    if cfg.provider != "digital_gateway":
        raise ValueError(
            "This live probe currently targets the Digital Gateway adapter"
        )
    async with agent_model(cfg) as model:
        tool = {
            "type": "function",
            "function": {
                "name": "gateway_probe",
                "description": "Return synthetic status ok.",
                "parameters": {
                    "type": "object",
                    "properties": {},
                    "required": [],
                    "additionalProperties": False,
                },
            },
        }
        question = HumanMessage(content="Call gateway_probe once, then reply ok.")
        result = await model.bind_tools([tool], tool_choice="required").ainvoke(
            [question]
        )
        if (
            len(result.tool_calls) != 1
            or result.tool_calls[0]["name"] != "gateway_probe"
        ):
            raise ValueError("The synthetic tool-call contract was not satisfied")
        reply = await model.ainvoke(
            [
                question,
                result,
                ToolMessage(content="ok", tool_call_id=result.tool_calls[0]["id"]),
            ]
        )
        if "ok" not in str(reply.content).lower():
            raise ValueError("The synthetic tool-result contract was not satisfied")
    judge = evaluator(
        "gateway_smoke", "Classify this synthetic status: {input}", "ok", "bad"
    )
    try:
        result = await asyncio.to_thread(judge.evaluate, {"input": "ok"})
        if result[0].label != "ok" or result[0].score != 1:
            raise ValueError("The synthetic judge contract was not satisfied")
    finally:
        judge.llm._sync_client.close()
        await judge.llm._async_client.close()
        evaluator.cache_clear()
    print(
        json.dumps(
            {
                "smoke": "passed",
                "tool_round_trip": True,
                "structured_judge": True,
                **validate_models(),
            }
        )
    )


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--live", action="store_true")
    args = parser.parse_args()
    os.environ["LANGSMITH_TRACING"] = "false"
    logging.getLogger("azure").setLevel(logging.CRITICAL)
    try:
        config = validate_models()
        if args.live:
            asyncio.run(smoke())
        else:
            print(json.dumps({"configuration": "valid", "model_calls": 0, **config}))
    except Exception as exc:
        # No response bodies, headers, URLs, identities or credentials in logs.
        print(
            json.dumps(
                {
                    "smoke": "failed",
                    "error_type": type(exc).__name__,
                    "status": getattr(exc, "status_code", None),
                }
            )
        )
        raise SystemExit(1) from None


if __name__ == "__main__":
    main()
