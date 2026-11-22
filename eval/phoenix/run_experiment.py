"""CLI: run a Phoenix experiment against the respiratory eval dataset.

Run from repo root:
    uv run python eval/phoenix/run_experiment.py \\
        --dataset-name respiratory-eval-0 \\
        --dataset-version-id <VERSION_ID> \\
        --system-prompt-version v2 \\
        --repetitions 1
"""

from __future__ import annotations

import argparse
import logging
import sys
from pathlib import Path

from dotenv import load_dotenv

load_dotenv()
logging.basicConfig(level=logging.INFO, stream=sys.stderr)
logger = logging.getLogger(__name__)

PHOENIX_DIR = Path(__file__).parent


def _validate_env() -> list[str]:
    """Return a list of missing required env vars."""
    required = ["USAI_API_KEY", "USAI_BASE_URL", "AGENT_MODEL", "JUDGE_MODEL"]
    return [v for v in required if not __import__("os").getenv(v)]


def cmd_dry_run(args) -> None:  # noqa: ARG001
    """Validate imports and env without running anything."""
    missing = _validate_env()
    if missing:
        print(f"WARNING: missing env vars (needed for real run): {missing}", file=sys.stderr)
    else:
        print("All required env vars set.")

    # Check agent and judge imports
    try:
        sys.path.insert(0, str(PHOENIX_DIR))
        from agent import RespMcpAgent  # noqa: F401
        from judges import check_answer_scope, match_expected_response  # noqa: F401
        print("Agent and judge imports OK.")
    except Exception as exc:
        print(f"Import error: {exc}", file=sys.stderr)
        sys.exit(1)

    # Validate dataset YAML
    import yaml
    registry = yaml.safe_load((PHOENIX_DIR / "datasets.yaml").read_text())["datasets"]
    name = args.dataset_name or "respiratory-eval-0"
    if name not in registry:
        print(f"ERROR: '{name}' not in datasets.yaml", file=sys.stderr)
        sys.exit(1)
    import pandas as pd
    csv_path = PHOENIX_DIR / registry[name]["csv_path"]
    df = pd.read_csv(csv_path)
    print(f"Dataset '{name}': {len(df)} rows — OK")
    print("Dry run complete.")


def cmd_run(args) -> None:
    """Run the full experiment."""
    missing = _validate_env()
    if missing and not args.no_validate:
        print(
            f"ERROR: missing env vars: {missing}. "
            "Set them in .env or pass --no-validate to skip.",
            file=sys.stderr,
        )
        sys.exit(1)

    sys.path.insert(0, str(PHOENIX_DIR))
    from agent import RespMcpAgent
    from judges import check_answer_scope, match_expected_response

    phoenix_endpoint = args.phoenix_endpoint

    import phoenix as px
    client = px.Client(endpoint=phoenix_endpoint)

    # Load dataset
    dataset = client.get_dataset(name=args.dataset_name)
    if args.dataset_version_id:
        dataset = client.get_dataset(
            name=args.dataset_name,
            version_id=args.dataset_version_id,
        )

    logger.info(
        "Running experiment on dataset '%s' (%d examples), prompt=%s, reps=%d",
        args.dataset_name,
        len(dataset),
        args.system_prompt_version,
        args.repetitions,
    )

    # Initialize the agent (runs MCP server initialization)
    agent = RespMcpAgent(
        system_prompt_version=args.system_prompt_version,
        project_name=args.project_name,
        phoenix_endpoint=phoenix_endpoint,
    )
    task = agent.create_experiment_task()

    description = args.experiment_description or (
        f"prompt={args.system_prompt_version}, "
        f"agent={__import__('os').getenv('AGENT_MODEL','?')}, "
        f"judge={__import__('os').getenv('JUDGE_MODEL','?')}"
    )

    experiment = client.run_experiment(
        dataset=dataset,
        task=task,
        evaluators=[check_answer_scope, match_expected_response],
        experiment_description=description,
        repetitions=args.repetitions,
    )

    print("\nExperiment complete.")
    print(f"  Experiment ID: {experiment.id}")
    print(f"  View at: {phoenix_endpoint}/experiments/{experiment.id}")
    print("\nSummary:")
    try:
        summary = experiment.get_evaluations()
        if summary is not None:
            print(summary.to_string())
    except Exception:
        print("  (see Phoenix UI for detailed results)")


def main() -> None:
    parser = argparse.ArgumentParser(description="Run a Phoenix respiratory eval experiment")
    parser.add_argument(
        "--dataset-name", default="respiratory-eval-0",
        help="Dataset name in Phoenix"
    )
    parser.add_argument("--dataset-version-id", help="Specific dataset version ID to use")
    parser.add_argument(
        "--system-prompt-version", choices=["v1", "v2"], default="v2",
        help="System prompt version"
    )
    parser.add_argument(
        "--project-name", default="respiratory-mcp-eval",
        help="Phoenix project name for traces"
    )
    parser.add_argument(
        "--phoenix-endpoint", default="http://localhost:6006",
        help="Phoenix server URL"
    )
    parser.add_argument("--experiment-description", help="Human-readable experiment description")
    parser.add_argument(
        "--repetitions", type=int, default=1,
        help="Number of times to run each example (1 for initial, 3 for stability)"
    )
    parser.add_argument(
        "--dry-run", action="store_true",
        help="Validate imports and env without running"
    )
    parser.add_argument(
        "--no-validate", action="store_true",
        help="Skip env var validation check"
    )
    args = parser.parse_args()

    if args.dry_run:
        cmd_dry_run(args)
    else:
        cmd_run(args)


if __name__ == "__main__":
    main()
