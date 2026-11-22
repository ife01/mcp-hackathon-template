"""Deterministic tool-level eval — runs all 15 benchmark cases against the
MCP server directly (no LLM) and checks grounding, schema, and error-handling
invariants. No network access to model providers required.

Run from repo root:
    uv run python eval/run_eval.py

Exit code 0 = all checks passed. Non-zero = failures (see output).
"""

from __future__ import annotations

import asyncio
import json
import sys
from datetime import date, datetime, timezone
from pathlib import Path
from unittest.mock import AsyncMock, patch

# Ensure the src package is importable
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from resp_mcp.models.common import Provenance, WeeklyObservation  # noqa: E402
from resp_mcp.server import mcp  # noqa: E402

AS_OF = "2026-10-31"
SNAPSHOT_DIR = Path(__file__).parent / "snapshot"

PASS = 0
FAIL = 0
_results: list[dict] = []


def _prov(dataset_id: str, geo: str, week: str | None = None) -> Provenance:
    return Provenance(
        dataset_id=dataset_id,
        dataset_name="NHSN" if "vdzy" in dataset_id else "CDC",
        url=f"https://data.cdc.gov/resource/{dataset_id}.json",  # type: ignore[arg-type]
        latest_week_ending=date.fromisoformat(week) if week else None,
        retrieved_at=datetime.now(timezone.utc),
        geography_level=geo,
        notes=[],
    )


def _load_snapshot(name: str) -> list[dict]:
    return json.loads((SNAPSHOT_DIR / f"{name}.json").read_text())


def _obs_from_nhsn(rows: list[dict], jur: str, pathogen: str, as_of: str) -> list[WeeklyObservation]:
    col = {
        "influenza": "totalconfflunewadmper100k",
        "covid19": "totalconfc19newadmper100k",
        "rsv": "totalconfrsvnewadmper100k",
    }[pathogen]
    lvl_col = {
        "influenza": "totalconfflunewadmper100klevel",
        "covid19": "totalconfc19newadmper100klevel",
        "rsv": "totalconfrsvnewadmper100klevel",
    }[pathogen]
    out = []
    for r in rows:
        if r.get("weekendingdate", "") > as_of:
            continue
        v = r.get(col)
        out.append(WeeklyObservation(
            jurisdiction=jur,
            week_ending=date.fromisoformat(r["weekendingdate"]),
            value=float(v) if v else None,
            unit="admissions_per_100k",
            official_level=r.get(lvl_col),
        ))
    out.sort(key=lambda o: o.week_ending)
    return out


def _result_dict(result) -> dict:
    if hasattr(result, "content") and result.content:
        item = result.content[0]
        text = item.text if hasattr(item, "text") else str(item)
        return json.loads(text)
    return {}


def check(name: str, condition: bool, detail: str = "") -> None:
    global PASS, FAIL
    status = "PASS" if condition else "FAIL"
    if condition:
        PASS += 1
    else:
        FAIL += 1
    _results.append({"name": name, "status": status, "detail": detail})
    if not condition:
        print(f"  ✗ FAIL: {name} — {detail}", file=sys.stderr)


# ── Load frozen snapshots ─────────────────────────────────────────────────────

nhsn_ga = _load_snapshot("nhsn_ga")
nhsn_usa = _load_snapshot("nhsn_usa")
nhsn_ca = _load_snapshot("nhsn_ca")
nhsn_oh = _load_snapshot("nhsn_oh")
nhsn_tx = _load_snapshot("nhsn_tx")

ga_flu_obs = _obs_from_nhsn(nhsn_ga, "GA", "influenza", AS_OF)
usa_flu_obs = _obs_from_nhsn(nhsn_usa, "USA", "influenza", AS_OF)
ga_covid_obs = _obs_from_nhsn(nhsn_ga, "GA", "covid19", AS_OF)
ca_rsv_obs = _obs_from_nhsn(nhsn_ca, "CA", "rsv", AS_OF)
oh_rsv_obs = _obs_from_nhsn(nhsn_oh, "OH", "rsv", AS_OF)
tx_covid_obs = _obs_from_nhsn(nhsn_tx, "TX", "covid19", AS_OF)

ga_prov = _prov("vdzy-6i9v", "state", AS_OF)
usa_prov = _prov("vdzy-6i9v", "national", AS_OF)
ca_prov = _prov("vdzy-6i9v", "state", AS_OF)
oh_prov = _prov("vdzy-6i9v", "state", AS_OF)
tx_prov = _prov("vdzy-6i9v", "state", AS_OF)
ww_prov = _prov("atcp-73re", "site_aggregate", "2026-08-10")
ww_prov.notes.append("Wastewater aggregate is server-computed median across NWSS sites, not an official CDC state classification.")
nrevss_prov = _prov("seuz-s2cv", "national", AS_OF)
nrevss_prov.notes.append("Test positivity data is only available at the national level from this source")

