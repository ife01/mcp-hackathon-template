"""Independent raw-data reference calculations; no resp_mcp imports.

These implement the documented descriptive rules, not clinical validation.
"""

from __future__ import annotations

import gzip
import json
import math
import statistics
from collections import defaultdict
from datetime import date, timedelta
from pathlib import Path

from epiweeks import Week

PATHOGENS = {
    "influenza": ("totalconfflunewadm", "Influenza A virus", "Influenza"),
    "covid19": ("totalconfc19newadm", "SARS-CoV-2", "COVID-19"),
    "rsv": ("totalconfrsvnewadm", "RSV", "RSV"),
}
STATES = {"GA": "georgia", "CA": "california", "OH": "ohio", "TX": "texas"}


def number(value):
    try:
        result = float(value)
        return result if math.isfinite(result) and result >= 0 else None
    except (ValueError, TypeError):
        return None


def series(
    folder: Path, code: str, pathogen: str, signal: str, cutoff: str
) -> list[dict]:
    prefix, target, label = PATHOGENS[pathogen]
    if signal == "hospital_admissions":
        filename = f"nhsn_{code.lower()}.json"
    elif signal == "test_positivity":
        filename = "nrevss_national.json"
    else:
        filename = f"nwss_{STATES[code]}.json"
    path = folder / filename
    if path.exists():
        rows = json.loads(path.read_bytes())
    elif path.with_suffix(".json.gz").exists():
        rows = json.loads(gzip.decompress(path.with_suffix(".json.gz").read_bytes()))
    elif signal == "hospital_admissions":
        path = folder / "nhsn_scan_national.json.gz"
        rows = [
            r
            for r in json.loads(gzip.decompress(path.read_bytes()))
            if r.get("jurisdiction") == code
        ]
    else:
        raise ValueError(f"Unrecorded geography: {code}")
    result = []
    if signal == "wastewater":
        grouped = defaultdict(dict)
        for row in rows:
            if row["pathogen_target"] != target or row["week_end"][:10] > cutoff:
                continue
            if row.get("site"):
                grouped[row["week_end"][:10]].setdefault(row["site"], []).append(row)
        for week, sites in grouped.items():
            values = []
            for records in sites.values():
                signatures = {
                    (number(r.get("site_wval")), r.get("site_wval_category"))
                    for r in records
                }
                if len(signatures) == 1:
                    value = number(records[0].get("site_wval"))
                    if value is not None:
                        values.append(value)
            result.append(
                {
                    "date": week,
                    "value": statistics.median(values) if len(values) >= 2 else None,
                    "count": None,
                }
            )
    else:
        for row in rows:
            week = row.get("weekendingdate", row.get("week_end"))[:10]
            if week > cutoff or (
                signal == "test_positivity" and row["pathogen"] != label
            ):
                continue
            value = (
                row.get(prefix + "per100k")
                if signal == "hospital_admissions"
                else row.get("percent_test_positivity")
            )
            result.append(
                {"date": week, "value": number(value), "count": number(row.get(prefix))}
            )
    return sorted(result, key=lambda r: r["date"])


def trend(points: list[dict], signal: str) -> str:
    recent = points[-4:]
    if len(recent) != 4 or any(p["value"] is None for p in recent):
        return "insufficient_data"
    dates = [date.fromisoformat(p["date"]) for p in recent]
    if any((b - a).days != 7 for a, b in zip(dates, dates[1:])):
        return "insufficient_data"
    if signal == "hospital_admissions" and all(p["count"] is not None for p in recent):
        if (
            max(
                statistics.mean(p["count"] for p in recent[:2]),
                statistics.mean(p["count"] for p in recent[2:]),
            )
            < 10
        ):
            return "insufficient_data"
    before = statistics.mean(p["value"] for p in recent[:2])
    after = statistics.mean(p["value"] for p in recent[2:])
    delta = after - before
    if signal == "hospital_admissions":
        changed = abs(delta) >= 0.1 and (before == 0 or abs(delta / before) >= 0.10)
    elif signal == "test_positivity":
        changed = abs(delta) >= 1
    else:
        if before == 0 and after != 0:
            return "insufficient_data"
        changed = before != 0 and abs(delta / before) >= 0.15
    return ("increasing" if delta > 0 else "decreasing") if changed else "stable"


def season_rank(points: list[dict], count: int, nhsn: bool) -> tuple[int | None, int]:
    if not points or points[-1]["value"] is None:
        return None, 0
    ref = date.fromisoformat(points[-1]["date"])
    week = Week.fromdate(ref, system="CDC")
    year = week.year if week.week >= 27 else week.year - 1
    first = Week(year, 27, system="CDC").enddate()
    index = (ref - first).days // 7
    lookup = {p["date"]: p["value"] for p in points}
    priors = []
    for offset in range(1, count + 1):
        y = year - offset
        if nhsn and y < 2024:
            continue
        first, last = (
            Week(y, 27, system="CDC").enddate(),
            Week(y + 1, 26, system="CDC").enddate(),
        )
        target = min(first + timedelta(weeks=index), last)
        if nhsn and target < date(2024, 11, 9):
            continue
        for delta in (0, -7, 7):
            candidate = target + timedelta(days=delta)
            if not first <= candidate <= last or (
                nhsn and candidate < date(2024, 11, 9)
            ):
                continue
            if lookup.get(candidate.isoformat()) is not None:
                priors.append(lookup[candidate.isoformat()])
                break
    return (1 + sum(v > points[-1]["value"] for v in priors) if priors else None), len(
        priors
    )


def full_season_peaks(points, count, nhsn=False):
    if not points:
        return {}
    ref = date.fromisoformat(points[-1]["date"])
    week = Week.fromdate(ref, system="CDC")
    year = week.year if week.week >= 27 else week.year - 1
    lookup = {p["date"]: p["value"] for p in points}
    peaks = {}
    for offset in range(1, count + 1):
        y = year - offset
        first, last = (
            Week(y, 27, system="CDC").enddate(),
            Week(y + 1, 26, system="CDC").enddate(),
        )
        if nhsn and first < date(2024, 11, 9):
            continue
        values = []
        day = first
        while day <= last:
            value = lookup.get(day.isoformat())
            if value is None:
                break
            values.append(value)
            day += timedelta(days=7)
        if day > last:
            peaks[f"{y}-{str(y + 1)[-2:]}"] = max(values)
    return peaks
