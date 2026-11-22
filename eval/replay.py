"""Read-only HTTP replay of the known Socrata query subset, with no live fallback."""

from __future__ import annotations

import gzip
import json
import re
from functools import lru_cache
from pathlib import Path

import httpx
import respx


@lru_cache(maxsize=64)
def load(folder: Path, name: str) -> list[dict]:
    path = folder / name
    if path.exists():
        return json.loads(path.read_bytes())
    compressed = path.with_suffix(".json.gz")
    if compressed.exists():
        return json.loads(gzip.decompress(compressed.read_bytes()))
    raise ValueError(f"Required frozen file missing: {name}")


class Replay:
    def __init__(self, folder: Path, fail_sources=()):
        self.folder = folder
        self.fail_sources = set(fail_sources)
        self.seen = set()
        # The union adds historical state slices to the complete recent scan.
        nhsn = load(folder, "nhsn_scan_national.json") + [
            row
            for code in ("ga", "ca", "oh", "tx", "usa", "pr")
            for row in load(folder, f"nhsn_{code}.json")
        ]
        unique = {json.dumps(row, sort_keys=True): row for row in nhsn}
        self.datasets = {
            "vdzy-6i9v": list(unique.values()),
            "seuz-s2cv": load(folder, "nrevss_national.json"),
            "atcp-73re": [
                row
                for state in ("georgia", "california", "ohio", "texas")
                for row in load(folder, f"nwss_{state}.json")
            ],
        }

    def __enter__(self):
        self.mock = respx.mock(assert_all_mocked=True, assert_all_called=False)
        self.mock.__enter__()
        self.mock.get(
            url__regex=r"https://data\.cdc\.gov/resource/[a-z0-9-]+\.json"
        ).mock(side_effect=self.respond)
        return self

    def __exit__(self, *args):
        result = self.mock.__exit__(*args)
        if not self.fail_sources.issubset(self.seen):
            raise AssertionError("Not all simulated outage sources were exercised")
        return result

    def respond(self, request):
        dataset = request.url.path.split("/")[-1].removesuffix(".json")
        self.seen.add(dataset)
        if dataset in self.fail_sources:
            raise httpx.ConnectError(
                "Simulated frozen-evaluation outage", request=request
            )
        if dataset not in self.datasets:
            raise AssertionError("Unrecorded dataset; no live fallback")
        params = request.url.params
        where = params.get("$where", "")
        if dataset == "atcp-73re":
            geographies = re.findall(r"state_territory='([^']*)'", where)
            if not geographies or set(geographies) - {
                "Georgia",
                "California",
                "Ohio",
                "Texas",
            }:
                raise AssertionError(
                    "Wastewater geography was not recorded; "
                    "a subset cannot represent it."
                )
        if dataset == "vdzy-6i9v":
            geographies = re.findall(r"jurisdiction='([^']*)'", where)
            starts = re.findall(r"weekendingdate>='([^']*)'", where)
            if (
                starts
                and starts[0] < "2026-09-05"
                and set(geographies) - {"GA", "CA", "OH", "TX", "USA", "PR"}
            ):
                raise AssertionError(
                    "Historical NHSN geography was not recorded "
                    "outside the captured state subset."
                )
        clauses = params.get("$where", "").split(" AND ")
        rows = self.datasets[dataset]
        for clause in clauses:
            if not clause:
                continue
            terms = clause.strip("() ").split(" OR ")
            parsed = []
            for term in terms:
                match = re.fullmatch(r"(\w+)(>=|<=|=)'((?:[^']|'')*)'", term)
                if not match:
                    raise AssertionError(f"Unsupported frozen-query clause: {term}")
                parsed.append(match.groups())

            def matches(row):
                for field, operator, value in parsed:
                    actual = str(row.get(field, ""))
                    # Source timestamps are compared by calendar day.
                    if len(value) == 10 and field in ("week_end", "weekendingdate"):
                        actual = actual[:10]
                    value = value.replace("''", "'")
                    if {
                        "=": actual == value,
                        ">=": actual >= value,
                        "<=": actual <= value,
                    }[operator]:
                        return True
                return False

            rows = [r for r in rows if matches(r)]
        order = params.get("$order", "")
        if order:
            fields = [part.strip().split()[0] for part in order.split(",")]
            rows = sorted(rows, key=lambda r: tuple(str(r.get(f, "")) for f in fields))
        offset, limit = int(params.get("$offset", 0)), int(params.get("$limit", 5000))
        rows = rows[offset : offset + limit]
        if params.get("$select"):
            fields = params["$select"].split(",")
            rows = [{k: v for k, v in row.items() if k in fields} for row in rows]
        return httpx.Response(200, json=rows)
