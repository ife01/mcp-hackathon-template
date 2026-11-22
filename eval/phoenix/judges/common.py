"""Shared LLM-as-judge invocation, isolated from the agent-under-test."""

from __future__ import annotations

import json
import threading
from functools import lru_cache

import httpx
from dotenv import load_dotenv

from eval.phoenix.config import gateway

load_dotenv()
_JUDGE_LIMIT = threading.BoundedSemaphore(2)


@lru_cache(maxsize=8)
def evaluator(name: str, template: str, positive: str, negative: str):
    # Imported lazily so dataset pre-flight neither requires a key nor contacts a model.
    from phoenix.evals import LLM, ClassificationEvaluator

    cfg = gateway("judge")
    llm = LLM(
        provider="openai",
        model=cfg.model,
        api_key=cfg.api_key,
        base_url=cfg.base_url,
        timeout=cfg.timeout,
        sync_client_kwargs={"http_client": httpx.Client(trust_env=False)},
        async_client_kwargs={"http_client": httpx.AsyncClient(trust_env=False)},
    )
    return ClassificationEvaluator(
        name=name,
        llm=llm,
        prompt_template=template,
        choices={positive: 1, negative: 0},
        temperature=0,
        include_explanation=True,
    )


def judge(name, template, positive, negative, values):
    payload = {
        k: json.dumps(v, ensure_ascii=True) if not isinstance(v, str) else v
        for k, v in values.items()
    }
    if sum(len(v) for v in payload.values()) > 120000:
        raise ValueError(
            "Judge input exceeds the explicit limit; no silent truncation or score."
        )
    try:
        with _JUDGE_LIMIT:
            result = evaluator(name, template, positive, negative).evaluate(payload)
    except Exception as exc:
        raise RuntimeError(
            f"Judge execution failed ({type(exc).__name__}); no score recorded."
        ) from None
    if (
        len(result) != 1
        or result[0].label not in (positive, negative)
        or result[0].score not in (0, 1)
    ):
        raise ValueError(
            "Judge returned an invalid/missing classification; no score recorded."
        )
    return result[0]
