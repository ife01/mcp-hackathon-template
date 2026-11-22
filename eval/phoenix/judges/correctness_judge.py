"""Correctness judge: match_expected_response.

Compares the agent's answer to the ground-truth reference.
Returns "correct" / "incorrect".
"""

from __future__ import annotations

import os

from dotenv import load_dotenv

load_dotenv()

_TEMPLATE = """\
You are evaluating a respiratory disease surveillance assistant that answers
questions about CDC public health data.

The assistant was asked:
{input}

The assistant answered:
{output}

The reference (ground truth) answer is:
{reference}

Scoring rules:
- Mark CORRECT if the assistant's answer contains the key factual claims from the
  reference answer. Allow reasonable formatting differences (units written out vs
  abbreviated, slight rounding within 5%, extra context or caveats).
- Mark CORRECT if the assistant appropriately abstains when the reference answer
  indicates the question is unanswerable (e.g. scope boundary, missing data).
- Mark INCORRECT if the assistant states a materially wrong number, attributes
  national data to a specific state as state-level data, presents a server-computed
  aggregate as an official CDC classification, makes a forecast or prediction,
  omits a critical caveat explicitly stated in the reference, or answers an
  unanswerable question with invented data.
- Do NOT penalise for extra correct context, different word order, or minor phrasing
  differences that do not change the factual meaning.

Reply with exactly one word: correct or incorrect.
"""

_CHOICES = {"correct": 1, "incorrect": 0}


def match_expected_response(input: dict, output: dict, expected: dict):  # noqa: A002
    """LLM-as-judge: is the agent's answer factually correct per the reference?"""
    from phoenix.evals import ClassificationTemplate, LiteLLMModel, llm_classify

    base_url = os.environ["USAI_BASE_URL"].rstrip("/")
    if not base_url.endswith("/api/v1"):
        base_url = f"{base_url}/api/v1"

    judge_model = LiteLLMModel(
        model=f"openai/{os.environ['JUDGE_MODEL']}",
        api_key=os.getenv("JUDGE_API_KEY", os.environ["USAI_API_KEY"]),
        base_url=os.getenv("JUDGE_BASE_URL", base_url),
        temperature=0.0,
    )

    query = input.get("query", "") if isinstance(input, dict) else str(input)
    answer = output.get("output", str(output)) if isinstance(output, dict) else str(output)
    reference = expected.get("responses", str(expected)) if isinstance(expected, dict) else str(expected)

    import pandas as pd
    df = pd.DataFrame([{
        "input": query,
        "output": answer,
        "reference": reference,
    }])

    template = ClassificationTemplate(
        rails=list(_CHOICES.keys()),
        template=_TEMPLATE,
        explanation_template=None,
    )

    result = llm_classify(
        dataframe=df,
        template=template,
        model=judge_model,
        rails=list(_CHOICES.keys()),
        provide_explanation=False,
    )
    label = result["label"].iloc[0]
    return _CHOICES.get(label, 0)
