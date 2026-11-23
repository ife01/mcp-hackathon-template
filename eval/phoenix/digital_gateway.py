"""Azure client-credential gateway; credentials stay inside SDK clients."""

from __future__ import annotations

import asyncio
import json
import os
import threading
from contextlib import asynccontextmanager
from functools import lru_cache
from urllib.parse import urlsplit

import httpx

from eval.phoenix.config import Gateway

_TOKEN_LOCK = threading.Lock()


def configuration(role: str) -> Gateway:
    required = (
        "AZURE_TENANT_ID",
        "AZURE_CLIENT_ID",
        "AZURE_CLIENT_SECRET",
        "DGW_OPENAI_ENDPOINT",
        "DGW_OPENAI_API_VERSION",
        "DGW_SUBSCRIPTION_KEY",
        f"{role.upper()}_MODEL",
    )
    missing = [name for name in required if not os.getenv(name, "").strip()]
    if not (os.getenv("DGW_SCOPE") or os.getenv("DGW_scope")):
        missing.append("DGW_SCOPE")
    if missing:
        raise ValueError("Digital Gateway requires " + ", ".join(missing))
    endpoint = os.environ["DGW_OPENAI_ENDPOINT"].rstrip("/")
    url = urlsplit(endpoint)
    if (
        url.scheme != "https"
        or not url.hostname
        or url.username
        or url.password
        or url.query
        or url.fragment
    ):
        raise ValueError("DGW_OPENAI_ENDPOINT requires HTTPS without URL credentials")
    try:
        mappings = json.loads(os.getenv("DGW_MODEL_DEPLOYMENTS", "{}"))
    except ValueError:
        raise ValueError("DGW_MODEL_DEPLOYMENTS must be a JSON object") from None
    if not isinstance(mappings, dict) or not all(
        isinstance(k, str) and isinstance(v, str) and v.strip()
        for k, v in mappings.items()
    ):
        raise ValueError("DGW_MODEL_DEPLOYMENTS must map model IDs to deployments")
    model = os.environ[f"{role.upper()}_MODEL"].strip()
    deployment = os.getenv(f"DGW_{role.upper()}_DEPLOYMENT") or mappings.get(model)
    if not deployment:
        raise ValueError(f"No explicit Digital Gateway deployment for {role} model")
    return Gateway(
        endpoint,
        model,
        "",
        float(os.getenv("MODEL_TIMEOUT_SECONDS", "90")),
        provider="digital_gateway",
        deployment=deployment,
    )


@lru_cache(maxsize=1)
def token_provider():
    from azure.identity import ClientSecretCredential, get_bearer_token_provider

    credential = ClientSecretCredential(
        os.environ["AZURE_TENANT_ID"],
        os.environ["AZURE_CLIENT_ID"],
        os.environ["AZURE_CLIENT_SECRET"],
        logging_enable=False,
    )
    get_token = get_bearer_token_provider(
        credential, os.getenv("DGW_SCOPE") or os.environ["DGW_scope"]
    )

    def token():
        with _TOKEN_LOCK:
            return get_token()

    return token


def sdk_options(cfg: Gateway, *, asynchronous=False) -> dict:
    from openai.lib.azure import API_KEY_SENTINEL

    get_token = token_provider()

    async def async_token():
        return await asyncio.to_thread(get_token)

    return {
        "azure_endpoint": cfg.base_url,
        "azure_deployment": cfg.deployment,
        "api_version": os.environ["DGW_OPENAI_API_VERSION"],
        "api_key": API_KEY_SENTINEL,
        "azure_ad_token_provider": async_token if asynchronous else get_token,
        "default_headers": {
            "Ocp-Apim-Subscription-Key": os.environ["DGW_SUBSCRIPTION_KEY"]
        },
        "timeout": cfg.timeout,
        # Explicitly ignore unrelated ambient static Azure tokens.
        "azure_ad_token": None,
    }


def generation_options(cfg: Gateway) -> dict:
    # Non-reasoning mode permits zero temperature on supported GPT-5 deployments.
    # The live smoke test must verify this capability before a full experiment.
    return {"reasoning_effort": "none"} if cfg.model.startswith("gpt-5") else {}


@asynccontextmanager
async def agent_model(cfg: Gateway):
    from langchain_openai import ChatOpenAI
    from openai import AsyncAzureOpenAI, AzureOpenAI
    from openai.lib.azure import API_KEY_SENTINEL

    # SDK clients carry authentication. Never place subscription headers on the
    # serializable LangChain model, where tracing could expose their values.
    with httpx.Client(trust_env=False) as http_client:
        async with httpx.AsyncClient(trust_env=False) as async_http:
            with AzureOpenAI(
                **sdk_options(cfg), http_client=http_client, max_retries=1
            ) as sync:
                async with AsyncAzureOpenAI(
                    **sdk_options(cfg, asynchronous=True),
                    http_client=async_http,
                    max_retries=1,
                ) as asynchronous:
                    sync._azure_ad_token = asynchronous._azure_ad_token = None
                    yield ChatOpenAI(
                        model=cfg.model,
                        api_key=API_KEY_SENTINEL,
                        client=sync.chat.completions,
                        async_client=asynchronous.chat.completions,
                        root_client=sync,
                        root_async_client=asynchronous,
                        temperature=0,
                        max_completion_tokens=1536,
                        use_responses_api=False,
                        **generation_options(cfg),
                    )
