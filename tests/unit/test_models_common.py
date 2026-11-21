"""Unit tests for resp_mcp.models.common."""

from __future__ import annotations

import json
from datetime import date, datetime, timezone

import pytest
from pydantic import ValidationError

from resp_mcp.models.common import (
    Pathogen,
    Provenance,
    Signal,
    WeeklyObservation,
)

NOW = datetime(2026, 11, 20, 21, 0, 0, tzinfo=timezone.utc)
WEEK = date(2026, 11, 14)


# ── Enums ─────────────────────────────────────────────────────────────────────

def test_pathogen_values():
    assert Pathogen.influenza == "influenza"
    assert Pathogen.covid19 == "covid19"
    assert Pathogen.rsv == "rsv"


def test_signal_values():
    assert Signal.hospital_admissions == "hospital_admissions"
    assert Signal.wastewater == "wastewater"
    assert Signal.test_positivity == "test_positivity"


def test_pathogen_from_string():
    assert Pathogen("influenza") is Pathogen.influenza


def test_signal_from_string():
    assert Signal("wastewater") is Signal.wastewater


# ── Provenance ────────────────────────────────────────────────────────────────

def _make_provenance(**kwargs) -> Provenance:
    defaults = dict(
        dataset_id="vdzy-6i9v",
        dataset_name="NHSN Hospital Admissions",
        url="https://data.cdc.gov/resource/vdzy-6i9v.json",
        latest_week_ending=WEEK,
        retrieved_at=NOW,
        geography_level="state",
    )
    defaults.update(kwargs)
    return Provenance(**defaults)


def test_provenance_round_trip_json():
    p = _make_provenance()
    data = json.loads(p.model_dump_json())
    p2 = Provenance(**data)
    assert p2.dataset_id == p.dataset_id
    assert p2.geography_level == p.geography_level


def test_provenance_latest_week_ending_none():
    p = _make_provenance(latest_week_ending=None)
    assert p.latest_week_ending is None


def test_provenance_notes_default_empty():
    p = _make_provenance()
    assert p.notes == []


def test_provenance_notes_list():
    p = _make_provenance(notes=["wastewater measures influenza A only"])
    assert len(p.notes) == 1


def test_provenance_geography_levels():
    for level in ("national", "state", "hhs_region", "site_aggregate"):
        p = _make_provenance(geography_level=level)
        assert p.geography_level == level


def test_provenance_invalid_geography_level():
    with pytest.raises(ValidationError):
        _make_provenance(geography_level="county")


def test_provenance_source_last_updated_optional():
    p = _make_provenance(source_last_updated=None)
    assert p.source_last_updated is None


# ── WeeklyObservation ─────────────────────────────────────────────────────────

def _make_obs(**kwargs) -> WeeklyObservation:
    defaults = dict(
        jurisdiction="GA",
        week_ending=WEEK,
        value=2.47,
        unit="admissions_per_100k",
    )
    defaults.update(kwargs)
    return WeeklyObservation(**defaults)


def test_observation_round_trip_json():
    obs = _make_obs()
    data = json.loads(obs.model_dump_json())
    obs2 = WeeklyObservation(**data)
    assert obs2.jurisdiction == "GA"
    assert obs2.value == 2.47


def test_observation_value_can_be_none():
    obs = _make_obs(value=None)
    assert obs.value is None


def test_observation_official_level_optional():
    obs = _make_obs(official_level="Low")
    assert obs.official_level == "Low"


def test_observation_coverage_optional():
    obs = _make_obs(coverage={"n_sites": 4})
    assert obs.coverage == {"n_sites": 4}


def test_observation_all_valid_units():
    for unit in ("admissions_per_100k", "admissions_count",
                 "percent_positive", "wval"):
        obs = _make_obs(unit=unit)
        assert obs.unit == unit


def test_observation_invalid_unit():
    with pytest.raises(ValidationError):
        _make_obs(unit="copies_per_liter")


def test_observation_coverage_mixed_types():
    obs = _make_obs(coverage={"n_sites": 4, "pct_hospitals": 68.1})
    assert obs.coverage["n_sites"] == 4
    assert obs.coverage["pct_hospitals"] == 68.1
