"""Validate the XML/CSV dataset, or explicitly upload it to Phoenix."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

if __package__ in (None, ""):
    sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from dotenv import load_dotenv

from eval.phoenix.config import phoenix_endpoint
from eval.phoenix.data import load_dataset, registry

load_dotenv()


def upload(name, phoenix_name=None, csv_path=None, endpoint=None):
    rows, info = load_dataset(name, csv_path)
    from phoenix.client import Client

    # Keep answers and references in outputs, hidden from the agent.
    dataset = Client(base_url=endpoint or phoenix_endpoint()).datasets.create_dataset(
        name=phoenix_name or name,
        examples=[
            {
                "input": {"query": r["query"], "case_id": r["case_id"]},
                "output": {"responses": r["responses"], "reference": r["reference"]},
                "metadata": {
                    "snapshot_manifest_sha256": info["snapshot_manifest_sha256"],
                    "csv_sha256": info["csv_sha256"],
                },
            }
            for r in rows
        ],
        dataset_description="Frozen CDC multi-tool respiratory evaluation; "
        "references are not agent inputs.",
    )
    return dataset, info


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--list", action="store_true")
    parser.add_argument("--dataset-name", default="respiratory-eval-0")
    parser.add_argument("--phoenix-name")
    parser.add_argument("--csv-path", type=Path)
    parser.add_argument("--phoenix-endpoint", default=phoenix_endpoint())
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()
    if args.list:
        print(json.dumps(registry(), indent=2))
        return
    if args.dry_run:
        _, info = load_dataset(args.dataset_name, args.csv_path)
        print(
            json.dumps(
                {"validation": "passed", "uploaded": False, "model_calls": 0, **info},
                indent=2,
            )
        )
        return
    dataset, info = upload(
        args.dataset_name, args.phoenix_name, args.csv_path, args.phoenix_endpoint
    )
    print(
        json.dumps(
            {
                "dataset_id": dataset.id,
                "dataset_version_id": dataset.version_id,
                **info,
            },
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
