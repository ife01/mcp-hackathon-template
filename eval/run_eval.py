"""Run deterministic tool-level evaluations against frozen HTTP replay.

Does not score an LLM's tool selection, arguments, or final-answer grounding.
"""

from __future__ import annotations

import argparse
import asyncio
import hashlib
import json
import math
import time
from datetime import date, timedelta
from pathlib import Path

import yaml
from ground_truth import full_season_peaks, season_rank, series, trend
from replay import Replay

from resp_mcp.clients import socrata
from resp_mcp.server import mcp

ROOT = Path(__file__).resolve().parent


def check_output(folder, tool, args, output):
    checks = []

    def check(label, actual, expected):
        passed = (
            math.isclose(actual, expected, rel_tol=1e-8, abs_tol=1e-8)
            if isinstance(expected, float) and isinstance(actual, (float, int))
            else actual == expected
        )
        checks.append(
            {"check": label, "passed": passed, "actual": actual, "expected": expected}
        )

    code, pathogen = args.get("jurisdiction"), args.get("pathogen", "influenza")
    signal, cutoff = args.get("signal"), args["as_of"]
    if "error" in output:
        check("unexpected tool error", output["error"], None)
        return checks
    if tool == "assess_trend":
        points = series(folder, code, pathogen, signal, cutoff)
        start = (
            date.fromisoformat(cutoff)
            - timedelta(weeks=args.get("lookback_weeks", 8))
            + timedelta(days=1)
        ).isoformat()
        points = [p for p in points if p["date"] >= start]
        check("trend direction", output["trend"]["direction"], trend(points, signal))
        check("trend window", output["trend"]["window_weeks"], min(4, len(points)))
        check(
            "units",
            output["series"][-1]["unit"],
            {
                "hospital_admissions": "admissions_per_100k",
                "wastewater": "wval",
                "test_positivity": "percent_positive",
            }[signal],
        )
        check("latest value", output["series"][-1]["value"], points[-1]["value"])
        check(
            "actual observation geography",
            output["series"][-1]["jurisdiction"],
            "USA" if signal == "test_positivity" else code,
        )
        check("latest date", output["series"][-1]["week_ending"], points[-1]["date"])
    elif tool == "compare_to_prior_seasons":
        points = series(folder, code, pathogen, signal, cutoff)
        rank, count = season_rank(
            points, args.get("prior_seasons", 3), signal == "hospital_admissions"
        )
        check("historical rank", output["comparison"]["rank_vs_prior"], rank)
        check(
            "usable prior-week count", output["comparison"]["n_prior_compared"], count
        )
        peaks = full_season_peaks(
            points, args.get("prior_seasons", 3), signal == "hospital_admissions"
        )
        check(
            "complete-season peak set",
            output["comparison"]["prior_season_peaks"],
            peaks,
        )
        expected_pct = (
            points[-1]["value"] / max(peaks.values()) * 100
            if peaks and max(peaks.values()) > 0 and points[-1]["value"] is not None
            else None
        )
        check(
            "percent of complete prior peak",
            output["comparison"]["pct_of_prior_peak"],
            expected_pct,
        )
        check(
            "current historical value",
            output["comparison"]["current_value"],
            points[-1]["value"] if points else None,
        )
        if not count:
            check(
                "no unsupported highest claim",
                "highest" in output["summary"].lower(),
                False,
            )
    elif tool == "get_respiratory_snapshot":
        readings = output["pathogens"][0]["signals"]
        for reading in readings:
            sig = reading["signal"]
            points = series(folder, code, "influenza", sig, cutoff)
            check(
                f"{sig} latest value", reading["latest"]["value"], points[-1]["value"]
            )
            check(f"{sig} date", reading["latest"]["week_ending"], points[-1]["date"])
            if sig == "test_positivity":
                check("national context label", reading["role"], "national_context")
                check(
                    "national context geography",
                    reading["latest"]["jurisdiction"],
                    "USA",
                )
            if sig == "wastewater":
                check(
                    "no invented CDC aggregate level",
                    reading["latest"]["official_level"],
                    None,
                )
    elif tool == "find_jurisdictions_with_rising_activity":
        # Fixed region in D5, independently enumerated rather than importing references.
        candidates = []
        for state in ["AL", "FL", "GA", "KY", "MS", "NC", "SC", "TN"]:
            points = series(folder, state, pathogen, signal, cutoff)
            if trend(points, signal) == "increasing":
                candidates.append((state, points[-1]["value"]))
        candidates.sort(key=lambda pair: (-pair[1], pair[0]))
        check("total rising before limit", output["n_rising_total"], len(candidates))
        check(
            "ranked rising states",
            [r["jurisdiction"] for r in output["rising"]],
            [p[0] for p in candidates[: args.get("limit", 10)]],
        )
        check("assessed count", output["n_assessed"], 8)
    return checks


