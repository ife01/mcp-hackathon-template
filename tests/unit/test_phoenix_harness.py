"""Credential-free evaluation contract and public health grading regressions."""

import csv
import hashlib
import json
import subprocess
import xml.etree.ElementTree as ET
from types import SimpleNamespace

import pytest

from eval.phoenix.config import ROOT, Gateway, api_url, gateway
from eval.phoenix.data import load_dataset, reference_for, verify_snapshot
from eval.phoenix.public_health_checks import (
    answer_anchor,
    argument_accuracy,
    evidence_integrity,
    hard_checks,
    numeric_grounding,
    tool_selection,
)
from eval.phoenix.run_experiment import validate_remote


@pytest.fixture
def example():
    rows, _ = load_dataset("respiratory-eval-0")
    row = next(r for r in rows if r["case_id"] == "P01")
    expected = {"responses": row["responses"], "reference": row["reference"]}
    calls = []
    for name in ("A1", "A2"):
        raw = json.loads((ROOT / f"eval/transcripts/tools/{name}.json").read_bytes())[
            "calls"
        ][0]
        calls.append(
            {
                "id": name,
                "name": raw["tool"],
                "arguments": raw["arguments"],
                "status": "completed",
                "output": raw["output"],
            }
        )
    output = {
        "answer": "Answer: " + row["responses"],
        "tool_calls": calls,
        "snapshot_manifest_sha256": reference_for("P01")["snapshot_manifest_sha256"],
    }
    return row, expected, output


@pytest.mark.parametrize(
    "base,path,wanted",
    [
        ("https://gateway.example", "/api/v1", "https://gateway.example/api/v1"),
        (
            "https://gateway.example/api/v1/",
            "/api/v1",
            "https://gateway.example/api/v1",
        ),
        ("https://gateway.example/v1", "/api/v1", "https://gateway.example/v1"),
        (
            "https://resource.example/openai/v1/",
            "/api/v1",
            "https://resource.example/openai/v1",
        ),
        ("http://127.0.0.1:9191", "/v1", "http://127.0.0.1:9191/v1"),
    ],
)
def test_gateway_api_path(base, path, wanted):
    assert api_url(base, path) == wanted


@pytest.mark.parametrize(
    "base",
    [
        "http://remote.example",
        "https://user:secret@api.example",
        "https://api.example?key=secret",
        "https://api.example/v1/chat/completions",
    ],
)
def test_invalid_gateway_configuration_rejected(base):
    with pytest.raises(ValueError):
        api_url(base)


def test_gateway_secret_not_in_repr():
    assert "secret-123" not in repr(
        Gateway("https://example/v1", "model", "secret-123")
    )


def test_separate_agent_judge_models_and_optional_credentials(monkeypatch):
    for key, value in {
        "USAI_BASE_URL": "https://example/v1",
        "USAI_API_KEY": "agent-secret",
        "AGENT_MODEL": "agent-model",
        "JUDGE_MODEL": "judge-model",
        "JUDGE_API_KEY": "judge-secret",
        "JUDGE_BASE_URL": "https://judge.example/v1",
    }.items():
        monkeypatch.setenv(key, value)
    assert gateway("agent").model == "agent-model"
    assert gateway("judge").model == "judge-model"
    assert gateway("judge").api_key == "judge-secret"
    assert gateway("agent").api_key == "agent-secret"


def test_dataset_requires_no_gateway_and_keeps_answers_out_of_inputs(monkeypatch):
    for key in ("USAI_API_KEY", "USAI_BASE_URL", "AGENT_MODEL", "JUDGE_MODEL"):
        monkeypatch.delenv(key, raising=False)
    rows, info = load_dataset("respiratory-eval-0")
    assert len(rows) == 15
    assert len({r["case_id"] for r in rows}) == 15
    assert info["snapshot_manifest_sha256"] == verify_snapshot()
    assert all(
        len(json.loads(r["reference"])["required_tool_groups"]) >= 2 for r in rows[:10]
    )


