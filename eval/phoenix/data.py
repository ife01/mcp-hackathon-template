"""Dataset validation and evidence identity, independent of model configuration."""

from __future__ import annotations

import csv
import hashlib
import json
import xml.etree.ElementTree as ET
from pathlib import Path

import yaml
from dotenv import load_dotenv

from eval.phoenix.config import MODULE, ROOT

load_dotenv()
SNAPSHOT = ROOT / "eval" / "snapshot_v2"
REGISTRY = MODULE / "datasets.yaml"


def verify_snapshot(folder: Path = SNAPSHOT) -> str:
    path = folder / "capture_manifest.json"
    manifest = json.loads(path.read_bytes())
    if not manifest.get("complete") or not manifest.get("files"):
        raise ValueError("Snapshot is incomplete or has no file inventory")
    for name, info in manifest["files"].items():
        target = (folder / name).resolve()
        if target.parent != folder.resolve():
            raise ValueError("Unsafe snapshot manifest path")
        if hashlib.sha256(target.read_bytes()).hexdigest() != info["sha256"]:
            raise ValueError(f"Snapshot integrity mismatch: {name}")
    return hashlib.sha256(path.read_bytes()).hexdigest()


def source_identity() -> dict:
    def digest(paths):
        return hashlib.sha256(
            b"".join(
                p.relative_to(ROOT).as_posix().encode() + p.read_bytes()
                for p in sorted(paths)
            )
        ).hexdigest()

    return {
        "snapshot_manifest_sha256": verify_snapshot(),
        "server_source_sha256": digest((ROOT / "src").rglob("*.py")),
        "harness_source_sha256": digest((ROOT / "eval" / "phoenix").rglob("*.py")),
        "prompts_sha256": digest((MODULE / "prompts").glob("*.txt")),
        "reference_artifacts_sha256": digest(
            p
            for p in (MODULE / "datasets").rglob("*")
            if p.is_file() and p.suffix in (".json", ".csv", ".xml")
        ),
        "oracle_sha256": hashlib.sha256(
            (ROOT / "eval/ground_truth.py").read_bytes()
        ).hexdigest(),
    }


def registry() -> dict:
    return yaml.safe_load(REGISTRY.read_text(encoding="utf-8"))["datasets"]


def load_dataset(name: str, csv_path: Path | None = None) -> tuple[list[dict], dict]:
    entry = registry().get(name)
    if entry is None:
        raise ValueError("Unknown dataset; use --list")
    path = csv_path or MODULE / entry["csv_path"]
    with path.open(encoding="utf-8", newline="") as file:
        reader = csv.DictReader(file)
        if not {"case_id", "query", "responses", "reference"}.issubset(
            reader.fieldnames or []
        ):
            raise ValueError("CSV requires case_id, query, responses, reference")
        rows = list(reader)
    xml_path = MODULE / entry["xml_path"]
    pairs = {}
    for question in ET.parse(xml_path).getroot().findall("qa_pair"):
        case_id = question.attrib["id"]
        if case_id in pairs:
            raise ValueError(f"Duplicate XML evaluation case: {case_id}")
        pairs[case_id] = (question.findtext("question"), question.findtext("answer"))
    seen = set()
    expected_hash = verify_snapshot()
    for row in rows:
        case_id = row["case_id"]
        if case_id in seen or not row["query"].strip() or not row["responses"].strip():
            raise ValueError("Duplicate or empty evaluation case")
        seen.add(case_id)
        ref = json.loads(row["reference"])
        if pairs.get(case_id) != (row["query"], row["responses"]):
            raise ValueError(f"XML/CSV mismatch: {case_id}")
        if ref["snapshot_manifest_sha256"] != expected_hash:
            raise ValueError("Reference data identity differs from the frozen snapshot")
        if ref != reference_for(case_id):
            raise ValueError(
                "CSV reference differs from the independent reference artifact"
            )
        if ref["answer"] != row["responses"]:
            raise ValueError("Reference answer mismatch")
    if not rows:
        raise ValueError("Dataset is empty")
    if seen != set(pairs):
        raise ValueError("CSV must include every XML evaluation case exactly once")
    return rows, {
        "name": name,
        "rows": len(rows),
        "csv_sha256": hashlib.sha256(path.read_bytes()).hexdigest(),
        "snapshot_manifest_sha256": expected_hash,
    }


def reference_for(case_id: str) -> dict:
    path = MODULE / "datasets/respiratory-eval-0/references.json"
    refs = json.loads(path.read_text(encoding="utf-8"))
    if case_id not in refs:
        raise ValueError("Case ID is not in the frozen evaluation dataset")
    return refs[case_id]
