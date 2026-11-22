"""Stdio MCP server with frozen HTTP replay; no model or live CDC access."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

if __package__ in (None, ""):
    sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from dotenv import load_dotenv

from eval.phoenix.data import SNAPSHOT, reference_for, verify_snapshot
from eval.replay import Replay
from resp_mcp.server import mcp

load_dotenv()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--case-id")
    args = parser.parse_args()
    verify_snapshot()
    ref = reference_for(args.case_id) if args.case_id else {}
    mcp.instructions += (
        " This session uses a frozen evaluation snapshot through 2026-10-31. "
        "Preserve the requested as_of cutoff. Missing recorded geography is "
        "unavailable, not evidence of zero activity."
    )
    with Replay(SNAPSHOT, ref.get("fail_sources", [])):
        # Explicit stdio ignores platform PORT and production transport settings.
        mcp.run(transport="stdio")


if __name__ == "__main__":
    main()
