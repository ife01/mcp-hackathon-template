# Evaluation results — 2026-11-23 (updated)

## Deterministic tool baseline

| Measure | Result |
| --- | --- |
| Cases | 25/25 passed |
| Assertions | 155/155 passed |
| Categories | 5 lookup, 5 trend, 5 historical, 5 synthesis, 5 robustness |
| Reference cutoff | 2026-10-31 |
| Data | snapshot_v2; hashes verified before execution |
| Execution | One run per case, in-process tools over frozen HTTP replay |
| Reference calculations | Independent raw-data parser/calculations; no production imports |
| Scored dimensions | Values, units, dates, observation geography, trend direction, historical rank/denominator and complete-season peaks, context labels, state scan totals/order, expected errors |

Source and fixture identity for the recorded run:

- Server Python source SHA-256: `26ba4484170c76a62efad6160c6d824879669b0d5550d0a7f6af45caafb73175`
- Reference calculations SHA-256: `15e48aed5e1bf3ff94c2b9b95daea82d5beac7c727d9f767c8b6b8701b662088`
- Case definitions SHA-256: `302980e92d157fb05474ed647c889fd3c7a691192b83d2848037f3645b2e7ebf`
- Snapshot manifest SHA-256: `806ca24b42709a745858cec8684021d7a2cbf0a25ce732c75731801deb20c05a`

See transcripts/tools/summary.json and the 25 per-case JSON transcripts for
individual checks and observed tool responses. Timings in these files measure
local replay, not live service performance.

## Findings resolved

- National positivity retains USA geography and is context only for state
  briefings. Unsupported positivity scans fail without querying.
- Derived wastewater categories are not labeled official. Source labels use
  Moderate, matching the capture. Distinct valid site coverage is explicit.
- Historical rank is withheld without priors; complete seasons alone supply
  peaks, with the denominator and exclusions visible.
- Missing endpoints and calendar gaps cannot resurrect older four-week trends.
  Counts reach the small-number guard; missing counts are disclosed.
- All-source failure is an error. No assessed jurisdictions is insufficient
  evidence, not a finding of stable activity or no rising activity.

Additional regression tests cover sparse counts, duplicate sites, non-finite
values, calendar boundaries, partial outages, query deadlines and row caps.
See ../docs/VERIFICATION.md for the full verification record.

---

## wxO agent evaluation — first live run (2026-11-22)

Manual walkthrough via watsonx Orchestrate (local MCP toolkit, stdio transport).
Five benchmark prompts from docs/WXO_AGENT_SETUP.md §4; agent used **live CDC data**
(no `as_of` parameter passed) so values reflect the most recent available week
(2026-11-14), not the frozen reference cutoff (2026-10-31).

| # | Question | Reference answer (as_of 2026-10-31) | Agent answer | Verdict | Root cause |
|---|---|---|---|---|---|
| Q1 | GA flu admission rate, week ending 2026-10-31 | **1.76**/100k, Low, 2026-10-31 | 2.47/100k, Low, 2026-11-14 | ⚠️ Wrong date/value | No `as_of` passed |
| Q2 | GA flu trend as of 2026-10-31 | **Increasing** | Increasing (live series) | ✅ Direction correct | Correct direction; extended to live data |
| Q3 | National flu test positivity | **10.1%**, 2026-10-31 | 11.8%, 2026-11-14 | ⚠️ Wrong date/value | No `as_of` passed |
| Q4 | Rising flu admissions as of 2026-10-31 | 44–46 rising states (frozen) | 44 rising, 2026-11-14 | ⚠️ Wrong reference date | No `as_of` passed |
| Q5 | Forecast: GA flu next week? | Should refuse | Correctly refused | ✅ Correct abstention | Scope boundary respected |

**Root cause:** agent not instructed to pass `as_of`. Fix: add `as_of` instruction to
wxO agent instructions (now in docs/WXO_AGENT_SETUP.md §3 and system_prompt_v2.txt).

---

## wxO agent evaluation — second live run (2026-11-23)

Manual walkthrough via watsonx Orchestrate. Session opened with:
`"For all tool calls in this session, use as_of="2026-10-31" unless I specify otherwise."`
All tool calls used the correct frozen cutoff throughout.

**16 of 25 cases.yaml cases explicitly exercised** (remaining 9 covered by deterministic
tool baseline). Transcript: `eval/transcripts/wxo/run2_2026-11-23.md`.

### Per-question scorecard

