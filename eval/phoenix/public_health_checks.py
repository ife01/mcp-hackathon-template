"""Deterministic evidence checks complement, rather than replace, semantic judges."""

from __future__ import annotations

import json
import math
import re

from dotenv import load_dotenv

load_dotenv()


def reference(expected) -> dict:
    value = expected["reference"]
    return json.loads(value) if isinstance(value, str) else value


def score(value, explanation, label=None):
    return {
        "score": value,
        "label": label or ("pass" if value == 1 else "fail"),
        "explanation": explanation,
    }


def canonical(value):
    if not isinstance(value, str):
        return value
    aliases = {
        "georgia": "GA",
        "california": "CA",
        "ohio": "OH",
        "texas": "TX",
        "florida": "FL",
        "alabama": "AL",
        "mississippi": "MS",
        "kentucky": "KY",
        "tennessee": "TN",
        "north carolina": "NC",
        "south carolina": "SC",
        "flu": "influenza",
        "covid": "covid19",
        "covid-19": "covid19",
        "sars-cov-2": "covid19",
    }
    if value.upper() in (
        "GA",
        "CA",
        "OH",
        "TX",
        "FL",
        "AL",
        "MS",
        "KY",
        "TN",
        "NC",
        "SC",
        "USA",
    ):
        return value.upper()
    return aliases.get(value.lower(), value)


def matches(call, group):
    if call.get("name") not in group["names"] or call.get("status") == "pending":
        return False
    args = call.get("arguments", {})
    for key, value in group["arguments"].items():
        if call["name"] == "get_respiratory_snapshot" and key in ("pathogen", "signal"):
            if key == "pathogen" and args.get("pathogens") is not None:
                if value not in [canonical(p) for p in args["pathogens"]]:
                    return False
            continue
        if canonical(args.get(key)) != value:
            return False
    return True


def tool_selection(output, expected):
    ref = reference(expected)
    groups = ref["required_tool_groups"]
    if not groups and ref.get("allow_no_tools"):
        return score(
            None,
            "Tools are optional for an appropriate scope refusal.",
            "not_applicable",
        )
    hit = sum(
        any(matches(call, group) for call in output.get("tool_calls", []))
        for group in groups
    )
    return score(
        hit / len(groups) if groups else 0,
        f"Required analytical action coverage: "
        f"{hit}/{len(groups)}. Valid alternative tools are accepted.",
    )


def argument_accuracy(output, expected):
    ref = reference(expected)
    calls = output.get("tool_calls", [])
    if not calls:
        return (
            score(None, "No tool arguments for a scope refusal.", "not_applicable")
            if ref.get("allow_no_tools")
            else score(0, "No tool calls.")
        )
    good = 0
    for call in calls:
        error = (call.get("output") or {}).get("error")
        error_ok = (
            not error
            or error in ref.get("expected_errors", [])
            or error == "upstream_unavailable"
            and bool(ref.get("fail_sources"))
        )
        good += int(
            call.get("arguments", {}).get("as_of") == "2026-10-31"
            and error_ok
            and call.get("status") != "pending"
        )
    return score(
        good / len(calls),
        f"Completed calls with preserved cutoff and no "
        f"unexpected input/tool error: {good}/{len(calls)}.",
    )


def answer_anchor(output, expected):
    answer = output.get("answer", "").strip()
    match = re.match(r"(?:\*\*)?Answer:\s*(.*?)(?:\*\*)?(?:\r?\n|$)", answer, re.I)
    actual = match.group(1).strip(" `*.") if match else ""
    target = str(expected["responses"]).strip()
    return score(
        int(actual.casefold() == target.casefold()),
        "First-line answer compared with the independent scalar reference.",
    )


