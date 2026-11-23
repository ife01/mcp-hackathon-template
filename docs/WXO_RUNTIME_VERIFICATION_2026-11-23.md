# wxO runtime verification — November 23, 2026

This earlier verification used `respiratory_mcp_local_v2`, with server source from commit `8f5fabb`.
RSA now uses v3; see [the later scan-fix verification](WXO_SCAN_FIX_2026-11-23.md).
The policies used for these records are retained in their evidence bundle.
The current instructions are in [WXO_AGENT_POLICY.txt](WXO_AGENT_POLICY.txt).
The model remains `groq/openai/gpt-oss-120b`. Its settings and four tool bindings are unchanged by the instruction updates.

## What the regression investigation found

The original eval2 session began with an explicit October 31 cutoff instruction.
The initial six-question retest omitted that preamble and used different question wording.
Those tests measured different conversation conditions.

Replaying all 14 original task prompts after the original preamble recovered the dated Georgia rate.
The actual tool call passed `as_of="2026-10-31"` and returned 1.76 admissions per 100,000.
The Region 4 scan passed `hhs_region=4` and returned eight assessed states without unavailable jurisdictions.
This supports the user's report that eval2 handled those dates correctly.
It does not establish that every original answer was correct.

The fresh-conversation baseline reproduced a real failure: RSA sent `as_of: null` for a dated Georgia question.
Other answers incorrectly converted fractional changes, described trend windows, or explained source availability.
The captured tool payloads let us distinguish these answer errors from tool calculations.

The deployment comparison found one substantive Python change: the application-limit error message.
Dependency requirements changed from open ranges to pinned versions, and tool references changed to the versioned registration.
The investigation found no changed date-filter or region-calculation code.
It does not prove identical behavior across all dependency versions or possible inputs.

## Fixes and recorded attempts

RSA's updated policy requires explicit dates and regions in tool calls.
It explains native units, fractional changes and the two-week comparison method.
It limits unsupported source-history claims and requests verbatim tool errors.
The policy contains no benchmark answer values or fixed observation cutoff.

The first policy attempt still produced an unsupported records-availability explanation.
That failed answer remains in the evidence as phase `post`, record 5.
The second policy adds a concise response contract and stronger error handling.
Its final checks remain separate from the first attempt.

| Phase | Conversation design | Completed records |
| --- | --- | --- |
| `replay` | Original preamble and 14 original tasks in one conversation | 15 |
| `fresh` | Six independent questions before instruction changes | 6 |
| `post` | Six independent questions after the first policy | 6 |
| `post-replay` | Original preamble and tasks after the first policy | 15 |
| `extra` | National-only refusal, historical comparison and undated latest-data checks after the first policy | 3 |
| `post2` | Six independent questions after the final policy | 6 |
| `errors2` | Three additional independent unsupported-date checks after the final policy | 3 |
| `extra2` | Repeat of scope, history and undated checks after the final policy | 3 |

These 57 records are development and verification evidence, not 54 independent benchmark cases.
The transcript-export request from eval2 was excluded. Original task text and sequence were retained.

## Final six-question findings

| Question | Actual tool behavior and answer review |
| --- | --- |
| Georgia dated rate | `assess_trend` receives October 31. Payload value is 1.76 per 100,000; answer rounds it to 1.8. |
| Georgia direction | October 31 cutoff; increasing direction and correct two-week mean comparison. |
| National positivity | October 31 cutoff; USA observations, 10.1% positivity, national context and revision caveat. |
| National scan | October 31 cutoff; 43 rising among 48 assessed, three insufficient, with states and DC identified. |
| Region 4 scan | October 31 cutoff and `hhs_region=4`; all eight regional states, eight rising, zero unavailable or insufficient. |
| Unsupported date | `as_of="2015-01-01"` reaches the tool. It returns the corrected application-limit error. Answer identifies an application limit but shortens the message. |

All six final records preserve the requested cutoff in actual calls.
All observations in the five data-returning records stay within that cutoff.
The Region 4 payload stays within its eight-state scope.
These findings use captured payloads, not a hard-coded match to earlier numerical answers.

Strict verbatim error compliance remains incomplete: two of four final date-error answers reproduce the complete message.
The other two identify the application limit but omit part of the explanation.
The final six-question phase passes five of six complete automated check sets because of that stricter fidelity check.
The three extra error checks pass two of three complete automated check sets.
Assistant review found no repeated claim of CDC dataset inception in these four final error answers.
This is not an independent public health review or a claim of perfect agent reliability.

A supplemental final historical answer still fails peak-denominator interpretation (`extra2`, record 1).
It correctly reports the requested current and prior-week values and missingness.
However, it adds a peak statistic and identifies 31.6% in 2024–25 as the highest peak.
The actual payload identifies a higher peak: 31.7% in 2025–26.
The tool calculation uses the correct denominator; RSA's added explanation is wrong.
This remains an unresolved agent-answer defect and needs review before using historical peak claims.
The final state-positivity refusal and undated latest-data answer behave appropriately.
Do not count all supplemental final answers as passes.

Other presentation limits remain: some answers add unsolicited context or round a returned value.
One answer uses imprecise wording about observations being available on the cutoff date, despite also excluding historical publication reconstruction.
The actual arguments and observation dates are the stronger evidence for date fidelity.
Do not report this run as flawless compliance or a new Phoenix score.

## Evidence and repeatable checks

The [evidence bundle](../eval/transcripts/wxo/2026-11-23-runtime-retest/evidence.json) contains prompts, timestamps, policies, calls, full tool results and answers.
It excludes service credentials, private service URLs and tenant metadata.
The [manifest](../eval/transcripts/wxo/2026-11-23-runtime-retest/manifest.json) records exact file hashes and phase counts.
The user's [pasted retest](../eval/transcripts/wxo/2026-11-23-runtime-retest/user-retest.txt) is preserved separately.

Use the offline checker from the repository root:

```shell
python -m eval.wxo_review eval/transcripts/wxo/2026-11-23-runtime-retest/evidence.json --phase post2 --index 4 --cutoff 2026-10-31 --region 4
```

The checker joins duplicate trace views, requires tool responses and checks dates and regional scope.
It also flags incomplete verbatim error preservation.
It does not judge every numerical statement or replace semantic answer review.
Nine regression tests cover missing evidence, duplicate calls, cutoffs, scope and error fidelity.

The frozen tool baseline was rerun: 25 of 25 cases and 155 of 155 assertions passed.
The final suite passed all 381 tests, including the nine new checker tests.
Two upstream dependency deprecation warnings remain. Lint and formatting checks passed.
See the [current tool summary](../eval/transcripts/wxo/2026-11-23-runtime-retest/tool-baseline-summary.json) for source hashes and assertion counts.
The Phoenix run remains separate, unchanged evidence over frozen replay.

For another live wxO test, refresh the page, select RSA and start a new conversation for each question.
Use the original preamble only when repeating the original contextual eval2 design.
Capture tool details and final answers, and report both designs separately.
Live-source results can change with revisions; a date cutoff does not select frozen replay.
