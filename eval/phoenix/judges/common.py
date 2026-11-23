"""Shared LLM-as-judge invocation, isolated from the agent-under-test."""

from __future__ import annotations

import json
import os
import threading
import time
from functools import lru_cache

import httpx
from dotenv import load_dotenv

from eval.phoenix.config import gateway

load_dotenv()
_JUDGE_LIMIT = threading.BoundedSemaphore(2)
_PACE_LOCK = threading.Lock()
_LAST_REQUEST = 0.0


def pace_request():
    global _LAST_REQUEST
    default = "6" if os.getenv("MODEL_PROVIDER") == "digital_gateway" else "0"
    interval = min(30, max(0, float(os.getenv("JUDGE_MIN_INTERVAL_SECONDS", default))))
    with _PACE_LOCK:
        delay = interval - (time.monotonic() - _LAST_REQUEST)
        if delay > 0:
            time.sleep(delay)
        _LAST_REQUEST = time.monotonic()


@lru_cache(maxsize=8)
def evaluator(name: str, template: str, positive: str, negative: str):
    # Imported lazily so dataset pre-flight neither requires a key nor contacts a model.
    from phoenix.evals import LLM, ClassificationEvaluator

    cfg = gateway("judge")
    if cfg.provider == "digital_gateway":
        from eval.phoenix.digital_gateway import generation_options, sdk_options

        llm = LLM(
            provider="azure",
            model=cfg.deployment,
            **sdk_options(cfg),
            sync_client_kwargs={"http_client": httpx.Client(trust_env=False)},
            async_client_kwargs={
                **sdk_options(cfg, asynchronous=True),
                "http_client": httpx.AsyncClient(trust_env=False),
            },
        )
        llm._sync_client.client._azure_ad_token = None
        llm._async_client.client._azure_ad_token = None
        extra = generation_options(cfg)
    else:
        llm = _compatible_llm(cfg)
        extra = {}
    return ClassificationEvaluator(
        name=name,
        llm=llm,
        prompt_template=template,
        choices={positive: 1, negative: 0},
        temperature=0,
        include_explanation=True,
        max_completion_tokens=1024,
        **extra,
    )


def _compatible_llm(cfg):
    from phoenix.evals import LLM

    llm = LLM(
        provider="openai",
        model=cfg.model,
        api_key=cfg.api_key,
        base_url=cfg.base_url,
        timeout=cfg.timeout,
        sync_client_kwargs={"http_client": httpx.Client(trust_env=False)},
        async_client_kwargs={"http_client": httpx.AsyncClient(trust_env=False)},
    )
    return llm


def judge(name, template, positive, negative, values):
    payload = {
        k: json.dumps(v, ensure_ascii=True) if not isinstance(v, str) else v
        for k, v in values.items()
    }
    if sum(len(v) for v in payload.values()) > 120000:
        raise ValueError(
            "Judge input exceeds the explicit limit; no silent truncation or score."
        )
    for attempt in range(3):
        try:
            with _JUDGE_LIMIT:
                pace_request()
                result = evaluator(name, template, positive, negative).evaluate(payload)
            break
        except Exception as exc:
            limited = getattr(exc, "status_code", None) == 429 or (
                type(exc).__name__ == "RateLimitError"
            )
            if limited and attempt < 2:
                # Retry bounded transient throttling only. Never expose headers.
                headers = getattr(getattr(exc, "response", None), "headers", {})
                try:
                    delay = float(headers.get("retry-after", 10 * (attempt + 1)))
                except (TypeError, ValueError):
                    delay = 10 * (attempt + 1)
                time.sleep(min(30, max(0, delay)))
                continue
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
