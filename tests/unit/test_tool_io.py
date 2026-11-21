"""Unit tests for models/tool_io.py — schema validation and round-trip."""

from __future__ import annotations

import json
from datetime import date, datetime, timezone
from pathlib import Path

import pytest
from pydantic import ValidationError

from resp_mcp.models.common import (
    Pathogen,
    Provenance,
    Signal,
    WeeklyObservation,
)
from resp_mcp.models.tool_io import (
    PathogenSnapshot,
    ScanInput,
    ScanOutput,
    ScanRow,
    SeasonInput,
    SeasonOutput,
    SeasonPoint,
    SeasonSummary,
    SignalReading,
    SnapshotInput,
    SnapshotOutput,
    TrendInput,
    TrendOutput,
    TrendSummary,
)

SCHEMA_DIR = Path("docs/schemas")

# ── Helpers ───────────────────────────────────────────────────────────────────


def _prov() -> Provenance:
    return Provenance(
        dataset_id="vdzy-6i9v",
        dataset_name="NHSN",
        url="https://data.cdc.gov/resource/vdzy-6i9v.json",  # type: ignore[arg-type]
        latest_week_ending=date(2026, 11, 14),
        retrieved_at=datetime.now(timezone.utc),
        geography_level="state",
    )


def _obs() -> WeeklyObservation:
    return WeeklyObservation(
        jurisdiction="GA",
        week_ending=date(2026, 11, 14),
        value=2.47,
        unit="admissions_per_100k",
        official_level="Low",
    )


def _trend_summary() -> TrendSummary:
    return TrendSummary(
        direction="increasing",
        pct_change=0.15,
        abs_change=0.3,
        window_weeks=4,
        method="2w_vs_prior_2w",
        basis="server_heuristic",
    )


# ── SnapshotInput validation ──────────────────────────────────────────────────


def test_snapshot_input_defaults():
    inp = SnapshotInput(jurisdiction="GA")
    assert inp.jurisdiction == "GA"
    assert len(inp.pathogens) == 3
    assert inp.as_of is None


def test_snapshot_input_jurisdiction_too_long():
    with pytest.raises(ValidationError):
        SnapshotInput(jurisdiction="X" * 65)


def test_snapshot_input_jurisdiction_empty():
    with pytest.raises(ValidationError):
        SnapshotInput(jurisdiction="")


def test_snapshot_input_as_of_pattern_valid():
    inp = SnapshotInput(jurisdiction="GA", as_of="2026-10-31")
    assert inp.as_of == "2026-10-31"


def test_snapshot_input_as_of_none():
    inp = SnapshotInput(jurisdiction="GA", as_of=None)
    assert inp.as_of is None


# ── TrendInput validation ─────────────────────────────────────────────────────


def test_trend_input_defaults():
    inp = TrendInput(
        jurisdiction="GA",
        pathogen=Pathogen.influenza,
        signal=Signal.hospital_admissions,
    )
    assert inp.lookback_weeks == 8
    assert inp.as_of is None


def test_trend_input_lookback_below_minimum():
    with pytest.raises(ValidationError):
        TrendInput(
            jurisdiction="GA",
            pathogen=Pathogen.influenza,
            signal=Signal.hospital_admissions,
            lookback_weeks=3,
        )


def test_trend_input_lookback_above_maximum():
    with pytest.raises(ValidationError):
        TrendInput(
            jurisdiction="GA",
            pathogen=Pathogen.influenza,
            signal=Signal.hospital_admissions,
            lookback_weeks=53,
        )


def test_trend_input_lookback_at_minimum():
    inp = TrendInput(
        jurisdiction="GA",
        pathogen=Pathogen.influenza,
        signal=Signal.hospital_admissions,
        lookback_weeks=4,
    )
    assert inp.lookback_weeks == 4


# ── SeasonInput validation ────────────────────────────────────────────────────


def test_season_input_defaults():
    inp = SeasonInput(
        jurisdiction="GA",
        pathogen=Pathogen.influenza,
        signal=Signal.hospital_admissions,
    )
    assert inp.prior_seasons == 3


def test_season_input_prior_seasons_above_max():
    with pytest.raises(ValidationError):
        SeasonInput(
            jurisdiction="GA",
            pathogen=Pathogen.influenza,
            signal=Signal.hospital_admissions,
            prior_seasons=6,
        )


# ── ScanInput validation ──────────────────────────────────────────────────────


def test_scan_input_defaults():
    inp = ScanInput(pathogen=Pathogen.influenza, signal=Signal.hospital_admissions)
    assert inp.limit == 10
    assert inp.hhs_region is None
    assert inp.min_level is None


def test_scan_input_hhs_region_out_of_range():
    with pytest.raises(ValidationError):
        ScanInput(
            pathogen=Pathogen.influenza,
            signal=Signal.hospital_admissions,
            hhs_region=11,
        )


def test_scan_input_limit_above_max():
    with pytest.raises(ValidationError):
        ScanInput(
            pathogen=Pathogen.influenza,
            signal=Signal.hospital_admissions,
            limit=57,
        )


def test_scan_input_min_level_too_long():
    with pytest.raises(ValidationError):
        ScanInput(
            pathogen=Pathogen.influenza,
            signal=Signal.hospital_admissions,
            min_level="X" * 17,
        )


# ── TrendOutput round-trip ────────────────────────────────────────────────────


