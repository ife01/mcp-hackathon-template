"""Independent ground truth for the respiratory eval benchmark.

Computed directly from eval/snapshot/ — deliberately uses NO resp_mcp code.
All values are derived from raw fixture JSON using only stdlib + statistics.

as_of date: 2026-10-31
"""

from __future__ import annotations

import json
from collections import Counter
from pathlib import Path
from statistics import median

SNAPSHOT_DIR = Path(__file__).parent / "snapshot"
AS_OF = "2026-10-31"


def _load(name: str) -> list[dict]:
    return json.loads((SNAPSHOT_DIR / f"{name}.json").read_text())


# ── NHSN helpers ─────────────────────────────────────────────────────────────

def nhsn_latest(jurisdiction: str, pathogen: str) -> dict:
    """Return latest NHSN row (week_ending <= AS_OF) for a jurisdiction/pathogen."""
    file_map = {"GA": "nhsn_ga", "CA": "nhsn_ca", "OH": "nhsn_oh",
                "TX": "nhsn_tx", "USA": "nhsn_usa"}
    col_map = {
        "influenza": ("totalconfflunewadmper100k", "totalconfflunewadmper100klevel"),
        "covid19": ("totalconfc19newadmper100k", "totalconfc19newadmper100klevel"),
        "rsv": ("totalconfrsvnewadmper100k", "totalconfrsvnewadmper100klevel"),
    }
    rows = _load(file_map[jurisdiction])
    rows = [r for r in rows if r.get("weekendingdate", "") <= AS_OF]
    rows.sort(key=lambda r: r["weekendingdate"], reverse=True)
    if not rows:
        return {}
    r = rows[0]
    rate_col, lvl_col = col_map[pathogen]
    return {
        "week_ending": r["weekendingdate"],
        "rate_per_100k": float(r.get(rate_col, 0)),
        "level": r.get(lvl_col),
        "jurisdiction": jurisdiction,
    }


def nhsn_series(jurisdiction: str, pathogen: str, n_weeks: int = 8) -> list[dict]:
    """Return the last n_weeks of NHSN observations <= AS_OF."""
    file_map = {"GA": "nhsn_ga", "CA": "nhsn_ca", "OH": "nhsn_oh",
                "TX": "nhsn_tx", "USA": "nhsn_usa"}
    col_map = {
        "influenza": "totalconfflunewadmper100k",
        "covid19": "totalconfc19newadmper100k",
        "rsv": "totalconfrsvnewadmper100k",
    }
    rows = _load(file_map[jurisdiction])
    rows = [r for r in rows if r.get("weekendingdate", "") <= AS_OF]
    rows.sort(key=lambda r: r["weekendingdate"])
    col = col_map[pathogen]
    return [
        {"week_ending": r["weekendingdate"], "value": float(r.get(col, 0))}
        for r in rows[-n_weeks:]
    ]


# ── NHSN trend (2w vs prior 2w, same logic as analytics/trend.py) ─────────────

def nhsn_trend(jurisdiction: str, pathogen: str, lookback: int = 8) -> str:
    series = nhsn_series(jurisdiction, pathogen, lookback)
    vals = [s["value"] for s in series]
    if len(vals) < 4:
        return "insufficient_data"
    recent = (vals[-1] + vals[-2]) / 2
    prior = (vals[-3] + vals[-4]) / 2
    if prior == 0:
        return "stable"
    pct = (recent - prior) / prior
    abs_chg = recent - prior
    # hospital admissions thresholds: >=10% relative AND >=0.1 abs
    if pct >= 0.10 and abs_chg >= 0.1:
        return "increasing"
    if pct <= -0.10 and abs_chg <= -0.1:
        return "decreasing"
    return "stable"


# ── NREVSS helpers ─────────────────────────────────────────────────────────────

def nrevss_latest(pathogen: str) -> dict:
    """Return latest NREVSS national positivity (<= AS_OF) for a pathogen."""
    pathogen_map = {
        "influenza": "Influenza",
        "covid19": "COVID-19",
        "rsv": "RSV",
    }
    rows = _load("nrevss_national")
    p_label = pathogen_map[pathogen]
    rows = [r for r in rows
            if r.get("pathogen") == p_label
            and r.get("week_end", "")[:10] <= AS_OF]
    rows.sort(key=lambda r: r.get("week_end", ""), reverse=True)
    if not rows:
        return {}
    r = rows[0]
    return {
        "week_ending": r["week_end"][:10],
        "percent_positive": float(r.get("percent_test_positivity", 0)),
        "geography": "national",
        "pathogen_label": p_label,
    }


# ── NWSS helpers ──────────────────────────────────────────────────────────────

