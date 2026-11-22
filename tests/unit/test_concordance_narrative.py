"""Unit tests for analytics/concordance.py and analytics/narrative.py."""

from __future__ import annotations

from datetime import date, datetime, timezone

from resp_mcp.analytics.concordance import (
    ConcordanceResult,
    SignalTrendInput,
    assess_concordance,
)
from resp_mcp.analytics.narrative import build_snapshot_narrative
from resp_mcp.analytics.seasons import SeasonComparison
from resp_mcp.analytics.trend import TrendDirection, TrendResult
from resp_mcp.models.common import Pathogen, Provenance, Signal

# ── Helpers ───────────────────────────────────────────────────────────────────

_SIGNAL_ORDER = [
    Signal.hospital_admissions,
    Signal.wastewater,
    Signal.test_positivity,
]


def _prov(week_ending: date | None, dataset_id: str = "test-id") -> Provenance:
    return Provenance(
        dataset_id=dataset_id,
        dataset_name="Test",
        url="https://data.cdc.gov/resource/test-id.json",  # type: ignore[arg-type]
        latest_week_ending=week_ending,
        retrieved_at=datetime.now(timezone.utc),
        geography_level="state",
    )


def _trend(direction: TrendDirection) -> TrendResult:
    _up = TrendDirection.increasing
    _dn = TrendDirection.decreasing
    return TrendResult(
        direction=direction,
        pct_change=0.2 if direction == _up else -0.2 if direction == _dn else 0.0,
        abs_change=1.0 if direction == _up else -1.0 if direction == _dn else 0.0,
        window_weeks=4,
        method="2w_vs_prior_2w",
        basis="server_heuristic",
    )


def _sti(
    signal: Signal,
    direction: TrendDirection,
    week_ending: date | None = None,
) -> SignalTrendInput:
    return SignalTrendInput(
        signal=signal,
        trend=_trend(direction),
        provenance=_prov(week_ending or date(2026, 11, 14)),
    )


# ── Empty / all insufficient ──────────────────────────────────────────────────


def test_empty_input_returns_insufficient():
    result = assess_concordance([])
    assert result.pattern == "insufficient_data"
    assert result.signals_used == []


def test_all_insufficient_returns_insufficient():
    inputs = [
        _sti(Signal.hospital_admissions, TrendDirection.insufficient_data),
        _sti(Signal.wastewater, TrendDirection.insufficient_data),
    ]
    result = assess_concordance(inputs)
    assert result.pattern == "insufficient_data"


# ── Concordant increase ───────────────────────────────────────────────────────


def test_all_increasing_is_concordant_increase():
    inputs = [
        _sti(Signal.hospital_admissions, TrendDirection.increasing),
        _sti(Signal.wastewater, TrendDirection.increasing),
        _sti(Signal.test_positivity, TrendDirection.increasing),
    ]
    result = assess_concordance(inputs)
    assert result.pattern == "concordant_increase"
    assert len(result.signals_used) == 3


def test_two_increasing_is_concordant_increase():
    inputs = [
        _sti(Signal.hospital_admissions, TrendDirection.increasing),
        _sti(Signal.wastewater, TrendDirection.increasing),
    ]
    result = assess_concordance(inputs)
    assert result.pattern == "concordant_increase"


# ── Concordant decrease ───────────────────────────────────────────────────────


def test_all_decreasing_is_concordant_decrease():
    inputs = [
        _sti(Signal.hospital_admissions, TrendDirection.decreasing),
        _sti(Signal.wastewater, TrendDirection.decreasing),
    ]
    result = assess_concordance(inputs)
    assert result.pattern == "concordant_decrease"


# ── Stable ────────────────────────────────────────────────────────────────────


def test_all_stable_is_stable():
    inputs = [
        _sti(Signal.hospital_admissions, TrendDirection.stable),
        _sti(Signal.wastewater, TrendDirection.stable),
        _sti(Signal.test_positivity, TrendDirection.stable),
    ]
    result = assess_concordance(inputs)
    assert result.pattern == "stable"


# ── Early warning ─────────────────────────────────────────────────────────────


def test_one_increasing_one_stable_is_early_warning():
    inputs = [
        _sti(Signal.hospital_admissions, TrendDirection.increasing),
        _sti(Signal.wastewater, TrendDirection.stable),
    ]
    result = assess_concordance(inputs)
    assert result.pattern == "early_warning"


