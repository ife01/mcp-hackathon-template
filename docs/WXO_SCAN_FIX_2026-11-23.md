# wxO scan membership and trend attribution

RSA now uses `respiratory_mcp_local_v3`, built from source commit `13d68fa`.
Its model remains `groq/openai/gpt-oss-120b` with the same settings.
The new registration retains the four-tool interface. Earlier toolkit versions remain available as backups.

## Reported failures and investigation

The user's national answer listed 50 jurisdiction codes while claiming 43 rising jurisdictions.
Its trend answer attributed the application's method to a "CDC NHSN server heuristic."
Both statements require correction.

The original conversation's tool trace was not supplied.
A separate pre-fix replay captured the actual calls and complete tool responses for the same six questions.
The national call passed `as_of="2026-10-31"`, `limit=56`, influenza and hospital admissions.
It returned 43 rising rows, 48 assessed jurisdictions, three insufficient-data jurisdictions and zero unavailable jurisdictions.
The replay's answer listed the same 43 members. It did not reproduce the 50-name answer.
Therefore, the original failure is recorded as intermittent answer behavior, with its original payload unverified.

Relative to that replay, the user's list adds AK, CT, HI, KS, MT, ND and WY.
This comparison does not establish what the original conversation's tool returned.

## Changes

The scan response now includes fields derived from its actual returned rows:

- `rising_jurisdictions`: the returned membership, after the requested limit.
- `n_returned`: the number of returned rows.
- `display_text`: a generated membership list with scope, counts, status and attribution.
- `hhs_region`: the requested region, if any.
- `trend_attribution`: an explicit statement that the application calculates the heuristic.

`n_rising_total` remains the total before the result limit.
The new display fields do not change trend thresholds, membership selection, date filtering or source values.
Trend responses also include attribution within `trend`.
CDC supplies the surveillance observations; the application calculates its descriptive trend classification.
Published NHSN `official_level` values retain their separate source attribution.

The active [RSA policy](WXO_AGENT_POLICY.txt) requires membership from the current response and distinguishes totals from displayed rows.
It also prohibits attributing the application heuristic to CDC.
The policy contains no expected scan count or benchmark membership list.

The JSON schema exporter now uses serialization mode for output models.
This includes the new computed response fields in the documented output schema.

## Verification design

The new toolkit package was downloaded and compared file by file with the upload before RSA received its tools.
The agent's instructions and new tool references were read back after the update.
Its model settings, collaborators and knowledge base were preserved.

Live verification includes the six-question shared conversation and three additional independent repetitions of each affected question.
Prompts specify their own dates. There is no session cutoff preamble or supplied answer list.
The evidence retains actual arguments, structured responses, final answers, model identity and instruction text.
Results are evaluated against each call's payload rather than fixed numerical expectations.

The offline evaluator now checks membership separately from reported totals.
Its checks reject added, omitted, duplicate or substituted jurisdiction codes.
It also flags missing application attribution and the misleading CDC-heuristic wording.
Exact reproduction of `display_text` remains a separate, stricter presentation check.
An answer can preserve membership while changing whitespace or formatting.

Contract tests exercise the national frozen scan and a regional result limited to three of eight rising states.
They check that returned membership, displayed count and pre-limit total remain distinct.
A trend contract test verifies explicit application attribution.

The final regression suite passed 386 tests, with two upstream dependency deprecation warnings.
The frozen tool baseline passed 25 cases and all 155 assertions.

## Captured live results

| Check | Finding |
| --- | --- |
| National scan in the shared conversation and three independent repetitions | All four answers match their actual 43 returned rising rows. Calls preserve October 31, influenza, hospital admissions and `limit=56`. |
| National counts | Each payload and answer reports 43 rising, 48 assessed, 51 requested, three insufficient-data and zero unavailable jurisdictions. |
| Georgia trend in three independent repetitions | Each makes an actual `assess_trend` call with the requested geography, signal, pathogen and cutoff. All three attribute the heuristic to the application. |
| Georgia trend in the shared conversation | Correct direction and attribution; reuses the preceding `assess_trend` response instead of making a new call. It does not pass a fresh-call requirement. |
| Region 4 regression | `hhs_region=4` and October 31 reach the scan. All eight returned members match the answer, with eight assessed and rising, zero insufficient and unavailable. |
| Exact display reproduction | Zero of five scan answers preserve the complete `display_text` byte for byte. They change formatting while preserving the returned membership and reported counts. |

The source-generated lists match the returned rows in every captured post-fix scan payload.
The answer membership checks separately verify which jurisdictions RSA actually lists.
No post-fix answer repeats the CDC-heuristic attribution error in these affected questions.
These targeted findings do not establish flawless agent compliance or an overall accuracy rate.

The [evidence bundle](../eval/transcripts/wxo/2026-11-23-scan-fix/evidence.json) includes all 18 records across pre-fix, post-fix and repeated checks.
It also retains the registered tool schemas, policy versions and package source hashes.
The [summary](../eval/transcripts/wxo/2026-11-23-scan-fix/summary.json) separates membership, attribution and strict presentation findings.
The [user-reported failures](../eval/transcripts/wxo/2026-11-23-scan-fix/user-reported-failures.json) remain separate from captured API traces.
The [manifest](../eval/transcripts/wxo/2026-11-23-scan-fix/manifest.json) records exact evidence hashes.
Credentials, private service URLs and tenant metadata are excluded.

To inspect the national answer checks from the repository root:

```shell
python -m eval.wxo_review eval/transcripts/wxo/2026-11-23-scan-fix/evidence.json --phase scan-after --index 3 --cutoff 2026-10-31
```

The command exits with a failure because exact display reproduction fails.
Its membership, payload consistency, cutoff and application-attribution checks pass.
Do not suppress the strict failure or report all checks as passing.
New checks apply to this follow-up; previously stored scores retain their original check definitions.

## Subsequent successful manual retest

The user supplied another six-question RSA conversation with UI times from 11:29 AM to 11:32 AM.
All six visible answers meet the targeted correctness criteria, including the 43-member national list and application attribution.
The unsupported-date answer preserves the complete corrected message.
See the [manual review](../eval/transcripts/wxo/2026-11-23-manual-success/REVIEW.md) and its separate transcribed evidence.
No raw tool details accompany that UI session. The API traces above remain a separate verification.
This does not resolve the historical peak-denominator defect or change Phoenix scores.

## Scope and remaining limits

These are development and targeted regression checks, not independent holdout accuracy estimates.
Live source data can change. Observation cutoffs do not reconstruct historical publication vintages.
The Phoenix results remain separate and were not rerun for this change.
Earlier historical-peak explanation and shortened-error findings remain in the prior verification record.
This change does not establish that every other agent behavior is correct.
