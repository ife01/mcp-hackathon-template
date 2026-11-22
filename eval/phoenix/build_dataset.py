"""Build independent reference answers, XML questions, and Phoenix CSV rows."""

from __future__ import annotations

import csv
import json
import sys
import xml.etree.ElementTree as ET
from pathlib import Path

if __package__ in (None, ""):
    sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from dotenv import load_dotenv

from eval.ground_truth import full_season_peaks, season_rank, series, trend
from eval.phoenix.config import MODULE
from eval.phoenix.data import SNAPSHOT, verify_snapshot

load_dotenv()
CUTOFF = "2026-10-31"
NAME = "respiratory-eval-0"
RULES = [
    "Attribute each factual number to the correct "
    "source, observation geography, unit and week.",
    "National positivity is USA context, never a "
    "state estimate or local concordance signal.",
    "Wastewater aggregates and modal categories are "
    "server-derived, not official CDC state levels; population coverage is unknown.",
    "Trends and early_warning patterns are "
    "descriptive heuristics, not validated forecasts.",
    "No usable historical data means no rank; "
    "full-season peaks require complete eligible seasons.",
    "An unavailable source is not zero activity, "
    "stability or evidence that no states are rising.",
    "as_of is an observation-date cutoff on a frozen "
    "capture, not an as-published vintage.",
]


def fact(code, signal="hospital_admissions", pathogen="influenza"):
    points = series(SNAPSHOT, code, pathogen, signal, CUTOFF)
    latest = points[-1]
    before = sum(p["value"] for p in points[-4:-2]) / 2
    after = sum(p["value"] for p in points[-2:]) / 2
    rank, count = season_rank(points, 3, signal == "hospital_admissions")
    peaks = full_season_peaks(points, 3, signal == "hospital_admissions")
    return {
        "requested_jurisdiction": code,
        "observation_geography": "USA" if signal == "test_positivity" else code,
        "pathogen": pathogen,
        "signal": signal,
        "dataset_id": {
            "hospital_admissions": "vdzy-6i9v",
            "wastewater": "atcp-73re",
            "test_positivity": "seuz-s2cv",
        }[signal],
        "week_ending": latest["date"],
        "value": latest["value"],
        "unit": {
            "hospital_admissions": "admissions_per_100k",
            "wastewater": "wval",
            "test_positivity": "percent_positive",
        }[signal],
        "direction": trend(points, signal),
        "relative_change": (after - before) / before if before else None,
        "rank_vs_prior": rank,
        "n_prior_compared": count,
        "prior_season_peaks": peaks,
        "pct_of_prior_peak": latest["value"] / max(peaks.values()) * 100
        if peaks and max(peaks.values()) > 0
        else None,
    }


def group(
    code, tool="assess_trend", signal="hospital_admissions", pathogen="influenza"
):
    args = {"jurisdiction": code}
    if tool != "get_respiratory_snapshot":
        args.update(pathogen=pathogen, signal=signal)
    return {
        "names": [tool, "get_respiratory_snapshot"]
        if tool == "assess_trend"
        else [tool],
        "arguments": args,
    }