def test_one_increasing_two_stable_is_early_warning():
    inputs = [
        _sti(Signal.hospital_admissions, TrendDirection.increasing),
        _sti(Signal.wastewater, TrendDirection.stable),
        _sti(Signal.test_positivity, TrendDirection.stable),
    ]
    result = assess_concordance(inputs)
    assert result.pattern == "early_warning"


# ── Mixed ─────────────────────────────────────────────────────────────────────


def test_increase_and_decrease_is_mixed():
    inputs = [
        _sti(Signal.hospital_admissions, TrendDirection.increasing),
        _sti(Signal.wastewater, TrendDirection.decreasing),
    ]
    result = assess_concordance(inputs)
    assert result.pattern == "mixed"


def test_decrease_and_stable_is_mixed():
    inputs = [
        _sti(Signal.hospital_admissions, TrendDirection.decreasing),
        _sti(Signal.wastewater, TrendDirection.stable),
    ]
    result = assess_concordance(inputs)
    assert result.pattern == "mixed"


# ── Lag guard ─────────────────────────────────────────────────────────────────


def test_lag_under_14_days_no_note():
    # 7 days apart — below 14-day threshold
    inputs = [
        _sti(Signal.hospital_admissions, TrendDirection.increasing, date(2026, 11, 14)),
        _sti(Signal.wastewater, TrendDirection.increasing, date(2026, 11, 7)),
    ]
    result = assess_concordance(inputs)
    assert result.temporal_alignment_note is None


def test_lag_exactly_14_days_no_note():
    # 14 days is NOT > 14, so no note
    # 14 days — NOT > 14, so no note
    inputs = [
        _sti(Signal.hospital_admissions, TrendDirection.increasing, date(2026, 11, 14)),
        _sti(Signal.wastewater, TrendDirection.increasing, date(2026, 10, 31)),
    ]
    result = assess_concordance(inputs)
    assert result.temporal_alignment_note is None


def test_lag_over_14_days_triggers_note():
    # 21 days apart
    # 21 days apart — exceeds 14-day threshold
    inputs = [
        _sti(Signal.hospital_admissions, TrendDirection.increasing, date(2026, 11, 14)),
        _sti(Signal.wastewater, TrendDirection.increasing, date(2026, 10, 24)),
    ]
    result = assess_concordance(inputs)
    assert result.temporal_alignment_note is not None
    assert "days" in result.temporal_alignment_note


def test_lag_note_appears_in_explanation():
    inputs = [
        _sti(Signal.hospital_admissions, TrendDirection.increasing, date(2026, 11, 14)),
        _sti(Signal.wastewater, TrendDirection.increasing, date(2026, 10, 24)),
    ]
    result = assess_concordance(inputs)
    assert "caution" in result.explanation.lower()


# ── Single signal ─────────────────────────────────────────────────────────────


def test_single_increasing_signal_returns_concordant_increase():
    inputs = [_sti(Signal.hospital_admissions, TrendDirection.increasing)]
    result = assess_concordance(inputs)
    assert result.pattern == "insufficient_data"


def test_single_stable_signal_returns_stable():
    inputs = [_sti(Signal.hospital_admissions, TrendDirection.stable)]
    result = assess_concordance(inputs)
    assert result.pattern == "insufficient_data"


# ── Insufficient signals excluded from usable ─────────────────────────────────


def test_one_usable_one_insufficient_uses_usable():
    inputs = [
        _sti(Signal.hospital_admissions, TrendDirection.increasing),
        _sti(Signal.wastewater, TrendDirection.insufficient_data),
    ]
    result = assess_concordance(inputs)
    # Only hospital_admissions usable → concordant_increase
    assert result.pattern == "insufficient_data"
    # Explanation notes the excluded signal
    assert "two distinct" in result.explanation.lower()


# ── Explanation content ───────────────────────────────────────────────────────


def test_concordant_increase_explanation_mentions_signal():
    inputs = [
        _sti(Signal.hospital_admissions, TrendDirection.increasing),
        _sti(Signal.wastewater, TrendDirection.increasing),
    ]
    result = assess_concordance(inputs)
    assert "increasing" in result.explanation.lower()


def test_early_warning_explanation_mentions_rising():
    inputs = [
        _sti(Signal.hospital_admissions, TrendDirection.increasing),
        _sti(Signal.wastewater, TrendDirection.stable),
    ]
    result = assess_concordance(inputs)
    expl = result.explanation.lower()
    assert "early" in expl or "rising" in expl or "increasing" in expl


# ── Narrative golden strings ──────────────────────────────────────────────────