def readings(call):
    data = call.get("output") or {}
    args = call.get("arguments", {})
    if data.get("error"):
        return []
    if call["name"] == "get_respiratory_snapshot":
        return [
            {
                "requested_jurisdiction": canonical(args.get("jurisdiction")),
                "pathogen": p["pathogen"],
                "signal": s["signal"],
                "provenance": s.get("provenance"),
                "observation": s.get("latest"),
            }
            for p in data.get("pathogens", [])
            for s in p.get("signals", [])
        ]
    if call["name"] == "assess_trend":
        return [
            {
                "requested_jurisdiction": canonical(args.get("jurisdiction")),
                "pathogen": data.get("pathogen"),
                "signal": data.get("signal"),
                "provenance": data.get("provenance"),
                "observation": data.get("series", [None])[-1]
                if data.get("series")
                else None,
            }
        ]
    if call["name"] == "compare_to_prior_seasons":
        prov = data.get("provenance") or {}
        return [
            {
                "requested_jurisdiction": canonical(args.get("jurisdiction")),
                "pathogen": data.get("pathogen"),
                "signal": data.get("signal"),
                "provenance": prov,
                "observation": {
                    "value": data["comparison"]["current_value"],
                    "week_ending": prov.get("latest_week_ending"),
                    "jurisdiction": "USA"
                    if prov.get("geography_level") == "national"
                    else args.get("jurisdiction"),
                },
            }
        ]
    return []


def evidence_integrity(output, expected):
    ref = reference(expected)
    if output.get("snapshot_manifest_sha256") != ref["snapshot_manifest_sha256"]:
        return score(0, "Task output is missing the expected frozen-snapshot identity.")
    if output.get("verification_only"):
        return score(0, "Scripted verification is not an agent benchmark result.")
    problems = []
    for call in output.get("tool_calls", []):
        for item in readings(call):
            obs = item["observation"]
            if obs is None:
                continue
            for fact in ref["facts"]:
                if all(
                    fact.get(k) == item.get(k)
                    for k in ("requested_jurisdiction", "pathogen", "signal")
                ):
                    val = obs.get("value")
                    equal = (
                        val == fact["value"]
                        if val is None or fact["value"] is None
                        else math.isclose(
                            val, fact["value"], abs_tol=1e-8, rel_tol=1e-8
                        )
                    )
                    if (
                        not equal
                        or obs.get("jurisdiction") != fact["observation_geography"]
                        or obs.get("week_ending") != fact["week_ending"]
                    ):
                        problems.append(
                            "Frozen value/date/geography differs from the "
                            "independent reference."
                        )
                    if "unit" in obs and obs["unit"] != fact["unit"]:
                        problems.append("Observation unit mismatch.")
                    if (item.get("provenance") or {}).get("dataset_id") != fact[
                        "dataset_id"
                    ]:
                        problems.append("Source identifier mismatch.")
    return score(
        int(not problems),
        "; ".join(sorted(set(problems)))
        or "Available overlapping evidence matches "
        "independent frozen reference values, dates, sources and geography.",
    )


def numeric_grounding(output, expected):
    """Support check only; semantic attribution is scored by the public health judge."""
    calls = output.get("tool_calls", [])
    # Normalize harmless numeric formatting (1,000; 5.0 vs 5) and percentages.
    supported = {100000.0}

    def numbers(text):
        # These digits name pathogens; they are not numerical surveillance claims.
        text = re.sub(r"\b(?:COVID-19|SARS-CoV-2)\b", "", text, flags=re.I)
        return re.findall(r"(?<![\w])\d+(?:\.\d+)?(?![\w])", text)

    # An outage can omit dates from its result. The actual call's cutoff still
    # supports a date in the answer; argument_accuracy separately verifies it.
    for token in numbers(
        json.dumps(
            [
                {"arguments": c.get("arguments"), "output": c.get("output")}
                for c in calls
            ]
        )
    ):
        value = float(token)
        for scale in (1, 100):
            supported.update(round(value * scale, places) for places in range(7))
    answer = output.get("answer", "").replace(",", "")
    unsupported = [token for token in numbers(answer) if float(token) not in supported]
    return score(
        int(not unsupported),
        "Unsupported numeric tokens present."
        if unsupported
        else "Numeric tokens are supported up to ordinary "
        "rounding/unit scaling; semantic geography, date "
        "and unit attribution require the public health judge.",
    )


def hard_checks(output, expected):
    return {
        f.__name__: f(output, expected)
        for f in (
            tool_selection,
            argument_accuracy,
            answer_anchor,
            evidence_integrity,
            numeric_grounding,
        )
    }
