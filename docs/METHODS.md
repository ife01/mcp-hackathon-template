# Methods: Respiratory Season Situational Awareness MCP Server

## Disclaimer

**All analytics in this server are heuristics developed for situational-awareness purposes only. They are NOT official CDC classifications, NOT endorsed by CDC, and must NOT be cited as official surveillance determinations.** Official CDC activity levels (from NHSN) are carried in the `official_level` field of every `WeeklyObservation`; use those for authoritative characterizations.

---

## 1. Trend Classification (`analytics/trend.py`)

### Method

Trend direction is classified by comparing the mean of the **latest 2 weeks** against the mean of the **prior 2 weeks** (the "2w vs prior 2w" window). The direction is signal-specific:

| Signal | Threshold for change |
|--------|----------------------|
| `hospital_admissions` | ≥10% relative **and** ≥0.1 per 100k absolute (dual guard) |
| `test_positivity` | ≥1.0 percentage-point absolute |
| `wastewater` | ≥15% relative |

If neither threshold is met, the classification is `stable`.

### Pre-processing

- Trailing `None` values are stripped before windowing.
- Fewer than 4 non-null observations → `insufficient_data`.
- If any value within the 4-week window is `None` → `insufficient_data`.

### Small-number guard (hospital admissions only)

When raw admission counts are provided alongside rates, and both window means are **below 10 admissions**, the result is downgraded to `insufficient_data`. This prevents spurious large-percentage swings when counts are very small (e.g., rare pediatric RSV in low-population states).

### Zero denominator

If the prior window mean is 0, `pct_change` is set to `None` and the classification falls back to `stable` for signals requiring a relative threshold (wastewater). For hospital admissions the absolute change still applies; for test positivity the absolute threshold is used directly.

### Output

```python
TrendResult(
    direction: TrendDirection,          # increasing | stable | decreasing | insufficient_data
    pct_change: float | None,           # (recent_mean - prior_mean) / prior_mean
    abs_change: float | None,           # recent_mean - prior_mean
    window_weeks: int,                  # non-null observations used
    method: "2w_vs_prior_2w",
    basis: "server_heuristic",
)
```

---

## 2. Season Comparison (`analytics/seasons.py`)

*Documented in Build 2.2.*

---

## 3. Cross-Signal Concordance (`analytics/concordance.py`)

*Documented in Build 2.3.*

---

## 4. Lag Guard

Applies when combining signals from different datasets (NHSN, NWSS, NREVSS). If the spread between the most recent and least recent `latest_week_ending` across usable signals exceeds **14 days**, a `temporal_alignment_note` is attached and concordance claims are explicitly qualified. See `analytics/concordance.py`.

---

## 5. Data sources and caveats

| Signal | Dataset | Geography | Lag | Key caveat |
|--------|---------|-----------|-----|------------|
| Hospital admissions | NHSN `vdzy-6i9v` | State, national | ~1 week | Per-100k rates; mandatory reporting since 2024 |
| Wastewater | NWSS `atcp-73re` | Site-level aggregated to state | ~1–2 weeks | Influenza A only; median of sites; <2 sites → value=None |
| Test positivity | NREVSS `seuz-s2cv` | National only | ~1–2 weeks | No state/region breakdown; A+B combined for influenza |

---

*Last updated: Build 2.1*
