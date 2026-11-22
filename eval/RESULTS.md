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

## Remaining agent evaluation

| Agent measure | Status |
| --- | --- |
| Tool selection | Not run |
| Argument accuracy | Not run |
| Final-answer numerical correctness and grounding | Not run |
| Citation/geography/unit/date fidelity | Not run |
| Caveat preservation and appropriate abstention | Not run |
| Live cold/warm median and p95 latency | Not run |
| Repeatability across three agent runs | Not run |

The Phoenix agent harness is now implemented; see phoenix/README.md. Its next
step requires a compatible model API base, API key, and separate agent/judge model
IDs. A wxO URL, agent ID and wxO key are needed only for a separate wxO-platform
evaluation. Use the
natural-language prompts as agent inputs, keeping expected calls hidden. To score
against these references, the service must use the same frozen dataset; a live
CDC-data run is a separate evaluation.

## Limits

These cases demonstrate the implemented descriptive rules, not the epidemiologic
validity of their thresholds or predictive ability. NHSN returned only 29 weeks
through this cutoff; historical abstention is correct for those cases. Wastewater
population coverage is unknown, and site participation can affect medians. Human
public health review of methods and representative outputs remains necessary
before claiming operational usefulness. No live wxO evaluation or Docker run is
represented by these results.