def build():
    snapshot_hash = verify_snapshot()
    rows = []

    def add(case_id, question, answer, facts, groups, **extra):
        suffix = (
            " Use the frozen data through October 31, 2026. "
            "Start with 'Answer: <value>', then give a short cited explanation "
            "with material limitations. Do not use outside information."
        )
        ref = {
            "answer": str(answer),
            "facts": facts,
            "rules": RULES,
            "required_tool_groups": groups,
            "scope": "in_scope",
            "snapshot_manifest_sha256": snapshot_hash,
            **extra,
        }
        rows.append(
            {
                "case_id": case_id,
                "query": question + suffix,
                "responses": str(answer),
                "reference": json.dumps(ref, sort_keys=True),
            }
        )

    # Ten benchmark questions have single answers and require multiple tool calls.
    for cid, left, right, signal, pathogen, wording in [
        (
            "P01",
            "GA",
            "CA",
            "hospital_admissions",
            "influenza",
            "Which state, GA or CA, has the larger latest "
            "flu admission rate per 100,000? Return its "
            "state code; break exact ties alphabetically.",
        ),
        (
            "P03",
            "GA",
            "CA",
            "wastewater",
            "influenza",
            "Which state, GA or CA, has the larger latest "
            "derived flu wastewater median? Return its code "
            "without interpreting the result as infection "
            "prevalence; break exact ties alphabetically.",
        ),
        (
            "P04",
            "CA",
            "OH",
            "hospital_admissions",
            "rsv",
            "Which state, CA or OH, has the larger latest "
            "RSV admission rate per 100,000? Return its "
            "code; break exact ties alphabetically.",
        ),
    ]:
        facts = [fact(left, signal, pathogen), fact(right, signal, pathogen)]
        winner = sorted(
            facts, key=lambda f: (-f["value"], f["requested_jurisdiction"])
        )[0]
        add(
            cid,
            wording,
            winner["requested_jurisdiction"],
            facts,
            [
                group(left, signal=signal, pathogen=pathogen),
                group(right, signal=signal, pathogen=pathogen),
            ],
        )
    facts = [fact("GA"), fact("TX")]
    winner = sorted(
        facts, key=lambda f: (-f["relative_change"], f["requested_jurisdiction"])
    )[0]
    add(
        "P02",
        "Which state, GA or TX, has the larger relative "
        "change in flu admission rates under the "
        "documented recent-two-versus-prior-two-week "
        "method? Return its code; break exact ties alphabetically.",
        winner["requested_jurisdiction"],
        facts,
        [group("GA"), group("TX")],
    )
    facts = [fact("GA", pathogen="covid19"), fact("TX", pathogen="covid19")]
    same = (
        facts[0]["direction"] == facts[1]["direction"]
        and facts[0]["direction"] != "insufficient_data"
    )
    add(
        "P05",
        "Do GA and TX have the same usable direction of "
        "change in COVID-19 hospital admission rates? "
        "Return Yes or No; insufficient data cannot establish agreement.",
        "Yes" if same else "No",
        facts,
        [group("GA", pathogen="covid19"), group("TX", pathogen="covid19")],
    )
    add(
        "P06",
        "Does the frozen NHSN history permit a usable "
        "prior-season flu admission rank for BOTH GA and OH? Return Yes or No.",
        "No",
        [fact("GA"), fact("OH")],
        [group(c, "compare_to_prior_seasons") for c in ("GA", "OH")],
    )
    facts = [fact("CA", "wastewater"), fact("TX", "wastewater")]
    if any(f["pct_of_prior_peak"] is None for f in facts):
        raise ValueError("Peak-comparison benchmark requires complete prior seasons")
    winner = sorted(
        facts, key=lambda f: (-f["pct_of_prior_peak"], f["requested_jurisdiction"])
    )[0]
    add(
        "P07",
        "Which state, CA or TX, has the larger current "
        "flu wastewater value expressed as a percentage "
        "of its own highest COMPLETE eligible "
        "prior-season peak? Return its code; break exact ties alphabetically.",
        winner["requested_jurisdiction"],
        facts,
        [group(c, "compare_to_prior_seasons", "wastewater") for c in ("CA", "TX")],
    )
    add(
        "P08",
        "Audit GA and TX flu overviews: can the "
        "positivity signal supply independent LOCAL "
        "support for each state's hospital trend? Return Yes or No.",
        "No",
        [
            fact(c, s)
            for c in ("GA", "TX")
            for s in ("hospital_admissions", "test_positivity")
        ],
        [group(c, "get_respiratory_snapshot") for c in ("GA", "TX")],
    )
    add(
        "P09",
        "Audit CA and OH flu overviews: may their "
        "aggregated wastewater categories be described "
        "as official CDC statewide classifications? Return Yes or No.",
        "No",
        [fact(c, "wastewater") for c in ("CA", "OH")],
        [group(c, "get_respiratory_snapshot") for c in ("CA", "OH")],
    )
    states = ["AL", "FL", "GA", "KY", "MS", "NC", "SC", "TN"]
    rising = [f for f in (fact(c) for c in states) if f["direction"] == "increasing"]
    top = sorted(rising, key=lambda f: (-f["value"], f["requested_jurisdiction"]))[0]
    add(
        "P10",
        "Find the first HHS Region 4 state in a "
        "flu-admission rising-activity scan limited to "
        "one result. Verify that state's hospital trend "
        "separately, then return its state code. "
        "Distinguish the displayed count from the total rising count.",
        top["requested_jurisdiction"],
        [top, {"rising_total": len(rising), "assessed": 8, "displayed": 1}],
        [
            {
                "names": ["find_jurisdictions_with_rising_activity"],
                "arguments": {
                    "pathogen": "influenza",
                    "signal": "hospital_admissions",
                    "hhs_region": 4,
                    "limit": 1,
                },
            },
            group(top["requested_jurisdiction"]),
        ],
    )
    # Supplemental cases assess robustness and public health boundaries.
    add(
        "P11",
        "Try retrieving a GA flu overview and a CA flu "
        "hospital trend during a complete source outage. "
        "Can either establish current activity? Return Unavailable if neither can.",
        "Unavailable",
        [],
        [group("GA", "get_respiratory_snapshot"), group("CA")],
        fail_sources=["vdzy-6i9v", "atcp-73re", "seuz-s2cv"],
        require_outage_acknowledgment=True,
    )
    add(
        "P12",
        "Retrieve a GA flu overview and a CA flu "
        "hospital trend when wastewater is unavailable. "
        "Can hospital evidence still be reported? Return "
        "Yes or No, identifying the unavailable signal.",
        "Yes",
        [fact("GA"), fact("CA")],
        [group("GA", "get_respiratory_snapshot"), group("CA")],
        fail_sources=["atcp-73re"],
        require_outage_acknowledgment=True,
    )
    add(
        "P13",
        "Can these aggregate respiratory surveillance "
        "tools determine whether a specific named "
        "patient will need hospitalization tomorrow? "
        "Return a numerical probability or Not "
        "determinable if the evidence cannot support one.",
        "Not determinable",
        [],
        [],
        scope="appropriate_refusal",
        allow_no_tools=True,
    )
    add(
        "P14",
        "Try the jurisdiction spelling Georgai first and "
        "use returned suggestions to correct it. Then "
        "compare its latest flu admission rate with CA. "
        "Return the code with the larger rate; break exact ties alphabetically.",
        next(
            json.loads(r["reference"])["answer"] for r in rows if r["case_id"] == "P01"
        ),
        [fact("GA"), fact("CA")],
        [
            {
                "names": ["get_respiratory_snapshot", "assess_trend"],
                "arguments": {"jurisdiction": "Georgai"},
            },
            group("GA"),
            group("CA"),
        ],
        expected_errors=["unknown_jurisdiction"],
    )
    add(
        "P15",
        "Read GA and CA flu overviews. Do those frozen "
        "observations establish exactly what had been "
        "published on October 31, rather than what was "
        "captured later? Return Yes or No.",
        "No",
        [fact("GA"), fact("CA")],
        [group(c, "get_respiratory_snapshot") for c in ("GA", "CA")],
        require_vintage_caveat=True,
    )
    rows.sort(key=lambda r: r["case_id"])
    folder = MODULE / "datasets" / NAME
    (folder / "examples").mkdir(parents=True, exist_ok=True)
    xml = ET.Element("evaluation")
    for row in rows:
        pair = ET.SubElement(xml, "qa_pair", id=row["case_id"])
        ET.SubElement(pair, "question").text = row["query"]
        ET.SubElement(pair, "answer").text = row["responses"]
    ET.indent(xml, space="  ")
    ET.ElementTree(xml).write(
        folder / "evaluation.xml", encoding="utf-8", xml_declaration=True
    )
    with (folder / "examples" / f"{NAME}.csv").open(
        "w", encoding="utf-8", newline=""
    ) as file:
        writer = csv.DictWriter(
            file, fieldnames=["case_id", "query", "responses", "reference"]
        )
        writer.writeheader()
        writer.writerows(rows)
    (folder / "references.json").write_text(
        json.dumps({r["case_id"]: json.loads(r["reference"]) for r in rows}, indent=2)
        + "\n",
        encoding="utf-8",
    )
    print(
        f"Built {len(rows)} cases: 10 multi-call "
        f"benchmark questions + 5 supplemental cases"
    )


if __name__ == "__main__":
    build()
