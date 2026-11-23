"""Real Azure SDK contracts with synthetic credentials and mocked HTTP."""

import json
from types import SimpleNamespace

import httpx
import pytest
import respx

from eval.phoenix import digital_gateway as dgw
from eval.phoenix.config import gateway


@pytest.fixture
def configured(monkeypatch):
    values = {
        "MODEL_PROVIDER": "digital_gateway",
        "AZURE_TENANT_ID": "test-tenant",
        "AZURE_CLIENT_ID": "test-client",
        "AZURE_CLIENT_SECRET": "synthetic-secret",
        "DGW_OPENAI_ENDPOINT": "https://gateway.example/prefix",
        "DGW_OPENAI_API_VERSION": "2024-10-21",
        "DGW_SUBSCRIPTION_KEY": "synthetic-subscription",
        "DGW_SCOPE": "api://test/.default",
        "DGW_MODEL_DEPLOYMENTS": json.dumps({"gpt-5-mini": "mini-deployment"}),
        "AGENT_MODEL": "gpt-5-mini",
        "JUDGE_MODEL": "gpt-5-mini",
        "AZURE_OPENAI_API_KEY": "unrelated-key",
        "AZURE_OPENAI_AD_TOKEN": "unrelated-token",
    }
    for name, value in values.items():
        monkeypatch.setenv(name, value)
    monkeypatch.setattr(dgw, "token_provider", lambda: lambda: "synthetic-token")


def response(content):
    return httpx.Response(
        200,
        json={
            "id": "synthetic",
            "object": "chat.completion",
            "created": 0,
            "model": "mini-deployment",
            "choices": [
                {
                    "index": 0,
                    "finish_reason": "stop",
                    "message": {"role": "assistant", "content": content},
                }
            ],
        },
    )


@pytest.mark.asyncio
async def test_real_agent_client_uses_aad_and_subscription_without_trace_secrets(
    configured,
):
    url = "https://gateway.example/prefix/openai/deployments/mini-deployment/chat/completions"
    with respx.mock(assert_all_called=True) as router:
        route = router.post(url).mock(return_value=response("ok"))
        async with dgw.agent_model(gateway("agent")) as model:
            answer = await model.ainvoke("Synthetic connection check")
            assert answer.content == "ok"
            serialized = json.dumps(model.to_json(), default=str)
            assert all(
                secret not in serialized
                for secret in (
                    "synthetic-secret",
                    "synthetic-subscription",
                    "synthetic-token",
                )
            )
    request = route.calls[0].request
    assert request.headers["Authorization"] == "Bearer synthetic-token"
    assert request.headers["Ocp-Apim-Subscription-Key"] == "synthetic-subscription"
    assert "api-key" not in request.headers
    payload = json.loads(request.content)
    assert payload["temperature"] == 0 and payload["reasoning_effort"] == "none"
    assert request.url.params["api-version"] == "2024-10-21"


@pytest.mark.asyncio
async def test_real_phoenix_azure_classification(configured):
    from eval.phoenix.judges import common

    common.evaluator.cache_clear()
    url = "https://gateway.example/prefix/openai/deployments/mini-deployment/chat/completions"
    with respx.mock(assert_all_called=True) as router:
        route = router.post(url).mock(
            return_value=response(
                json.dumps(
                    {
                        "label": "pass",
                        "explanation": "Synthetic check",
                    }
                )
            )
        )
        evaluator = common.evaluator(
            "azure_contract", "Question: {input}", "pass", "fail"
        )
        score = evaluator.evaluate({"input": "Synthetic"})[0]
        assert score.label == "pass" and score.score == 1
        evaluator.llm._sync_client.close()
        await evaluator.llm._async_client.close()
    assert route.calls[0].request.headers["Authorization"] == "Bearer synthetic-token"
    common.evaluator.cache_clear()


def test_unknown_deployment_rejected_before_auth(configured, monkeypatch):
    monkeypatch.setenv("DGW_MODEL_DEPLOYMENTS", "{}")
    with pytest.raises(ValueError, match="explicit Digital Gateway deployment"):
        gateway("agent")


def test_missing_credentials_error_names_only(configured, monkeypatch):
    monkeypatch.delenv("AZURE_CLIENT_SECRET")
    with pytest.raises(ValueError, match="AZURE_CLIENT_SECRET") as error:
        gateway("judge")
    assert "synthetic-subscription" not in str(error.value)


@pytest.mark.parametrize("status,expected_calls", [(429, 3), (400, 1)])
def test_judge_retries_only_transient_throttling(monkeypatch, status, expected_calls):
    from eval.phoenix.judges import common

    class ProviderError(Exception):
        status_code = status

    calls, waits = [], []

    def evaluate(payload):
        calls.append(payload)
        if len(calls) < 3:
            raise ProviderError("synthetic secret must not escape")
        return [SimpleNamespace(label="pass", score=1)]

    monkeypatch.setattr(
        common, "evaluator", lambda *args: SimpleNamespace(evaluate=evaluate)
    )
    monkeypatch.setattr(common.time, "sleep", waits.append)
    monkeypatch.setenv("JUDGE_MIN_INTERVAL_SECONDS", "0")
    if status == 429:
        assert (
            common.judge("test", "{input}", "pass", "fail", {"input": "ok"}).score == 1
        )
        assert waits == [10, 20]
    else:
        with pytest.raises(RuntimeError) as error:
            common.judge("test", "{input}", "pass", "fail", {"input": "ok"})
        assert "synthetic secret" not in str(error.value)
        assert not waits
    assert len(calls) == expected_calls
