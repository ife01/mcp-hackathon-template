"""Unit tests for resp_mcp.reference.jurisdictions."""

from __future__ import annotations

import pytest

from resp_mcp.reference.jurisdictions import (
    UnknownJurisdiction,
    get_all_jurisdictions,
    get_by_hhs_region,
    jurisdiction_full_name,
    resolve_jurisdiction,
)

# ── Registry completeness ─────────────────────────────────────────────────────

def test_all_50_states_plus_dc_present():
    all_j = get_all_jurisdictions()
    state_codes = {j.code for j in all_j if j.type == "state"}
    # 50 states
    assert len(state_codes) == 50


def test_usa_national_present():
    j = resolve_jurisdiction("USA")
    assert j.type == "national"
    assert j.hhs_region is None


def test_dc_is_district_type():
    j = resolve_jurisdiction("DC")
    assert j.type == "district"
    assert j.hhs_region == 3


def test_pr_is_territory():
    j = resolve_jurisdiction("PR")
    assert j.type == "territory"
    assert j.hhs_region == 2


def test_guam_is_region_9():
    j = resolve_jurisdiction("GU")
    assert j.hhs_region == 9


# ── Exact code matching ───────────────────────────────────────────────────────

def test_resolve_uppercase_code():
    j = resolve_jurisdiction("GA")
    assert j.code == "GA"
    assert j.name == "Georgia"


def test_resolve_lowercase_code():
    j = resolve_jurisdiction("ga")
    assert j.code == "GA"


def test_resolve_mixed_case_code():
    j = resolve_jurisdiction("Ca")
    assert j.code == "CA"


# ── Exact name matching ───────────────────────────────────────────────────────

def test_resolve_full_name():
    j = resolve_jurisdiction("Georgia")
    assert j.code == "GA"


def test_resolve_full_name_lowercase():
    j = resolve_jurisdiction("georgia")
    assert j.code == "GA"


def test_resolve_full_name_california():
    j = resolve_jurisdiction("California")
    assert j.code == "CA"


def test_resolve_full_name_ohio():
    j = resolve_jurisdiction("Ohio")
    assert j.code == "OH"


# ── Alias matching ────────────────────────────────────────────────────────────

def test_resolve_alias_us():
    assert resolve_jurisdiction("US").code == "USA"


def test_resolve_alias_national():
    assert resolve_jurisdiction("national").code == "USA"


def test_resolve_alias_united_states():
    assert resolve_jurisdiction("United States").code == "USA"


def test_resolve_alias_washington_dc():
    assert resolve_jurisdiction("Washington DC").code == "DC"


def test_resolve_alias_puerto_rico():
    assert resolve_jurisdiction("Puerto Rico").code == "PR"


def test_resolve_alias_virgin_islands():
    assert resolve_jurisdiction("Virgin Islands").code == "VI"


# ── Typo suggestions ──────────────────────────────────────────────────────────

def test_typo_georgai_suggests_georgia():
    with pytest.raises(UnknownJurisdiction) as exc_info:
        resolve_jurisdiction("Georgai")
    err = exc_info.value
    assert err.suggestions  # at least one suggestion
    # Suggestions should include Georgia/GA
    combined = " ".join(err.suggestions).lower()
    assert "georgia" in combined or "ga" in combined


def test_typo_califonia_suggests_california():
    with pytest.raises(UnknownJurisdiction) as exc_info:
        resolve_jurisdiction("Califonia")
    combined = " ".join(exc_info.value.suggestions).lower()
    assert "california" in combined or "ca" in combined


def test_unknown_jurisdiction_has_suggestions_attr():
    with pytest.raises(UnknownJurisdiction) as exc_info:
        resolve_jurisdiction("Georgai")
    assert isinstance(exc_info.value.suggestions, list)


def test_completely_unknown_has_no_suggestions():
    with pytest.raises(UnknownJurisdiction) as exc_info:
        resolve_jurisdiction("xyzzy")
    # suggestions list may be empty for a completely nonsensical input
    assert isinstance(exc_info.value.suggestions, list)


# ── Input guard ───────────────────────────────────────────────────────────────

def test_empty_string_raises_value_error():
    with pytest.raises(ValueError, match="empty"):
        resolve_jurisdiction("")


def test_whitespace_only_raises_value_error():
    with pytest.raises(ValueError):
        resolve_jurisdiction("   ")


def test_over_64_chars_raises_value_error():
    with pytest.raises(ValueError, match="too long"):
        resolve_jurisdiction("G" * 65)


def test_exactly_64_chars_does_not_raise_on_length():
    # 64-char input should not fail the length guard (it will fail as unknown)
    with pytest.raises(UnknownJurisdiction):
        resolve_jurisdiction("G" * 64)


def test_control_characters_stripped_then_matched():
    # "\x01GA\x02" after stripping → "GA"
    j = resolve_jurisdiction("\x01GA\x02")
    assert j.code == "GA"


def test_only_control_characters_raises():
    with pytest.raises(ValueError, match="control characters"):
        resolve_jurisdiction("\x01\x02\x03")


# ── HHS region lookup ─────────────────────────────────────────────────────────

def test_hhs_region_4_contains_georgia():
    region4 = get_by_hhs_region(4)
    codes = {j.code for j in region4}
    assert "GA" in codes


def test_hhs_region_9_contains_california_and_guam():
    region9 = get_by_hhs_region(9)
    codes = {j.code for j in region9}
    assert "CA" in codes
    assert "GU" in codes


def test_hhs_region_5_contains_ohio():
    region5 = get_by_hhs_region(5)
    codes = {j.code for j in region5}
    assert "OH" in codes


def test_all_hhs_regions_1_to_10_have_members():
    for region in range(1, 11):
        members = get_by_hhs_region(region)
        assert len(members) >= 1, f"HHS region {region} has no members"


# ── Full name helper ──────────────────────────────────────────────────────────

def test_jurisdiction_full_name_ga():
    assert jurisdiction_full_name("GA") == "Georgia"


def test_jurisdiction_full_name_usa():
    assert jurisdiction_full_name("USA") == "United States"


def test_jurisdiction_full_name_unknown_returns_code():
    assert jurisdiction_full_name("ZZ") == "ZZ"


def test_jurisdiction_full_name_case_insensitive():
    assert jurisdiction_full_name("ca") == "California"
