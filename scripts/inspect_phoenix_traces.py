"""Check local trace persistence and detect credentials without printing them."""

import argparse
import json
import re
import sys
from pathlib import Path
from urllib.parse import urlsplit

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from dotenv import dotenv_values

from eval.phoenix.config import ROOT


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--endpoint", default="http://127.0.0.1:16006")
    parser.add_argument("--project")
    args = parser.parse_args()
    if urlsplit(args.endpoint).hostname not in ("localhost", "127.0.0.1", "::1"):
        raise ValueError("This inspection targets a local Phoenix instance only")
    from phoenix.client import Client

    project = args.project
    if not project:
        files = list((ROOT / "eval/phoenix/runs").glob("experiment-*.json"))
        if not files:
            raise SystemExit("Specify a project or complete an experiment first.")
        latest = max(files, key=lambda p: p.stat().st_mtime)
        project = json.loads(latest.read_text())["project_name"]
    frame = Client(base_url=args.endpoint).spans.get_spans_dataframe(
        project_identifier=project
    )
    if frame.empty:
        raise SystemExit("No persisted spans found for the selected project.")
    serialized = frame.to_json(date_format="iso")
    values = dotenv_values(ROOT / ".env", interpolate=False)
    hits = [
        name
        for name, value in values.items()
        if value
        and any(word in name for word in ("SECRET", "KEY", "TENANT", "CLIENT_ID"))
        and value in serialized
    ]
    jwt = bool(
        re.search(
            r"eyJ[A-Za-z0-9_-]{20,}\.[A-Za-z0-9_-]{20,}\.[A-Za-z0-9_-]{20,}", serialized
        )
    )
    if hits or jwt:
        raise SystemExit("Possible credential exposure in local spans; do not export.")
    stats = {"persisted_spans": len(frame), "credential_matches": 0}
    kind = "attributes.openinference.span.kind"
    llm = frame[frame[kind] == "LLM"] if kind in frame else frame.iloc[:0]
    for name in ("prompt", "completion", "total"):
        column = "attributes.llm.token_count." + name
        if column in llm:
            stats["traced_llm_tokens_" + name] = int(llm[column].fillna(0).sum())
    print(json.dumps(stats, indent=2))


if __name__ == "__main__":
    main()
