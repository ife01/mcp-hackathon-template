# Evaluation results — updated 2026-11-23

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

## Manual wxO evaluations

The user's two earlier manual evaluations are part of the evidence package.
They test the actual wxO conversation workflow and show useful error discovery.
The original files remain unchanged:

- [First evaluation](<transcripts/wxo/originals/1st Evals.txt>)
- [Second evaluation](<transcripts/wxo/originals/2nd Evals.txt>)
- [Case review, failures and fix status](transcripts/wxo/MANUAL_REVIEW_2026-11-23.md)
- [Original file hashes](transcripts/wxo/originals/manifest.json)

| Evaluation | Design | Supported findings | Limits |
| --- | --- | --- | --- |
| First wxO run | Five questions in one conversation | Four dated answers visibly use later observations; forecast refusal demonstrated | No complete tool-argument export; no validated aggregate pass rate |
| Second wxO run | 14 task prompts after a date-setting preamble | Improved date handling and matching headline values; appropriate refusal of state positivity ranking | Region 4 missingness error, unsupported source-inception claim and abbreviated answers; no validated aggregate pass rate |
| Phoenix run | 15 fresh case sessions over frozen replay | 15/15 correctness, scope and public health after documented grading corrections | Separate agent; one repetition; same-model judging |

### What failed and what improved

The first user's questions already specified October 31, 2026.
Several responses instead used November 14.
The agent failed to preserve the requested cutoff; the user did not omit the date.
Claims that October 31 observations were absent conflict with the retained series and second-run values.
The second session added an explicit `as_of` instruction and shows improved date handling.
It does not prove every abbreviated call preserved the argument.
A live date-filtered query also remains distinct from frozen replay.

The second scan lists Arkansas as missing from HHS Region 4.
Arkansas belongs to Region 6, and the current frozen Region 4 response has no unavailable states.
The abbreviated record cannot attribute the error to the deployed tool, model or transcript generation.
The visible answer fails geographic-scope correctness.

The 2015 answer treats the application's 2020 lower date bound as proof of CDC dataset inception.
The server error at review time included a broad statement about NHSN beginning in 2020.
The shared message now identifies the application limit without asserting source inception.
Local regression checks cover all four tools.
The [targeted retest guide](../docs/WXO_TARGETED_RETEST.md) describes the required toolkit update and six wxO questions.
The corrected toolkit is now active as `respiratory_mcp_local_v2` on RSA.
The [runtime verification](../docs/WXO_RUNTIME_VERIFICATION_2026-11-23.md) records the original-session replay, fresh tests and two policy revisions.
All six final questions preserve cutoff arguments; the regional call preserves Region 4 scope.
Strict verbatim error preservation remains incomplete. A supplemental historical answer mislabels the peak denominator despite a correct tool payload.
These unresolved answer defects remain documented. The new runs do not change the Phoenix scores.

### How the records are counted

The second file contains 14 task prompts, a session preamble and a transcript-generation request.
Bob's 16-case mapping includes overlapping answers; it is not 16 independent trials.
A shared conversation is a valid evaluation design, but it measures contextual behavior.
The earlier 2/5 and 16/16 overall scores are not retained as validated accuracy rates.
Visible matches, observed failures and unassessable content are listed separately in the review.

The files are generated conversation records with ellipses and abbreviated payloads.
They are useful manual integration evidence without being complete provider trace exports.
Their embedded instructions and self-reported metadata are retained as source content only.
The older [Bob summary](transcripts/wxo/run2_2026-11-23.md) remains a secondary historical artifact.
The supplied original records take precedence where they differ.

## Phoenix agent evaluation — 2026-11-23

One real-model run completed the 15 frozen cases with prompt v2.
Correctness, scope and public health judges each scored 15/15 pass.
All applicable deterministic checks pass. No execution errors or missing scores remain.
The agent and judge used the same configured gpt-5.4-mini deployment.

The initial run had 17 rate-limited judge calls and three false numeric-check failures.
Request spacing and bounded retry recovered the missing scores without new agent calls.
Regression-tested grader corrections addressed rounding, outage dates and pathogen-name digits.
The original results and the revision remain in the public evidence.

Read [the full result](phoenix/RESULTS_2026-11-23.md) before citing these scores.
It links all 15 answers, actual tool results, judge explanations and source identities.
This is one repetition with same-model judging and no no-tool comparison.
It does not establish independent holdout accuracy or operational validity.
The supplied manual wxO evaluations test that platform separately.
Phoenix scores do not apply to wxO or retroactively repair its recorded answers.

## Limits

The tool cases validate implemented descriptive rules, not epidemiologic validity,
predictive ability or operational effectiveness. NHSN returned only 29 weeks
through this capture's cutoff; that is insufficient evidence for some historical
comparisons, not proof of the source's earliest available history. Wastewater
population coverage is unknown and changing site participation can affect medians.
Human public health review remains necessary. No analyst time-saving study has
been performed. See [the post-Bob audit](../docs/POST_BOB_REVIEW.md).