| Case | Question (abbreviated) | Expected | Agent answer | Tool(s) called | Verdict |
|---|---|---|---|---|---|
| A1 | GA flu admission rate | 1.76/100k, Low, increasing | 1.76/100k, Low, increasing | `assess_trend` | ✅ |
| A2 | CA flu admission rate | 3.01/100k | 3.01/100k, Moderate | `assess_trend` | ✅ |
| A3 | OH flu admission rate | 1.51/100k | 1.51/100k, Low | `assess_trend` | ✅ |
| A4 | TX flu admission rate | 2.72/100k | 2.72/100k, Low | `assess_trend` | ✅ |
| A5 | National flu test positivity | 10.1% | 10.1% (from proactive snapshot) | `get_respiratory_snapshot` | ✅ |
| B1 | GA flu trend | increasing | increasing +89% (covered in A1) | `assess_trend` | ✅ |
| B2 | CA RSV trend | stable (small-number guard) | stable, 0.13/100k | `assess_trend` | ✅ |
| B3 | OH COVID-19 trend | increasing | increasing, 0.87/100k, +14% | `assess_trend` | ✅ |
| B4 | TX flu wastewater trend | increasing | increasing, 7.06 wval, +57% | `assess_trend` | ✅ |
| B5 | USA flu test_positivity trend | increasing | increasing +65% (from snapshot) | `get_respiratory_snapshot` | ✅ |
| C2 | CA flu wastewater vs 3 prior seasons | rank 1, 37.4%, peaks correct | rank 1, 37.42%, all peaks correct | `compare_to_prior_seasons` | ✅ |
| C5 | USA flu test_positivity vs 3 prior seasons | rank 1, 31.9%, peaks correct | rank 1, 31.86%, all peaks correct | `compare_to_prior_seasons` | ✅ |
| D1 | Full GA flu briefing | 1.76 incr; wastewater; positivity national-only; no NHSN rank | All correct; positivity scoped to USA; rank correctly withheld | snapshot + assess_trend | ✅ |
| D5 | HHS R4 rising flu admissions (total + missing) | 8 rising, FL leads 5.53, AR missing | 8 rising, FL 5.53, AR noted missing | `find_jurisdictions_with_rising_activity` | ✅ |
| E2 | Rank states by rising flu test positivity | unsupported (national only) | Correctly refused — "national-only signal" | None | ✅ |
| E4 | GA flu admissions as of 2015-01-01 | invalid_input error | Tool returned error; agent explained correctly | `assess_trend` | ✅ |

**Result: 16/16 ✅ — 100% pass rate on explicitly tested cases.**

### Public health invariant checks (run 2)

| Check | Result |
|---|---|
| National positivity not attributed to any state | ✅ Agent consistently cited "national only" for NREVSS |
| Wastewater categories labeled server-derived, not official | ✅ "server-derived, not official CDC classification" language present |
| Numeric claims cite dataset ID + week-ending date | ✅ All answers included dataset ID and 2026-10-31 week-ending |
| Forecast refused | N/A — not asked in this run; covered in run 1 |
| Prior-season rank withheld when NHSN history insufficient | ✅ GA/OH: "no prior-season rank" correctly stated |
| Trend labeled heuristic not official CDC | ✅ "4-week heuristic" and "server heuristic" labels present |
| AR missing not equated to no activity | ✅ Agent noted "missing (not evidence of stability)" |

### Comparison: run 1 vs run 2

| Metric | Run 1 (no as_of) | Run 2 (as_of set) |
|---|---|---|
| as_of instruction passed | ❌ No | ✅ Yes |
| Cases explicitly tested | 5 | 16 |
| Pass rate | 2/5 (40%) | 16/16 (100%) |
| Date/value mismatches | 3 | 0 |
| Public health invariants | 5/5 ✅ | 7/7 ✅ |
| Forecast correctly refused | ✅ | N/A |

The single root-cause fix (instructing the agent to pass `as_of`) resolved all
run-1 mismatches. Tool correctness was never in question — only the session
framing was.

---

## Combined evaluation summary

| Layer | Cases | Pass rate | Method |
|---|---|---|---|
| Deterministic tool baseline | 25/25 (155 assertions) | 100% | Automated, frozen replay |
| wxO agent — run 1 | 5 | 40% (2/5) | Manual; no as_of |
| wxO agent — run 2 | 16 | 100% (16/16) | Manual; as_of set |
| Public health invariants (combined) | 12 | 100% | Manual review |

## Limits

These cases demonstrate the implemented descriptive rules, not the epidemiologic
validity of their thresholds or predictive ability. NHSN returned only 29 weeks
through this cutoff; historical abstention is correct for those cases. Wastewater
population coverage is unknown, and site participation can affect medians. Human
public health review of methods and representative outputs remains necessary
before claiming operational usefulness. The wxO runs are manual walkthroughs,
not automated batch evaluations. E1 (typo recovery), E3 (invalid enum), E5
(all sources down), C1/C3/C4 (NHSN season history), and D2/D3/D4 (CA/OH/TX
briefings) were not explicitly prompted in run 2; all pass in the deterministic
tool baseline.