def test_tampered_snapshot_fails(tmp_path):
    data = tmp_path / "slice.json.gz"
    data.write_bytes(b"original")
    (tmp_path / "capture_manifest.json").write_text(
        json.dumps(
            {
                "complete": True,
                "files": {
                    "slice.json.gz": {"sha256": hashlib.sha256(b"original").hexdigest()}
                },
            }
        )
    )
    verify_snapshot(tmp_path)
    data.write_bytes(b"tampered")
    with pytest.raises(ValueError, match="integrity"):
        verify_snapshot(tmp_path)


def test_incomplete_benchmark_cannot_be_uploaded_as_full_dataset(tmp_path):
    rows, _ = load_dataset("respiratory-eval-0")
    path = tmp_path / "incomplete.csv"
    with path.open("w", encoding="utf-8", newline="") as file:
        writer = csv.DictWriter(file, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows[:-1])
    with pytest.raises(ValueError, match="every XML evaluation case"):
        load_dataset("respiratory-eval-0", csv_path=path)


def test_duplicate_xml_cases_rejected(tmp_path, monkeypatch):
    from eval.phoenix import data

    entries = data.registry()
    entry = entries["respiratory-eval-0"]
    tree = ET.parse(data.MODULE / entry["xml_path"])
    tree.getroot().append(tree.getroot().find("qa_pair"))
    path = tmp_path / "duplicates.xml"
    tree.write(path, encoding="utf-8")
    entry["xml_path"] = str(path)
    monkeypatch.setattr(data, "registry", lambda: entries)
    with pytest.raises(ValueError, match="Duplicate XML evaluation case"):
        data.load_dataset("respiratory-eval-0")


@pytest.mark.parametrize("autocrlf", ["false", "true", "input"])
def test_frozen_manifest_survives_git_line_ending_settings(autocrlf):
    name = "eval/snapshot_v2/capture_manifest.json"
    # Exercise Git's actual clean filter, not a simulated newline replacement.
    result = subprocess.check_output(
        [
            "git",
            "-c",
            f"core.autocrlf={autocrlf}",
            "hash-object",
            f"--path={name}",
            name,
        ],
        cwd=ROOT,
        text=True,
    ).strip()
    raw = (ROOT / name).read_bytes()
    expected = hashlib.sha1(f"blob {len(raw)}\0".encode() + raw).hexdigest()
    assert result == expected


def test_remote_dataset_drift_rejected():
    rows, _ = load_dataset("respiratory-eval-0")
    examples = [
        {
            "input": {"query": r["query"], "case_id": r["case_id"]},
            "output": {"responses": r["responses"], "reference": r["reference"]},
        }
        for r in rows
    ]
    validate_remote(SimpleNamespace(examples=examples), rows)
    examples[0]["output"]["responses"] = "wrong"
    with pytest.raises(ValueError, match="differs"):
        validate_remote(SimpleNamespace(examples=examples), rows)


def test_valid_reference_evidence_passes_hard_checks(example):
    _, expected, output = example
    assert all(item["score"] == 1 for item in hard_checks(output, expected).values())


def test_missing_second_jurisdiction_cannot_pass_selection(example):
    _, expected, output = example
    output["tool_calls"] = output["tool_calls"][:1]
    assert tool_selection(output, expected)["score"] == 0.5


def test_full_state_name_is_a_valid_argument_alternative(example):
    _, expected, output = example
    output["tool_calls"][0]["arguments"]["jurisdiction"] = "Georgia"
    assert tool_selection(output, expected)["score"] == 1


def test_wrong_cutoff_fails_argument_check(example):
    _, expected, output = example
    output["tool_calls"][0]["arguments"]["as_of"] = "2026-10-24"
    assert argument_accuracy(output, expected)["score"] < 1


@pytest.mark.parametrize(
    "field,value",
    [("value", 999999), ("jurisdiction", "USA"), ("week_ending", "2026-10-24")],
)
def test_wrong_numeric_geographic_or_temporal_evidence_fails(example, field, value):
    _, expected, output = example
    output["tool_calls"][0]["output"]["series"][-1][field] = value
    assert evidence_integrity(output, expected)["score"] == 0


def test_scripted_verification_cannot_be_reported_as_benchmark(example):
    _, expected, output = example
    output["verification_only"] = True
    assert evidence_integrity(output, expected)["score"] == 0


