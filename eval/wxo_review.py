"""Check captured wxO tool evidence without making model or network requests.

These checks do not establish semantic answer correctness. Review answers too.
"""

from __future__ import annotations

import argparse
import json
import re
from pathlib import Path

REGION4 = {"AL", "FL", "GA", "KY", "MS", "NC", "SC", "TN"}


def tool_evidence(record: dict) -> list[dict]:
    """Join calls and responses by ID; do not count duplicate trace views twice."""
    calls, responses = {}, {}
    for step in record.get("step_history") or []:
        for detail in step.get("step_details") or []:
            kind = detail.get("type")
            candidates = detail.get("tool_calls", []) if kind == "tool_calls" else []
            if kind == "tool_call":
                candidates = [detail]
            for call in candidates:
                key = call.get("tool_call_id") or call.get("id")
                if key:
                    calls[key] = {
                        "name": call.get("name", "").rsplit(":", 1)[-1],
                        "arguments": call.get("args") or {},
                    }
            if kind == "tool_response":
                content = detail.get("content")
                try:
                    data = json.loads(content) if isinstance(content, str) else content
                except (ValueError, TypeError):
                    data = None
                if isinstance(data, dict) and isinstance(data.get("data"), dict):
                    data = data["data"]
                responses[detail.get("tool_call_id")] = data
    return [{**call, "output": responses.get(key)} for key, call in calls.items()]


def observation_dates(value):
    """Inspect observation dates, excluding retrieval timestamps."""
    if isinstance(value, dict):
        for key, item in value.items():
            if key in {"week_ending", "latest_week_ending", "as_of_week_ending"}:
                if isinstance(item, str) and re.fullmatch(r"\d{4}-\d{2}-\d{2}", item):
                    yield item
            else:
                yield from observation_dates(item)
    elif isinstance(value, list):
        for item in value:
            yield from observation_dates(item)


def review(record: dict, cutoff: str | None, region: int | None = None) -> dict:
    """Check explicit cutoff, completed payloads and Region 4 scope when requested."""
    calls = tool_evidence(record)
    checks = {
        "run_completed": record.get("status") == "completed",
        "tool_evidence_present": bool(calls),
        "tool_responses_present": bool(calls)
        and all(isinstance(c["output"], dict) for c in calls),
        "cutoff_arguments": bool(calls)
        and all(c["arguments"].get("as_of") == cutoff for c in calls),
    }
    dates = [d for c in calls for d in observation_dates(c.get("output"))]
    answer = "\n".join(record.get("answer") or [])
    checks["observations_within_cutoff"] = (
        all(d <= cutoff for d in dates) if cutoff and dates else None
    )
    scans = [
        c
        for c in calls
        if c["name"] == "find_jurisdictions_with_rising_activity"
        and isinstance(c.get("output"), dict)
        and not c["output"].get("error")
    ]
    if scans:
        checks["scan_payload_membership_consistent"] = all(
            scan_membership_consistent(c["output"]) for c in scans
        )
        checks["scan_display_preserved"] = all(
            bool(c["output"].get("display_text"))
            and c["output"]["display_text"] in answer
            for c in scans
        )
        checks["scan_answer_membership"] = all(
            scan_answer_membership(answer, c["output"]) for c in scans
        )
    if scans or any(
        c["name"] == "assess_trend"
        and isinstance(c.get("output"), dict)
        and c["output"].get("trend")
        for c in calls
    ):
        checks["application_heuristic_attribution"] = bool(
            re.search(r"application.{0,40}heuristic", answer, re.I)
        ) and not re.search(
            r"\bCDC(?:\s+NHSN)?(?:\s+server)?\s+heuristic\b", answer, re.I
        )
    if region is not None:
        scans = [
            c for c in calls if c["name"] == "find_jurisdictions_with_rising_activity"
        ]
        checks["region_argument"] = bool(scans) and all(
            c["arguments"].get("hhs_region") == region for c in scans
        )
        if region == 4:
            checks["region_payload_scope"] = bool(scans) and all(
                isinstance(c["output"], dict)
                and c["output"].get("n_jurisdictions_scanned") == len(REGION4)
                and all(
                    r.get("jurisdiction") in REGION4
                    for r in c["output"].get("rising", [])
                )
                and set(c["output"].get("unavailable_jurisdictions", [])) <= REGION4
                for c in scans
            )
    errors = [
        c["output"]
        for c in calls
        if isinstance(c["output"], dict) and c["output"].get("error")
    ]
    if errors:
        checks["error_message_preserved"] = all(
            e.get("message") and e["message"] in answer for e in errors
        )
    return {
        "checks": checks,
        "automated_checks_pass": all(v is not False for v in checks.values()),
        "semantic_answer_review_required": True,
        "tool_calls": len(calls),
    }


def scan_membership_consistent(payload: dict) -> bool:
    """Check displayed membership against rows, allowing a declared result limit."""
    rows = payload.get("rising")
    if not isinstance(rows, list):
        return False
    codes = [r.get("jurisdiction") for r in rows]
    return (
        bool(all(isinstance(code, str) for code in codes))
        and len(set(codes)) == len(codes)
        and payload.get("rising_jurisdictions") == codes
        and payload.get("n_returned") == len(codes)
        and isinstance(payload.get("n_rising_total"), int)
        and payload["n_rising_total"] >= len(codes)
    )


def scan_answer_membership(answer: str, payload: dict) -> bool:
    """Check code lists; other answer formats require semantic review."""
    expected = [r["jurisdiction"] for r in payload.get("rising", [])]
    if not expected:
        return bool(payload.get("display_text")) and payload["display_text"] in answer
    lists = re.findall(r"\b[A-Z]{2}(?:,\s*[A-Z]{2})+\b", answer)
    return bool(lists) and all(
        len(codes := re.findall(r"[A-Z]{2}", text)) == len(expected)
        and set(codes) == set(expected)
        for text in lists
    )


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("record", type=Path)
    parser.add_argument("--cutoff")
    parser.add_argument("--region", type=int)
    parser.add_argument("--phase", help="Select a phase from a saved evidence bundle.")
    parser.add_argument("--index", type=int, default=0, help="Zero-based record index.")
    args = parser.parse_args()
    record = json.loads(args.record.read_text(encoding="utf-8"))
    if args.phase:
        record = record["phases"][args.phase]["records"][args.index]
    result = review(record, args.cutoff, args.region)
    print(json.dumps(result, indent=2))
    raise SystemExit(0 if result["automated_checks_pass"] else 1)


if __name__ == "__main__":
    main()
