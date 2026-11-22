"""Inventory actual frozen coverage and file hashes; never infer completeness."""

from __future__ import annotations

import argparse
import gzip
import hashlib
import json
from collections import defaultdict
from pathlib import Path


def audit(folder: Path) -> dict:
    files = {}
    for path in sorted(folder.glob("*.json*")):
        if path.name.endswith("manifest.json"):
            continue
        rows = json.loads(
            gzip.decompress(path.read_bytes())
            if path.suffix == ".gz"
            else path.read_bytes()
        )
        if not isinstance(rows, list):
            continue
        groups = defaultdict(set)
        for row in rows:
            groups[row.get("pathogen_target", row.get("pathogen", "all"))].add(
                row.get("weekendingdate", row.get("week_end", ""))[:10]
            )
        files[path.name] = {
            "sha256": hashlib.sha256(path.read_bytes()).hexdigest(),
            "rows": len(rows),
            "coverage": {
                key: {"weeks": len(dates), "first": min(dates), "last": max(dates)}
                for key, dates in sorted(groups.items())
            },
        }
    return {
        "files": files,
        "warning": (
            "Counts describe stored rows only. They do not prove complete retrieval, "
            "source finalization, or population representativeness."
        ),
    }


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("folder", nargs="?", type=Path, default=Path("eval/snapshot"))
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    result = audit(args.folder)
    text = json.dumps(result, indent=2) + "\n"
    if args.output:
        args.output.write_text(text, encoding="utf-8")
    else:
        print(text)