def nwss_state_summary(state: str, pathogen: str) -> dict:
    """
    Return NWSS aggregate for a state/pathogen at as_of.
    Uses per-site latest date <= AS_OF, then median wval + modal category.
    """
    file_map = {"GA": "nwss_georgia", "CA": "nwss_california",
                "OH": "nwss_ohio", "TX": "nwss_texas"}
    pathogen_map = {
        "influenza": "Influenza A virus",
        "covid19": "SARS-CoV-2",
        "rsv": "RSV",
    }
    rows = _load(file_map[state])
    target_pathogen = pathogen_map[pathogen]
    rows = [r for r in rows if r.get("pathogen_target") == target_pathogen]

    # For each site, get its most recent measurement <= AS_OF
    site_latest: dict[str, dict] = {}
    for r in rows:
        d = r.get("date_included_in_wval", "")
        if d > AS_OF:
            continue
        site = r.get("site", "")
        if site not in site_latest or d > site_latest[site].get("date_included_in_wval", ""):
            site_latest[site] = r

    if not site_latest:
        return {"status": "insufficient_coverage", "n_sites": 0}

    site_rows = list(site_latest.values())
    wvals = [float(r["site_wval"]) for r in site_rows if r.get("site_wval")]
    cats = [r["site_wval_category"] for r in site_rows if r.get("site_wval_category")]
    modal_cat = Counter(cats).most_common(1)[0][0] if cats else None
    median_wval = round(median(wvals), 2) if wvals else None

    # Representative date = most recent date_included_in_wval among selected sites
    rep_date = max(r.get("date_included_in_wval", "") for r in site_rows)

    return {
        "n_sites": len(site_rows),
        "median_wval": median_wval,
        "modal_category": modal_cat,
        "representative_date": rep_date,
    }


# ── Scan helpers ──────────────────────────────────────────────────────────────

def scan_rising_influenza_admissions(hhs_region: int | None = None) -> list[str]:
    """
    Return jurisdictions with increasing influenza hospital admissions at AS_OF.
    Uses nhsn_scan_national fixture; applies same 2w-vs-prior-2w trend logic.
    """
    rows = _load("nhsn_scan_national")
    rows = [r for r in rows if r.get("weekendingdate", "") <= AS_OF]

    # Group by jurisdiction
    by_jur: dict[str, list] = {}
    for r in rows:
        j = r["jurisdiction"]
        by_jur.setdefault(j, []).append(r)

    # HHS region map (subset — states only)
    HHS = {
        1: ["CT", "MA", "ME", "NH", "RI", "VT"],
        2: ["NJ", "NY"],
        3: ["DC", "DE", "MD", "PA", "VA", "WV"],
        4: ["AL", "FL", "GA", "KY", "MS", "NC", "SC", "TN"],
        5: ["IL", "IN", "MI", "MN", "OH", "WI"],
        6: ["AR", "LA", "NM", "OK", "TX"],
        7: ["IA", "KS", "MO", "NE"],
        8: ["CO", "MT", "ND", "SD", "UT", "WY"],
        9: ["AZ", "CA", "HI", "NV"],
        10: ["AK", "ID", "OR", "WA"],
    }

    rising = []
    for jur, jur_rows in by_jur.items():
        if jur in ("USA", "AS", "GU", "MP", "PR", "VI"):
            continue
        if hhs_region is not None and jur not in HHS.get(hhs_region, []):
            continue
        jur_rows.sort(key=lambda r: r["weekendingdate"])
        vals = [float(r.get("totalconfflunewadmper100k", 0)) for r in jur_rows]
        if len(vals) < 4:
            continue
        recent = (vals[-1] + vals[-2]) / 2
        prior = (vals[-3] + vals[-4]) / 2
        if prior == 0:
            continue
        pct = (recent - prior) / prior
        abs_chg = recent - prior
        if pct >= 0.10 and abs_chg >= 0.1:
            rising.append(jur)
    return sorted(rising)


# ── Pre-computed reference facts ───────────────────────────────────────────────
# Used as expected answers in the benchmark CSV (hidden from agent).

REFERENCE = {
    # A: Direct lookup
    "A1_ga_flu_admissions": nhsn_latest("GA", "influenza"),
    "A2_usa_flu_admissions": nhsn_latest("USA", "influenza"),
    "A3_ga_flu_ww": nwss_state_summary("GA", "influenza"),
    "A4_national_flu_positivity": nrevss_latest("influenza"),
    "A5_ca_rsv_admissions": nhsn_latest("CA", "rsv"),

    # B: Trend
    "B1_ga_flu_trend": nhsn_trend("GA", "influenza"),
    "B2_usa_flu_trend": nhsn_trend("USA", "influenza"),
    "B3_tx_covid_trend": nhsn_trend("TX", "covid19"),
    "B4_oh_rsv_trend": nhsn_trend("OH", "rsv"),
    "B5_ga_flu_8w_series": nhsn_series("GA", "influenza", 8),

    # C: Season comparison (qualitative — computed at eval time by tool)
    # Reference: current value and week number for grounding checks
    "C1_ga_flu_current": nhsn_latest("GA", "influenza"),
    "C2_usa_flu_current": nhsn_latest("USA", "influenza"),

    # D: Multi-step synthesis
    "D1_ga_all_signals": {
        "nhsn_flu": nhsn_latest("GA", "influenza"),
        "nwss_flu": nwss_state_summary("GA", "influenza"),
        "nrevss_flu": nrevss_latest("influenza"),
    },

    # E: Robustness (expected: structured errors, not data)
    "E1_nrevss_geography": "national",   # NREVSS is national-only — not state-level
    "E2_ww_not_official_cdc": True,      # NWSS aggregate is NOT an official CDC state level
    "E3_rising_states_scan": scan_rising_influenza_admissions(),
}


if __name__ == "__main__":
    import json as _json
    print(_json.dumps(REFERENCE, indent=2, default=str))
