# Evaluation results — 2026-11-22

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
local replay, not live service performance. No comparable pre-fix 25-case run was
captured; do not present a numerical before/after agent improvement claim.

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

## wxO agent evaluation — first live run (2026-11-22)

Manual walkthrough via watsonx Orchestrate (local MCP toolkit, stdio transport).
Five benchmark prompts from docs/WXO_AGENT_SETUP.md §4; agent used **live CDC data**
(no `as_of` parameter passed) so values reflect the most recent available week
(2026-11-14), not the frozen reference cutoff (2026-10-31).

### Per-question assessment

| # | Question | Tool called | Reference answer (as_of 2026-10-31) | Agent answer | Verdict | Root cause |
|---|---|---|---|---|---|---|
| Q1 | GA flu admission rate, week ending 2026-10-31 | `get_respiratory_snapshot(GA, influenza)` | **1.76**/100k, CDC level **Low**, week ending **2026-10-31** | 2.47/100k, CDC level Low, week ending **2026-11-14** | ⚠️ Wrong date/value | Agent used live data; no `as_of` passed |
| Q2 | GA flu trend as of 2026-10-31 | `assess_trend(GA, influenza, hospital_admissions)` | **Increasing** (0.94→1.76 over last 4w) | Increasing, series 2026-10-03 to 2026-11-14 | ✅ Direction correct | Correct direction; series extended to live data |
| Q3 | National flu test positivity, week ending 2026-10-31 | `get_respiratory_snapshot(USA, influenza)` | **10.1%**, week ending **2026-10-31** (NREVSS national only) | 11.8%, week ending **2026-11-14** | ⚠️ Wrong date/value | Same: no `as_of`; live data used |
| Q4 | Which US states had rising flu admissions as of 2026-10-31? | `find_jurisdictions_with_rising_activity(influenza, hospital_admissions)` | 44–46 rising states from frozen scan (as_of 2026-10-31) | 44 rising states, week ending 2026-11-14 | ⚠️ Wrong reference date | Same: no `as_of`; live data used |
| Q5 | Forecast: what will GA flu activity be next week? | *(no tool called)* | Should refuse — no forecasting | Correctly refused; summarised observed trend only | ✅ Correct abstention | Scope boundary respected |

### Public health invariant checks

| Check | Result |
|---|---|
| National positivity not attributed to Georgia | ✅ Agent cited "national level only" |
| NWSS aggregate not labeled official CDC state classification | N/A — wastewater not tested in this run |
| Numeric claims cite dataset ID + week-ending date | ✅ All answers included dataset ID and week-ending date |
| Forecast refused | ✅ Agent declined Q5, cited data limitation |
| Caveats preserved | ✅ Hospital coverage (65-71%) and heuristic disclaimer included |
| Trend labeled heuristic not official CDC | ✅ "server-derived heuristic" language present |

### Root cause: missing `as_of` parameter

The agent was not instructed to pass `as_of="2026-10-31"` and therefore all four
tool calls used live CDC data. The frozen reference expects `as_of=2026-10-31`.
This is a **system-prompt gap**, not a tool correctness failure:

- Q1: 2.47 (2026-11-14 live) vs. **1.76** (2026-10-31 frozen) — difference is real, later data
- Q3: 11.8% (2026-11-14 live) vs. **10.1%** (2026-10-31 frozen) — same cause
- Q4: 44 rising states at 2026-11-14 vs. reference at 2026-10-31 — different weeks, counts may differ

The tool outputs are **internally consistent and correctly grounded** to the week they cite.
The discrepancy is temporal: the agent answered the question as of today's data, the
reference expected frozen-snapshot data.

### Fix: add `as_of` instruction to system prompt v2

The existing `system_prompt_v2.txt` already contains:

> *"Use as_of="2026-10-31" for all tool calls unless the user explicitly specifies a different date."*

This instruction was not reflected in the wxO agent instructions used for this run
(docs/WXO_AGENT_SETUP.md §3). The wxO instructions must be updated to include the
`as_of` rule explicitly when running against the frozen benchmark.

**For production use (live data), the agent behavior is correct** — it should
answer with the most recent available data. The `as_of` instruction only applies
during deterministic evaluation.

## Limits

These cases demonstrate the implemented descriptive rules, not the epidemiologic
validity of their thresholds or predictive ability. NHSN returned only 29 weeks
through this cutoff; historical abstention is correct for those cases. Wastewater
population coverage is unknown, and site participation can affect medians. Human
public health review of methods and representative outputs remains necessary
before claiming operational usefulness. No live wxO evaluation or Docker run is
represented by these results.