def test_ungrounded_number_is_not_supported(example):
    _, expected, output = example
    output["answer"] += "\nThe rate was 987654321."
    assert numeric_grounding(output, expected)["score"] == 0


def test_public_health_gate_fails_without_spending_judge_call(example, monkeypatch):
    from eval.phoenix.judges import public_health_judge

    _, expected, output = example
    output["tool_calls"] = []
    monkeypatch.setattr(
        public_health_judge,
        "judge",
        lambda *a: pytest.fail("Must not call judge after hard failure"),
    )
    assert (
        public_health_judge.check_public_health({"query": "q"}, output, expected)[
            "score"
        ]
        == 0
    )


def test_scope_refusal_does_not_require_wasted_tool_call():
    ref = reference_for("P13")
    expected = {"responses": ref["answer"], "reference": ref}
    output = {
        "answer": "Answer: Not determinable",
        "tool_calls": [],
        "snapshot_manifest_sha256": ref["snapshot_manifest_sha256"],
    }
    assert tool_selection(output, expected)["score"] is None
    assert argument_accuracy(output, expected)["score"] is None
    assert answer_anchor(output, expected)["score"] == 1


def test_supplemental_outage_is_explicit_not_inferred_from_question():
    ref = reference_for("P11")
    assert set(ref["fail_sources"]) == {"vdzy-6i9v", "atcp-73re", "seuz-s2cv"}
    assert reference_for("P01").get("fail_sources", []) == []


@pytest.mark.asyncio
async def test_real_chat_client_uses_configured_gateway_without_network():
    import httpx
    import respx
    from langchain_openai import ChatOpenAI

    payloads = []

    def respond(request):
        payloads.append(json.loads(request.content))
        return httpx.Response(
            200,
            json={
                "id": "verification",
                "object": "chat.completion",
                "created": 0,
                "model": "verification-agent",
                "choices": [
                    {
                        "index": 0,
                        "finish_reason": "stop",
                        "message": {"role": "assistant", "content": "okay"},
                    }
                ],
            },
        )

    with respx.mock(assert_all_mocked=True) as router:
        router.post("https://gateway.example/v1/chat/completions").mock(
            side_effect=respond
        )
        async with httpx.AsyncClient(trust_env=False) as client:
            model = ChatOpenAI(
                model="verification-agent",
                api_key="unit-test-key",
                base_url="https://gateway.example/v1",
                temperature=0,
                max_retries=0,
                use_responses_api=False,
                http_async_client=client,
                timeout=5,
            )
            response = await model.ainvoke("Return okay")
    assert response.content == "okay"
    assert payloads[0]["model"] == "verification-agent"
    assert payloads[0]["temperature"] == 0


@pytest.mark.asyncio
async def test_real_phoenix_judge_client_and_classification_contract(monkeypatch):
    import httpx
    import respx

    from eval.phoenix.judges import common

    common.evaluator.cache_clear()
    monkeypatch.setattr(
        common,
        "gateway",
        lambda role: Gateway(
            "https://judge.example/v1", "verification-judge", "unit-test-key", 5
        ),
    )
    with respx.mock(assert_all_mocked=True) as router:
        router.post("https://judge.example/v1/chat/completions").mock(
            return_value=httpx.Response(
                200,
                json={
                    "id": "judge-verification",
                    "object": "chat.completion",
                    "created": 0,
                    "model": "verification-judge",
                    "choices": [
                        {
                            "index": 0,
                            "finish_reason": "stop",
                            "message": {
                                "role": "assistant",
                                "content": json.dumps(
                                    {
                                        "label": "pass",
                                        "explanation": "Synthetic protocol check",
                                    }
                                ),
                            },
                        }
                    ],
                },
            )
        )
        evaluator = common.evaluator(
            "test_contract", "Question: {input}", "pass", "fail"
        )
        result = evaluator.evaluate({"input": "synthetic"})
        assert result[0].label == "pass" and result[0].score == 1
        evaluator.llm._sync_client.close()
        await evaluator.llm._async_client.close()
    common.evaluator.cache_clear()
