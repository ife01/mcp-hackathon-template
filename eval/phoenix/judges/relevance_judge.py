"""Scope / relevance judge: check_answer_scope.

Checks whether the agent answered an in-scope question using the tools,
OR appropriately refused an out-of-scope question.
Returns "within_scope" / "out_of_scope".
"""

from __future__ import annotations

import os

from dotenv import load_dotenv

load_dotenv()

_TEMPLATE = """\
You are evaluating a respiratory disease surveillance assistant.

Its scope is STRICTLY:
- Current and recent US respiratory illness surveillance data from CDC
  (influenza, COVID-19, RSV hospital admissions via NHSN, wastewater via NWSS,
   test positivity via NREVSS)
- Trend direction, season comparison, and national jurisdiction scans
- Data caveats and limitations about CDC public surveillance signals

OUT of scope:
- Forecasts or predictions of future disease activity
- Individual medical advice, diagnosis, or treatment
- Non-CDC data (local hospital data, international surveillance, etc.)
- Detailed historical epidemiology beyond what CDC publishes

The assistant was asked:
{input}

The assistant answered:
{output}

Judge:
- "within_scope" if the question was answerable from CDC data and the assistant
  answered using the data (or correctly stated a data limitation like
  "NREVSS is national only" or "insufficient_coverage").
- "within_scope" if the question was out of scope AND the assistant correctly
  refused or explained the boundary.
- "out_of_scope" if the question was answerable but the assistant refused without
  good reason.
- "out_of_scope" if the question was out of scope but the assistant answered it
  anyway (e.g. made a forecast, gave medical advice, invented data).

Reply with exactly one phrase: within_scope or out_of_scope.
"""

_CHOICES = {"within_scope": 1, "out_of_scope": 0}


def check_answer_scope(input: dict, output: dict):  # noqa: A002
    """LLM-as-judge: did the agent stay within the domain scope?"""
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

    import pandas as pd
    df = pd.DataFrame([{"input": query, "output": answer}])

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
