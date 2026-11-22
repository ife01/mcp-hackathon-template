"""CLI: upload a CSV dataset to Phoenix (or validate it with --dry-run).

Run from repo root:
    uv run python eval/phoenix/create_dataset.py --dataset-name respiratory-eval-0
    uv run python eval/phoenix/create_dataset.py --dataset-name respiratory-eval-0 --dry-run
    uv run python eval/phoenix/create_dataset.py --list
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

import yaml
from dotenv import load_dotenv

load_dotenv()

PHOENIX_DIR = Path(__file__).parent
DATASETS_YAML = PHOENIX_DIR / "datasets.yaml"


def _load_registry() -> dict:
    return yaml.safe_load(DATASETS_YAML.read_text())["datasets"]


def _resolve_csv(registry_entry: dict) -> Path:
    """Resolve the csv_path relative to the eval/phoenix/ directory."""
    return PHOENIX_DIR / registry_entry["csv_path"]


def cmd_list(args) -> None:  # noqa: ARG001
    registry = _load_registry()
    print(f"{'Name':<30}  {'Description'}")
    print("-" * 70)
    for name, entry in registry.items():
        desc = entry.get("description", "").strip().replace("\n", " ")[:60]
        print(f"{name:<30}  {desc}")


def cmd_upload(args) -> None:
    import pandas as pd

    registry = _load_registry()
    name = args.dataset_name

    if name not in registry:
        print(f"ERROR: dataset '{name}' not in datasets.yaml. Use --list to see options.",
              file=sys.stderr)
        sys.exit(1)

    entry = registry[name]
    csv_path = _resolve_csv(entry)
    if not csv_path.exists():
        print(f"ERROR: CSV not found at {csv_path}", file=sys.stderr)
        sys.exit(1)

    df = pd.read_csv(csv_path)
    input_keys = entry.get("input_keys", ["query"])
    output_keys = entry.get("output_keys", ["responses"])
    required = set(input_keys) | set(output_keys)
    missing = required - set(df.columns)
    if missing:
        print(f"ERROR: CSV missing columns: {missing}", file=sys.stderr)
        sys.exit(1)

    print(f"Dataset '{name}': {len(df)} rows, columns: {list(df.columns)}")

    if args.dry_run:
        print("Dry run: validation passed. No data uploaded.")
        return

    # Upload to Phoenix
    phoenix_name = args.phoenix_name or name
    phoenix_endpoint = args.phoenix_endpoint

    import phoenix as px
    client = px.Client(endpoint=phoenix_endpoint)
    dataset = client.upload_dataset(
        dataframe=df,
        dataset_name=phoenix_name,
        input_keys=input_keys,
        output_keys=output_keys,
    )
    print(f"Uploaded dataset: name={dataset.name}")
    print(f"  Dataset ID:      {dataset.id}")
    version_id = getattr(dataset, "version_id", None) or getattr(dataset, "id", None)
    print(f"  Version ID:      {version_id}")
    print("\nRecord this version ID for use with run_experiment.py:")
    print(f"  --dataset-version-id {version_id}")


def main() -> None:
    parser = argparse.ArgumentParser(description="Manage Phoenix evaluation datasets")
    parser.add_argument("--list", action="store_true", help="List registered datasets")
    parser.add_argument("--dataset-name", help="Dataset name (from datasets.yaml)")
    parser.add_argument("--phoenix-name", help="Override name in Phoenix (default: dataset-name)")
    parser.add_argument("--csv-path", help="Override CSV path")
    parser.add_argument(
        "--phoenix-endpoint", default="http://localhost:6006",
        help="Phoenix server URL (default: http://localhost:6006)"
    )
    parser.add_argument(
        "--dry-run", action="store_true",
        help="Validate CSV without uploading"
    )
    args = parser.parse_args()

    if args.list:
        cmd_list(args)
    elif args.dataset_name:
        cmd_upload(args)
    else:
        parser.print_help()
        sys.exit(1)


if __name__ == "__main__":
    main()
