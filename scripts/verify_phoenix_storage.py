"""Explicit local Phoenix storage check with no agent/model scores."""

import argparse
import json
import sys
import uuid
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from eval.phoenix.create_dataset import upload
from eval.phoenix.data import load_dataset
from eval.phoenix.run_experiment import validate_remote


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--endpoint", default="http://127.0.0.1:16006")
    args = parser.parse_args()
    from urllib.parse import urlsplit

    if urlsplit(args.endpoint).hostname not in ("127.0.0.1", "localhost", "::1"):
        raise ValueError("This verification helper only writes to loopback Phoenix.")
    from phoenix.client import Client

    name = "respiratory-storage-verification-" + uuid.uuid4().hex[:8]
    dataset, info = upload("respiratory-eval-0", name, endpoint=args.endpoint)
    client = Client(base_url=args.endpoint)
    reloaded = client.datasets.get_dataset(
        dataset=dataset.id, version_id=dataset.version_id
    )
    validate_remote(reloaded, load_dataset("respiratory-eval-0")[0])

    def task(example):
        return {
            "case_id": example.input["case_id"],
            "verification_only": True,
            "answer": "Storage contract verification, no model was called.",
        }

    def verification_only(output):
        assert output["verification_only"]
        return {"label": "verification_only", "explanation": "No model score."}

    result = client.experiments.run_experiment(
        dataset=reloaded,
        task=task,
        evaluators={"storage_contract": verification_only},
        experiment_name="verification-only-no-model-scores",
        experiment_metadata={"verification_only": True, "contains_model_scores": False},
        retries=0,
        print_summary=False,
    )
    assert len(result["task_runs"]) == 15
    assert not any(r.get("error") for r in result["task_runs"])
    assert not any(r.error for r in result["evaluation_runs"])
    print(
        json.dumps(
            {
                "phoenix_storage": "passed",
                "cases": info["rows"],
                "dataset_id": dataset.id,
                "dataset_version_id": dataset.version_id,
                "experiment_id": result["experiment_id"],
                "model_calls": 0,
                "contains_model_scores": False,
            },
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