empty_ww = []
empty_nrevss = []


async def run_checks() -> None:
    # ── A: Direct lookup ─────────────────────────────────────────────────────

    # A1: GA flu admissions
    with (
        patch("resp_mcp.sources.nhsn.fetch_series", new_callable=AsyncMock,
              return_value=(ga_flu_obs, ga_prov)),
        patch("resp_mcp.sources.nwss.fetch_series", new_callable=AsyncMock,
              return_value=(empty_ww, ww_prov)),
        patch("resp_mcp.sources.nrevss.fetch_series", new_callable=AsyncMock,
              return_value=(empty_nrevss, nrevss_prov)),
    ):
        r = _result_dict(await mcp.call_tool("get_respiratory_snapshot", {
            "jurisdiction": "GA", "pathogens": ["influenza"], "as_of": AS_OF,
        }))
    check("A1_ga_flu_snapshot_ok", r.get("jurisdiction") == "GA")
    psnap = r.get("pathogens", [{}])[0]
    sigs = {s["signal"]: s for s in psnap.get("signals", [])}
    ha = sigs.get("hospital_admissions", {})
    latest_val = (ha.get("latest") or {}).get("value")
    check("A1_ga_flu_rate_1_76", abs(float(latest_val or 0) - 1.76) < 0.05,
          f"got {latest_val}")
    check("A1_ga_flu_level_low",
          (ha.get("latest") or {}).get("official_level") == "Low")
    check("A1_ga_flu_prov_attached",
          ha.get("provenance", {}).get("dataset_id") == "vdzy-6i9v")

    # A2: USA flu admissions
    with (
        patch("resp_mcp.sources.nhsn.fetch_series", new_callable=AsyncMock,
              return_value=(usa_flu_obs, usa_prov)),
        patch("resp_mcp.sources.nwss.fetch_series", new_callable=AsyncMock,
              return_value=(empty_ww, ww_prov)),
        patch("resp_mcp.sources.nrevss.fetch_series", new_callable=AsyncMock,
              return_value=(empty_nrevss, nrevss_prov)),
    ):
        r = _result_dict(await mcp.call_tool("get_respiratory_snapshot", {
            "jurisdiction": "USA", "pathogens": ["influenza"], "as_of": AS_OF,
        }))
    psnap = r.get("pathogens", [{}])[0]
    sigs = {s["signal"]: s for s in psnap.get("signals", [])}
    ha = sigs.get("hospital_admissions", {})
    latest_val = (ha.get("latest") or {}).get("value")
    check("A2_usa_flu_rate_2_49", abs(float(latest_val or 0) - 2.49) < 0.05,
          f"got {latest_val}")

    # A3: NREVSS national-only caveat present in output
    with (
        patch("resp_mcp.sources.nhsn.fetch_series", new_callable=AsyncMock,
              return_value=(ga_flu_obs, ga_prov)),
        patch("resp_mcp.sources.nwss.fetch_series", new_callable=AsyncMock,
              return_value=(empty_ww, ww_prov)),
        patch("resp_mcp.sources.nrevss.fetch_series", new_callable=AsyncMock,
              return_value=(empty_nrevss, nrevss_prov)),
    ):
        r = _result_dict(await mcp.call_tool("get_respiratory_snapshot", {
            "jurisdiction": "GA", "pathogens": ["influenza"], "as_of": AS_OF,
        }))
    caveats_text = " ".join(str(c) for c in r.get("caveats", []))
    check("A3_nrevss_national_caveat",
          "national" in caveats_text.lower(),
          f"caveats: {r.get('caveats')}")

    # A4: Wastewater aggregate caveat present
    check("A4_ww_aggregate_caveat",
          "not an official" in caveats_text.lower() or "server-computed" in caveats_text.lower()
          or "aggregate" in caveats_text.lower(),
          f"caveats: {r.get('caveats')}")

    # ── B: Trend ─────────────────────────────────────────────────────────────

    import resp_mcp.tools.trend as _trend_mod
    from resp_mcp.models.common import Signal as _Signal

    # B1: GA flu trend — expect increasing
    ga_flu_trend_mock = AsyncMock(return_value=(ga_flu_obs, ga_prov))
    with patch.dict(_trend_mod._ADAPTERS, {_Signal.hospital_admissions: ga_flu_trend_mock}):
        r = _result_dict(await mcp.call_tool("assess_trend", {
            "jurisdiction": "GA", "pathogen": "influenza",
            "signal": "hospital_admissions", "as_of": AS_OF,
        }))
    check("B1_ga_flu_trend_increasing",
          r.get("trend", {}).get("direction") == "increasing",
          f"got direction={r.get('trend',{}).get('direction')}")
    check("B1_trend_series_present", len(r.get("series", [])) > 0)
    check("B1_trend_basis_server_heuristic",
          r.get("trend", {}).get("basis") == "server_heuristic")

    # B2: assess_trend returns structured error for bad jurisdiction
    r = _result_dict(await mcp.call_tool("assess_trend", {
        "jurisdiction": "Georgai", "pathogen": "influenza",
        "signal": "hospital_admissions",
    }))
    check("B2_bad_jur_structured_error",
          r.get("error") == "unknown_jurisdiction",
          f"got {r.get('error')}")
    check("B2_bad_jur_has_suggestions",
          len(r.get("suggestions", [])) > 0)

    # B3: as_of too early returns error
    r = _result_dict(await mcp.call_tool("assess_trend", {
        "jurisdiction": "GA", "pathogen": "influenza",
        "signal": "hospital_admissions", "as_of": "2015-01-01",
    }))
    check("B3_as_of_too_early_error",
          r.get("error") == "invalid_input",
          f"got {r.get('error')}")

    # B4: invalid pathogen returns error
    r = _result_dict(await mcp.call_tool("assess_trend", {
        "jurisdiction": "GA", "pathogen": "flu B",
        "signal": "hospital_admissions",
    }))
    check("B4_bad_pathogen_error",
          r.get("error") == "invalid_input",
          f"got {r.get('error')}")

    # B5: flu alias resolves
    ga_flu_trend_mock2 = AsyncMock(return_value=(ga_flu_obs, ga_prov))
    with patch.dict(_trend_mod._ADAPTERS, {_Signal.hospital_admissions: ga_flu_trend_mock2}):
        r = _result_dict(await mcp.call_tool("assess_trend", {
            "jurisdiction": "GA", "pathogen": "flu",
            "signal": "hospital_admissions", "as_of": AS_OF,
        }))
    check("B5_flu_alias_resolves", r.get("pathogen") == "influenza",
          f"got {r.get('pathogen')}")

    # ── C: Season comparison ──────────────────────────────────────────────────

    import resp_mcp.tools.seasons as _seasons_mod
    ga_seasons_mock = AsyncMock(return_value=(ga_flu_obs, ga_prov))
    with patch.dict(_seasons_mod._ADAPTERS, {_Signal.hospital_admissions: ga_seasons_mock}):
        r = _result_dict(await mcp.call_tool("compare_to_prior_seasons", {
            "jurisdiction": "GA", "pathogen": "influenza",
            "signal": "hospital_admissions", "as_of": AS_OF,
        }))
    check("C1_season_comparison_present", "comparison" in r)
    check("C1_season_has_current_season",
          "current_season" in r.get("comparison", {}))
    check("C1_season_prov_attached",
          r.get("provenance", {}).get("dataset_id") == "vdzy-6i9v")

    # ── D: Scan ───────────────────────────────────────────────────────────────

    # Load all-jurisdiction data from scan snapshot
    scan_rows = _load_snapshot("nhsn_scan_national")
    scan_obs_map: dict[str, list[WeeklyObservation]] = {}
    for jur_code in set(r["jurisdiction"] for r in scan_rows):
        rows_jur = [r for r in scan_rows if r["jurisdiction"] == jur_code]
        scan_obs_map[jur_code] = _obs_from_nhsn(rows_jur, jur_code, "influenza", AS_OF)

    scan_prov = _prov("vdzy-6i9v", "state", AS_OF)

    async def _scan_fetch(jur, pathogen, start, end):
        obs = scan_obs_map.get(jur.code, [])
        return obs, scan_prov

    import resp_mcp.tools.scan as _scan_mod
    with patch.dict(_scan_mod._ADAPTERS, {_Signal.hospital_admissions: _scan_fetch}):
        r = _result_dict(await mcp.call_tool("find_jurisdictions_with_rising_activity", {
            "pathogen": "influenza", "signal": "hospital_admissions",
            "as_of": AS_OF, "limit": 50,
        }))
    rising_codes = [row["jurisdiction"] for row in r.get("rising", [])]
    n_scanned = r.get("n_jurisdictions_scanned", 0)
    check("D1_scan_returns_rising_list", isinstance(r.get("rising"), list))
    check("D1_scan_n_scanned_positive", n_scanned > 0, f"got {n_scanned}")
    check("D1_scan_ga_in_rising", "GA" in rising_codes,
          f"rising: {rising_codes[:10]}")
    # Scan total != displayed rows (n_scanned > len(rising))
    check("D2_scan_total_distinct_from_rows",
          n_scanned >= len(rising_codes),
          f"n_scanned={n_scanned}, len(rising)={len(rising_codes)}")

    # ── E: Public health invariants ───────────────────────────────────────────

    # E1: NREVSS geographic caveat propagates from snapshot tool
    with (
        patch("resp_mcp.sources.nhsn.fetch_series", new_callable=AsyncMock,
              return_value=(ga_flu_obs, ga_prov)),
        patch("resp_mcp.sources.nwss.fetch_series", new_callable=AsyncMock,
              return_value=(empty_ww, ww_prov)),
        patch("resp_mcp.sources.nrevss.fetch_series", new_callable=AsyncMock,
              return_value=(empty_nrevss, nrevss_prov)),
    ):
        r = _result_dict(await mcp.call_tool("get_respiratory_snapshot", {
            "jurisdiction": "GA", "pathogens": ["influenza"], "as_of": AS_OF,
        }))
    psnap = r.get("pathogens", [{}])[0]
    sigs = {s["signal"]: s for s in psnap.get("signals", [])}
    test_pos = sigs.get("test_positivity", {})
    tp_prov_geo = (test_pos.get("provenance") or {}).get("geography_level")
    check("E1_nrevss_geography_level_national",
          tp_prov_geo == "national",
          f"geography_level={tp_prov_geo}")

    # E2: NWSS provenance notes include aggregate caveat
    ww_sig = sigs.get("wastewater", {})
    ww_notes = (ww_sig.get("provenance") or {}).get("notes", [])
    check("E2_ww_aggregate_note_in_provenance",
          any("not an official" in n.lower() or "aggregate" in n.lower()
              or "server-computed" in n.lower() for n in ww_notes),
          f"notes: {ww_notes}")

    # E3: Trend result carries basis=server_heuristic (never CDC_official)
    ga_flu_trend_mock3 = AsyncMock(return_value=(ga_flu_obs, ga_prov))
    with patch.dict(_trend_mod._ADAPTERS, {_Signal.hospital_admissions: ga_flu_trend_mock3}):
        r = _result_dict(await mcp.call_tool("assess_trend", {
            "jurisdiction": "GA", "pathogen": "influenza",
            "signal": "hospital_admissions", "as_of": AS_OF,
        }))
    check("E3_trend_basis_never_official_cdc",
          r.get("trend", {}).get("basis") != "official_cdc_level_change",
          f"basis={r.get('trend',{}).get('basis')}")

    # E4: Partial source failure (NHSN up, NWSS down) → tool still succeeds, caveat present

    async def _failing_nwss(*a, **kw):
        return [], ww_prov  # returns empty, no exception — simulates no-data

    with (
        patch("resp_mcp.sources.nhsn.fetch_series", new_callable=AsyncMock,
              return_value=(ga_flu_obs, ga_prov)),
        patch("resp_mcp.sources.nwss.fetch_series", side_effect=_failing_nwss),
        patch("resp_mcp.sources.nrevss.fetch_series", new_callable=AsyncMock,
              return_value=(empty_nrevss, nrevss_prov)),
    ):
        r = _result_dict(await mcp.call_tool("get_respiratory_snapshot", {
            "jurisdiction": "GA", "pathogens": ["influenza"], "as_of": AS_OF,
        }))
    check("E4_partial_source_failure_no_crash",
          r.get("jurisdiction") == "GA",
          f"error={r.get('error')}")

    # E5: Zero stdout during tool call (MCP stdio safety)
    import io
    captured = io.StringIO()
    original_stdout = sys.stdout
    sys.stdout = captured
    try:
        ga_flu_trend_mock4 = AsyncMock(return_value=(ga_flu_obs, ga_prov))
        with patch.dict(_trend_mod._ADAPTERS, {_Signal.hospital_admissions: ga_flu_trend_mock4}):
            await mcp.call_tool("assess_trend", {
                "jurisdiction": "GA", "pathogen": "influenza",
                "signal": "hospital_admissions", "as_of": AS_OF,
            })
    finally:
        sys.stdout = original_stdout
    check("E5_zero_stdout",
          captured.getvalue() == "",
          f"stdout: {captured.getvalue()!r}")


def print_summary() -> None:
    total = PASS + FAIL
    print(f"\n{'='*60}")
    print(f"Deterministic eval: {PASS}/{total} checks passed")
    if FAIL:
        print("\nFailed checks:")
        for r in _results:
            if r["status"] == "FAIL":
                print(f"  ✗ {r['name']}: {r['detail']}")
    else:
        print("All checks passed ✓")
    print("=" * 60)


def main() -> None:
    asyncio.run(run_checks())
    print_summary()
    sys.exit(0 if FAIL == 0 else 1)


if __name__ == "__main__":
    main()