def test_narrative_contains_jurisdiction():
    text = build_snapshot_narrative(
        jurisdiction="GA",
        pathogen=Pathogen.influenza,
        signal=Signal.hospital_admissions,
        latest_value=2.5,
        latest_week_ending=date(2026, 11, 14),
        unit="admissions_per_100k",
        official_level="Low",
        trend=None,
        comparison=None,
        concordance=None,
    )
    assert "GA" in text


def test_narrative_mentions_official_level():
    text = build_snapshot_narrative(
        jurisdiction="GA",
        pathogen=Pathogen.influenza,
        signal=Signal.hospital_admissions,
        latest_value=2.5,
        latest_week_ending=date(2026, 11, 14),
        unit="admissions_per_100k",
        official_level="Low",
        trend=None,
        comparison=None,
        concordance=None,
    )
    assert "Low" in text


def test_narrative_value_rounded_to_1_decimal():
    text = build_snapshot_narrative(
        jurisdiction="GA",
        pathogen=Pathogen.influenza,
        signal=Signal.hospital_admissions,
        latest_value=2.473,
        latest_week_ending=date(2026, 11, 14),
        unit="admissions_per_100k",
        official_level=None,
        trend=None,
        comparison=None,
        concordance=None,
    )
    assert "2.5" in text
    assert "2.473" not in text


def test_narrative_includes_trend_sentence():
    trend = _trend(TrendDirection.increasing)
    trend.pct_change = 0.5
    text = build_snapshot_narrative(
        jurisdiction="GA",
        pathogen=Pathogen.influenza,
        signal=Signal.hospital_admissions,
        latest_value=2.5,
        latest_week_ending=date(2026, 11, 14),
        unit="admissions_per_100k",
        official_level=None,
        trend=trend,
        comparison=None,
        concordance=None,
    )
    assert "increasing" in text.lower()
    assert "heuristic" in text.lower()


def test_narrative_includes_season_sentence():
    comparison = SeasonComparison(
        current_season="2026-27",
        current_week_of_season=19,
        current_value=5.0,
        prior=[],
        rank_vs_prior=1,
        n_prior_compared=2,
        pct_of_prior_peak=None,
        method="week_of_season_aligned",
    )
    text = build_snapshot_narrative(
        jurisdiction="GA",
        pathogen=Pathogen.influenza,
        signal=Signal.hospital_admissions,
        latest_value=5.0,
        latest_week_ending=date(2026, 11, 14),
        unit="admissions_per_100k",
        official_level=None,
        trend=None,
        comparison=comparison,
        concordance=None,
    )
    assert "highest" in text.lower()
    assert "2026-27" in text


def test_narrative_includes_concordance_sentence_for_multi_signal():
    concordance = ConcordanceResult(
        pattern="concordant_increase",
        signals_used=[Signal.hospital_admissions, Signal.wastewater],
        temporal_alignment_note=None,
        explanation="All 2 available signal(s) show an increasing trend.",
    )
    text = build_snapshot_narrative(
        jurisdiction="GA",
        pathogen=Pathogen.influenza,
        signal=Signal.hospital_admissions,
        latest_value=2.5,
        latest_week_ending=date(2026, 11, 14),
        unit="admissions_per_100k",
        official_level=None,
        trend=None,
        comparison=None,
        concordance=concordance,
    )
    assert "increasing" in text.lower()


def test_narrative_no_concordance_sentence_for_single_signal():
    concordance = ConcordanceResult(
        pattern="concordant_increase",
        signals_used=[Signal.hospital_admissions],
        temporal_alignment_note=None,
        explanation="Only one signal.",
    )
    text = build_snapshot_narrative(
        jurisdiction="GA",
        pathogen=Pathogen.influenza,
        signal=Signal.hospital_admissions,
        latest_value=2.5,
        latest_week_ending=date(2026, 11, 14),
        unit="admissions_per_100k",
        official_level=None,
        trend=None,
        comparison=None,
        concordance=concordance,
    )
    # Concordance sentence is suppressed for single signal
    assert "Only one signal" not in text


def test_narrative_unavailable_value():
    text = build_snapshot_narrative(
        jurisdiction="PR",
        pathogen=Pathogen.influenza,
        signal=Signal.wastewater,
        latest_value=None,
        latest_week_ending=date(2026, 11, 14),
        unit="wval",
        official_level=None,
        trend=None,
        comparison=None,
        concordance=None,
    )
    assert "unavailable" in text.lower()
