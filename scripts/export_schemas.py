#!/usr/bin/env python3
"""Export JSON schemas for all tool I/O models to docs/schemas/.

Run with:  uv run python scripts/export_schemas.py

Outputs:
  docs/schemas/snapshot_input.json
  docs/schemas/snapshot_output.json
  docs/schemas/trend_input.json
  docs/schemas/trend_output.json
  docs/schemas/season_input.json
  docs/schemas/season_output.json
  docs/schemas/scan_input.json
  docs/schemas/scan_output.json
"""

from __future__ import annotations

import asyncio
import json
from pathlib import Path

from resp_mcp.models.tool_io import (
    ScanInput,
    ScanOutput,
    SeasonInput,
    SeasonOutput,
    SnapshotInput,
    SnapshotOutput,
    TrendInput,
    TrendOutput,
)

SCHEMA_DIR = Path("docs/schemas")
SCHEMA_DIR.mkdir(parents=True, exist_ok=True)

_MODELS = [
    ("snapshot_input", SnapshotInput),
    ("snapshot_output", SnapshotOutput),
    ("trend_input", TrendInput),
    ("trend_output", TrendOutput),
    ("season_input", SeasonInput),
    ("season_output", SeasonOutput),
    ("scan_input", ScanInput),
    ("scan_output", ScanOutput),
]

for name, model in _MODELS:
    schema = model.model_json_schema(
        mode="serialization" if name.endswith("_output") else "validation"
    )
    out = SCHEMA_DIR / f"{name}.json"
    out.write_text(json.dumps(schema, indent=2) + "\n", encoding="utf-8")
    print(f"  wrote {out}")

print(f"\nExported {len(_MODELS)} schemas to {SCHEMA_DIR}/")


async def export_registered():
    from resp_mcp.server import mcp

    registered = {
        tool.name: {"description": tool.description, "inputSchema": tool.parameters}
        for tool in await mcp.list_tools()
    }
    (SCHEMA_DIR / "mcp_tools.json").write_text(
        json.dumps(registered, indent=2) + "\n", encoding="utf-8"
    )


asyncio.run(export_registered())
