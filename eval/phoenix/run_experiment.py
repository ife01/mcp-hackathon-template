"""Run a Phoenix experiment with agent traces, semantic judges and code checks."""

from __future__ import annotations

import argparse
import dataclasses
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

if __package__ in (None, ""):
    sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from dotenv import load_dotenv

from eval.phoenix.config import MODULE, phoenix_endpoint, validate_models
from eval.phoenix.data import load_dataset, source_identity

load_dotenv()


def validate_remote(dataset, rows):
    local = {r["case_id"]: r for r in rows}
    if len(dataset.examples) != len(rows):
        raise ValueError("Phoenix dataset size differs from the validated local CSV")
    seen = set()
    for example in dataset.examples:
        inputs, outputs = example["input"], example["output"]
        case_id = inputs.get("case_id")
        row = local.get(case_id)
        if row is None or case_id in seen:
            raise ValueError("Unrecognized or duplicate Phoenix case ID")
        seen.add(case_id)
        if (
            inputs.get("query") != row["query"]
            or outputs.get("responses") != row["responses"]
        ):
            raise ValueError(
                "Phoenix question/reference answer differs from validated CSV"
            )
        remote = outputs.get("reference")
        if (json.loads(remote) if isinstance(remote, str) else remote) != json.loads(
            row["reference"]
        ):
            raise ValueError(
                "Phoenix reference facts differ from validated local references"
            )


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--dataset-name", default="respiratory-eval-0")
    parser.add_argument(
        "--phoenix-name", help="Remote dataset name/ID if different from registry name"
    )
    parser.add_argument("--system-prompt-version", choices=("v1", "v2"), default="v2")
    parser.add_argument("--project-name", default="respiratory-eval")
    parser.add_argument("--phoenix-endpoint", default=phoenix_endpoint())
    parser.add_argument(
        "--experiment-description", default="Frozen-data respiratory agent evaluation"
    )
    parser.add_argument("--dataset-version-id")
    parser.add_argument("--repetitions", type=int, choices=(1, 2, 3), default=1)
    parser.add_argument(
        "--no-validate",
        action="store_true",
        help="Skip remote-vs-local CSV comparison, never "
        "snapshot integrity or credential checks",
    )
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()
    rows, info = load_dataset(args.dataset_name)
    identity = source_identity()
    if args.dry_run:
        print(
            json.dumps(
                {
                    "validation": "passed",
                    "model_calls": 0,
                    "uploaded": False,
                    "prompt_version": args.system_prompt_version,
                    "repetitions": args.repetitions,
                    **info,
                    **identity,
                },
                indent=2,
            )
        )
        return

    models = validate_models()  # Before contacting Phoenix or calling any model.
    from phoenix.client import Client

    from eval.phoenix.agent import RespiratoryAgent
    from eval.phoenix.judges import (
        check_answer_scope,
        check_public_health,
        match_expected_response,
    )
    from eval.phoenix.public_health_checks import (
        answer_anchor,
        argument_accuracy,
        evidence_integrity,
        numeric_grounding,
        tool_selection,
    )

    client = Client(base_url=args.phoenix_endpoint)
    dataset = client.datasets.get_dataset(
        dataset=args.phoenix_name or args.dataset_name,
        version_id=args.dataset_version_id,
    )
    if not args.no_validate:
        validate_remote(dataset, rows)
    collector = __import__("os").getenv(
        "PHOENIX_COLLECTOR_ENDPOINT", args.phoenix_endpoint + "/v1/traces"
    )
    agent = RespiratoryAgent(args.system_prompt_version, args.project_name, collector)
    agent.initialize()
    evaluators = {
        "answer_correctness": match_expected_response,
        "answer_scope": check_answer_scope,
        "public_health": check_public_health,
        "tool_action_coverage": tool_selection,
        "argument_validity": argument_accuracy,
        "answer_anchor": answer_anchor,
        "evidence_integrity": evidence_integrity,
        "numeric_support": numeric_grounding,
    }
    experiment = client.experiments.run_experiment(
        dataset=dataset,
        task=agent.create_experiment_task(),
        evaluators=evaluators,
        experiment_name=f"respiratory-{args.system_prompt_version}",
        experiment_description=args.experiment_description,
        experiment_metadata={
            **identity,
            **info,
            "models": models,
            "prompt_version": args.system_prompt_version,
            "validation_skipped": args.no_validate,
            "repetitions": args.repetitions,
        },
        repetitions=args.repetitions,
        retries=0,
        timeout=300,
    )
    # Flush spans before the process exits. Do not turn evaluator errors into passes.
    from eval.phoenix.agent import _TRACING

    if _TRACING:
        _TRACING[2].force_flush()
    errors = sum(bool(r.get("error")) for r in experiment["task_runs"])
    errors += sum(bool(r.error) for r in experiment["evaluation_runs"])
    result = {
        **experiment,
        "execution_errors": errors,
        "live_agent_evaluation": True,
        "recorded_at": datetime.now(timezone.utc).isoformat(),
    }
    folder = MODULE / "runs"
    folder.mkdir(exist_ok=True)
    path = folder / f"experiment-{experiment['experiment_id']}.json"
    path.write_text(
        json.dumps(
            result,
            indent=2,
            default=lambda x: (
                dataclasses.asdict(x) if dataclasses.is_dataclass(x) else str(x)
            ),
        )
        + "\n",
        encoding="utf-8",
    )
    print(
        json.dumps(
            {
                "experiment_id": experiment["experiment_id"],
                "execution_errors": errors,
                "repetitions": args.repetitions,
                "results": str(path),
            },
            indent=2,
        )
    )
    if errors:
        raise SystemExit(
            "Experiment has execution/judge errors; inspect "
            "Phoenix before reporting scores."
        )


if __name__ == "__main__":
    main()
