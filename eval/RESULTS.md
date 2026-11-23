# Evaluation results — evidence audit 2026-11-22

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

## wxO manual walkthroughs (reported by Bob)

Bob reports a first five-question walkthrough and a second shared-session
walkthrough covering 16 case IDs. The second is summarized in
[the retained transcript](transcripts/wxo/run2_2026-11-23.md). Its original
2026-11-23 date label is retained as reported. These are human-written session
summaries, not exported provider traces or independent Phoenix experiments.

The first walkthrough reportedly omitted `as_of`, producing later observation
weeks for several benchmark questions. Explicit cutoff instructions addressed
that date mismatch in the second walkthrough. A cutoff still queries live CDC
records: it does not establish use of snapshot_v2 or exclude later revisions.

| Evidence | What it supports | Limits |
| --- | --- | --- |
| Run 1: five reported questions | Initial integration and a date-preservation issue; forecast refusal reported | No raw trace, exact model/version or independently reproducible grading |
| Run 2: 16 case IDs discussed | Reported valid tool selection, scoped positivity, historical abstention and matching headline values in several answers | Shared history; B1 reused A1 and B5 reused a proactive snapshot; original pass labels contain a material geography error |
| Reported public health checklist | Useful review topics | Overlapping observations and an N/A forecast item do not establish 12 independent passing tests |

### Material correction to the original run-2 score

The D5 summary labels Arkansas as missing from an HHS Region 4 scan and grades
that answer PASS. Arkansas belongs to Region 6, according to the
[HHS regional directory](https://www.hhs.gov/about/agencies/iea/regional-offices/index.html).
The committed frozen D5 tool response has 8 requested, 8 assessed and 0 unavailable
jurisdictions, with an empty unavailable list. Its limit of 5 affects display,
not missingness. The manual run reportedly displayed all 8.

The described D5 answer therefore fails the geographic-scope/missingness check,
even though its rising total and lead state match the reference. The original
16/16 and 100% invariant claims are withdrawn. We do not substitute 15/16 because
the other answers have not been independently regraded from complete evidence.
For example, the C5 summary says 31% where the reference is 31.86%; acceptable
rounding and the full explanation need review.

Not every case was an independent prompt, and not every raw tool payload/final
answer is retained. The original transcript remains available with an audit note;
its PASS annotations are historical reviewer judgments, not current validated
scores. Tool-baseline coverage does not establish agent coverage for unasked cases.

## Phoenix agent evaluation

The 15-question frozen benchmark, stdio agent, three semantic judges, deterministic
checks and trace/experiment storage are implemented. Credential-free integration
verification used scripted responses and mocked HTTP. **No real-model Phoenix
experiment has been run.** The user currently has wxO service access but no model
API gateway; the current agent and judges require separate model access.

An honest next step using existing access is a fresh-conversation manual wxO
assessment with retained evidence and the rubric in
[WXO_AGENT_SETUP.md](../docs/WXO_AGENT_SETUP.md#evaluation-without-a-model-api).
Such a review is useful but is not a Phoenix LLM-as-judge result.

## Limits

The tool cases validate implemented descriptive rules, not epidemiologic validity,
predictive ability or operational effectiveness. NHSN returned only 29 weeks
through this capture's cutoff; that is insufficient evidence for some historical
comparisons, not proof of the source's earliest available history. Wastewater
population coverage is unknown and changing site participation can affect medians.
Human public health review remains necessary. No analyst time-saving study has
been performed. See [the post-Bob audit](../docs/POST_BOB_REVIEW.md).