def verify_snapshot(folder):
    manifest = json.loads((folder / "capture_manifest.json").read_bytes())
    if not manifest["complete"]:
        raise ValueError("Snapshot capture did not complete")
    for name, entry in manifest["files"].items():
        if hashlib.sha256((folder / name).read_bytes()).hexdigest() != entry["sha256"]:
            raise ValueError(f"Snapshot hash mismatch: {name}")


async def run(cases_path: Path, output_dir: Path):
    spec = yaml.safe_load(cases_path.read_text(encoding="utf-8"))
    folder = cases_path.parent / spec["snapshot"]
    verify_snapshot(folder)
    output_dir.mkdir(parents=True, exist_ok=True)
    reports = []
    for case in spec["cases"]:
        socrata._cache = socrata._Cache()
        checks, calls = [], []
        start = time.perf_counter()
        with Replay(folder, case.get("fail_sources", [])):
            for planned in case["calls"]:
                result = await mcp.call_tool(planned["tool"], planned["arguments"])
                output = json.loads(result.content[0].text)
                calls.append({**planned, "output": output})
                if case.get("expected_error"):
                    checks.append(
                        {
                            "check": "expected error",
                            "passed": output.get("error") == case["expected_error"],
                            "actual": output.get("error"),
                            "expected": case["expected_error"],
                        }
                    )
                else:
                    checks.extend(
                        check_output(
                            folder, planned["tool"], planned["arguments"], output
                        )
                    )
        report = {
            "id": case["id"],
            "category": case["category"],
            "prompt": case["prompt"],
            "passed": bool(checks) and all(c["passed"] for c in checks),
            "replay_seconds": time.perf_counter() - start,
            "checks": checks,
            "calls": calls,
        }
        (output_dir / f"{case['id']}.json").write_text(
            json.dumps(report, indent=2) + "\n", encoding="utf-8"
        )
        reports.append(report)
        print(f"{case['id']}: {'PASS' if report['passed'] else 'FAIL'}", flush=True)
    passed = sum(r["passed"] for r in reports)
    summary = {
        "mode": "offline_tool_replay",
        "passed": passed,
        "total": len(reports),
        "checks_passed": sum(c["passed"] for r in reports for c in r["checks"]),
        "checks_total": sum(len(r["checks"]) for r in reports),
        "agent_evaluation": "not run",
        "snapshot": spec["snapshot"],
        "snapshot_manifest_sha256": hashlib.sha256(
            (folder / "capture_manifest.json").read_bytes()
        ).hexdigest(),
        "server_source_sha256": hashlib.sha256(
            b"".join(
                p.relative_to(ROOT.parent).as_posix().encode() + p.read_bytes()
                for p in sorted((ROOT.parent / "src").rglob("*.py"))
            )
        ).hexdigest(),
        "reference_sha256": hashlib.sha256(
            (ROOT / "ground_truth.py").read_bytes()
        ).hexdigest(),
        "cases_sha256": hashlib.sha256(cases_path.read_bytes()).hexdigest(),
        "cases": [
            {k: r[k] for k in ("id", "category", "passed", "replay_seconds")}
            for r in reports
        ],
    }
    (output_dir / "summary.json").write_text(
        json.dumps(summary, indent=2) + "\n", encoding="utf-8"
    )
    print(f"{passed}/{len(reports)} cases passed; this is not an agent evaluation.")
    return passed == len(reports)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--cases", type=Path, default=ROOT / "cases.yaml")
    parser.add_argument("--output", type=Path, default=ROOT / "transcripts" / "tools")
    args = parser.parse_args()
    raise SystemExit(0 if asyncio.run(run(args.cases, args.output)) else 1)