def test_trend_output_round_trip_json():
    out = TrendOutput(
        jurisdiction="GA",
        pathogen=Pathogen.influenza,
        signal=Signal.hospital_admissions,
        series=[_obs()],
        trend=_trend_summary(),
        provenance=_prov(),
        summary="Influenza hospital admissions in GA are increasing.",
        caveats=["server heuristic, not CDC classification"],
    )
    dumped = out.model_dump_json()
    loaded = TrendOutput.model_validate_json(dumped)
    assert loaded.jurisdiction == "GA"
    assert loaded.pathogen == Pathogen.influenza
    assert loaded.trend.direction == "increasing"
    assert loaded.series[0].value == pytest.approx(2.47)


# ── SnapshotOutput round-trip ─────────────────────────────────────────────────


def test_snapshot_output_round_trip():
    reading = SignalReading(
        signal=Signal.hospital_admissions,
        status="ok",
        latest=_obs(),
        trend=_trend_summary(),
        provenance=_prov(),
    )
    ps = PathogenSnapshot(
        pathogen=Pathogen.influenza,
        signals=[reading],
        concordance_pattern="concordant_increase",
    )
    out = SnapshotOutput(
        jurisdiction="GA",
        as_of_week_ending=date(2026, 11, 14),
        pathogens=[ps],
        summary="Overall influenza activity is increasing in GA.",
        caveats=[],
    )
    dumped = out.model_dump_json()
    loaded = SnapshotOutput.model_validate_json(dumped)
    assert loaded.jurisdiction == "GA"
    assert loaded.pathogens[0].pathogen == Pathogen.influenza
    assert loaded.pathogens[0].signals[0].status == "ok"


# ── SeasonOutput round-trip ───────────────────────────────────────────────────


def test_season_output_round_trip():
    comparison = SeasonSummary(
        current_season="2026-27",
        current_week_of_season=19,
        current_value=2.5,
        prior=[SeasonPoint(
            season="2025-26", week_ending=date(2025, 11, 15),
            week_of_season=19, value=3.1,
        )],
        rank_vs_prior=2,
        pct_of_prior_peak=80.6,
        method="week_of_season_aligned",
    )
    out = SeasonOutput(
        jurisdiction="GA",
        pathogen=Pathogen.influenza,
        signal=Signal.hospital_admissions,
        comparison=comparison,
        provenance=_prov(),
        summary="Activity is below the prior-season peak.",
    )
    dumped = out.model_dump_json()
    loaded = SeasonOutput.model_validate_json(dumped)
    assert loaded.comparison.current_season == "2026-27"
    assert loaded.comparison.rank_vs_prior == 2


# ── ScanOutput round-trip ─────────────────────────────────────────────────────


def test_scan_output_round_trip():
    out = ScanOutput(
        pathogen=Pathogen.influenza,
        signal=Signal.hospital_admissions,
        as_of_week_ending=date(2026, 11, 14),
        rising=[
            ScanRow(
                jurisdiction="GA",
                trend_direction="increasing",
                latest_value=2.5,
                latest_week_ending=date(2026, 11, 14),
                official_level="Low",
                pct_change=0.18,
            )
        ],
        provenance=_prov(),
        n_jurisdictions_scanned=51,
        n_insufficient_data=3,
        summary="3 jurisdictions show rising influenza hospital admissions.",
    )
    dumped = out.model_dump_json()
    loaded = ScanOutput.model_validate_json(dumped)
    assert loaded.n_jurisdictions_scanned == 51
    assert loaded.rising[0].jurisdiction == "GA"


# ── TrendSummary validation ───────────────────────────────────────────────────


def test_trend_summary_missing_required_fields():
    with pytest.raises(ValidationError):
        TrendSummary(direction="increasing")  # missing window_weeks, method, basis


def test_trend_summary_pct_change_none_allowed():
    ts = TrendSummary(
        direction="insufficient_data",
        pct_change=None,
        abs_change=None,
        window_weeks=2,
        method="2w_vs_prior_2w",
        basis="server_heuristic",
    )
    assert ts.pct_change is None


# ── Schema files exist and are valid JSON ─────────────────────────────────────


@pytest.mark.parametrize("name", [
    "snapshot_input", "snapshot_output",
    "trend_input", "trend_output",
    "season_input", "season_output",
    "scan_input", "scan_output",
])
def test_schema_file_exists_and_is_valid_json(name: str):
    path = SCHEMA_DIR / f"{name}.json"
    assert path.exists(), f"Schema file not found: {path}"
    schema = json.loads(path.read_text())
    assert "title" in schema or "properties" in schema


def test_trend_input_schema_has_jurisdiction_bounds():
    schema = json.loads((SCHEMA_DIR / "trend_input.json").read_text())
    props = schema.get("properties", {})
    assert props["jurisdiction"]["minLength"] == 1
    assert props["jurisdiction"]["maxLength"] == 64


def test_trend_input_schema_has_lookback_bounds():
    schema = json.loads((SCHEMA_DIR / "trend_input.json").read_text())
    props = schema.get("properties", {})
    assert props["lookback_weeks"]["minimum"] == 4
    assert props["lookback_weeks"]["maximum"] == 52


def test_scan_input_schema_has_hhs_region_bounds():
    schema = json.loads((SCHEMA_DIR / "scan_input.json").read_text())
    props = schema.get("properties", {})
    hhs = props.get("hhs_region", {})
    # hhs_region is anyOf[int, null] in Pydantic v2
    any_of = hhs.get("anyOf", [])
    int_schema = next((s for s in any_of if s.get("type") == "integer"), None)
    assert int_schema is not None
    assert int_schema.get("minimum") == 1
    assert int_schema.get("maximum") == 10
