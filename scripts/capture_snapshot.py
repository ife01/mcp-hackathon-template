"""Capture paginated public CDC data into a NEW evaluation snapshot directory.

Run only when network access is intended. Existing frozen evidence is preserved.
"""

from __future__ import annotations

import argparse
import asyncio
import gzip
import json
from datetime import date, datetime, timedelta, timezone
from pathlib import Path

from audit_snapshot import audit

from resp_mcp.clients.socrata import (
    metadata,
    query,
    soql_and,
    soql_eq,
    soql_gte,
    soql_lte,
)


async def capture(start: date, end: date, output: Path) -> None:
    if output.exists():
        raise ValueError(
            "Choose a new output directory; frozen evidence is never overwritten."
        )
    output.mkdir(parents=True)
    manifest = {
        "as_of": end.isoformat(),
        "requested_start": start.isoformat(),
        "retrieved_at": datetime.now(timezone.utc).isoformat(),
        "complete": False,
        "semantics": "Week-ending cutoff using data retrieved now; not an as-published "
        "vintage.",
        "sources": {},
    }
    try:
        for source, dataset, column in [
            ("nhsn", "vdzy-6i9v", "weekendingdate"),
            ("nrevss", "seuz-s2cv", "week_end"),
        ]:
            meta = await metadata(dataset)
            columns = {c["fieldName"] for c in meta["columns"]}
            if column not in columns:
                raise ValueError(f"Required date column missing from {dataset}")
            manifest["sources"][source] = {
                "dataset_id": dataset,
                "rowsUpdatedAt": meta.get("rowsUpdatedAt"),
            }
            rows = await query(
                dataset,
                where=soql_and(
                    soql_gte(column, start.isoformat()),
                    soql_lte(column, end.isoformat()),
                ),
                order=f"{column} ASC",
            )
            if source == "nhsn":
                for code in ["GA", "CA", "OH", "TX", "USA", "PR"]:
                    save(
                        output / f"nhsn_{code.lower()}.json",
                        [r for r in rows if r.get("jurisdiction") == code],
                    )
                save(
                    output / "nhsn_scan_national.json",
                    [
                        r
                        for r in rows
                        if r.get(column, "")[:10]
                        >= (end - timedelta(weeks=8)).isoformat()
                    ],
                )
            else:
                save(output / "nrevss_national.json", rows)
            print(f"Captured {source}: {len(rows)} rows", flush=True)
        meta = await metadata("atcp-73re")
        manifest["sources"]["nwss"] = {
            "dataset_id": "atcp-73re",
            "rowsUpdatedAt": meta.get("rowsUpdatedAt"),
        }
        required = {
            "week_end",
            "state_territory",
            "site",
            "site_wval",
            "pathogen_target",
        }
        if not required.issubset({c["fieldName"] for c in meta["columns"]}):
            raise ValueError("NWSS schema changed; inspect metadata before capture")
        for state in ["Georgia", "California", "Ohio", "Texas"]:
            rows = []
            cursor = start
            while cursor <= end:
                stop = min(cursor + timedelta(weeks=26) - timedelta(days=1), end)
                rows.extend(
                    await query(
                        "atcp-73re",
                        where=soql_and(
                            soql_eq("state_territory", state),
                            soql_gte("week_end", cursor.isoformat()),
                            soql_lte("week_end", stop.isoformat()),
                        ),
                        order="week_end ASC, pathogen_target ASC, site ASC",
                    )
                )
                cursor = stop + timedelta(days=1)
            save(output / f"nwss_{state.lower()}.json", rows)
            print(f"Captured NWSS {state}: {len(rows)} rows", flush=True)
        manifest.update(audit(output))
        manifest["complete"] = True
    finally:
        save(output / "capture_manifest.json", manifest)


def save(path: Path, value) -> None:
    if isinstance(value, list):
        path.with_suffix(".json.gz").write_bytes(
            gzip.compress(json.dumps(value).encode("utf-8"), mtime=0)
        )
    else:
        path.write_text(json.dumps(value, indent=2) + "\n", encoding="utf-8")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--start", type=date.fromisoformat, default=date(2023, 7, 1))
    parser.add_argument("--as-of", required=True, type=date.fromisoformat)
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args()
    if args.start > args.as_of:
        parser.error("start must not follow as-of")
    asyncio.run(capture(args.start, args.as_of, args.output))
