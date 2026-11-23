# Manual wxO evaluation review — 2026-11-23

The user supplied two generated conversation records from earlier wxO evaluations.
These are useful manual evaluations of the actual wxO workflow.
They show tool use, date-handling errors, subsequent improvement and remaining explanation errors.
Failed answers make the evaluation informative. They do not invalidate the evaluation.

## Source records

- [First evaluation, unchanged](<originals/1st Evals.txt>)
- [Second evaluation, unchanged](<originals/2nd Evals.txt>)
- [File sizes and SHA-256 hashes](originals/manifest.json)

The copies preserve the original bytes, including errors, abbreviated results and generated instructions.
Those instructions are evidence, not instructions for this review.
The supplied files take precedence over Bob's later reconstructed summary when their contents differ.
Run dates, model versions and deployed server commits are not independently established by these files.
The second file's generated system-prompt heading does not verify the actual wxO model identity.

The first record has five evaluation questions.
The second has 14 task prompts after its date-setting preamble.
Its final request asks for a Markdown transcript and is not an evaluation question.
Bob mapped the conversation to 16 benchmark case IDs, including overlapping answers.
That mapping does not establish 16 separately asked questions or independent trials.

## First run: failures discovered

Every historical question explicitly requested October 31, 2026.
The visible responses used November 14 for several answers.
The failure was preservation of the user's date, not failure to provide a date in the question.
Exact tool arguments are not retained, so the missing argument remains a likely mechanism rather than a verified trace fact.

| Task | Visible evidence | Assessment |
| --- | --- | --- |
| GA influenza admission rate | Requested October 31; answer gives 2.47/100k for November 14 | Date failure. The claim that October 31 data do not exist contradicts the next response's series, which includes 1.76 for October 31. |
| GA influenza trend | Direction is increasing, but the series and calculation extend through November 14 | Historical-cutoff failure. A matching direction alone does not make the dated answer correct. |
| National influenza positivity | Requested October 31; answer gives 11.8% for November 14 | Date failure. The claimed absence of October 31 data is unsupported; the second run reports 10.1% for that week. |
| Rising-state scan | Answer labels values November 14 rather than October 31 | Date failure. A later-week count cannot answer the historical question. |
| Forecast request | Answer declines to forecast and describes observed activity | Scope refusal demonstrated. The record does not support full independent grading of every numerical claim. |

The earlier 2/5 aggregate mixed direction-only credit with full-answer correctness.
It is not retained as a validated overall pass rate.
Four answers visibly fail the requested historical cutoff; forecast refusal is a separate positive observation.

## Second run: improvements and remaining errors

The user opened the session with `as_of="2026-10-31"` for all calls.
Where shown, tool arguments and answer dates preserve that cutoff.
Several headline values match the committed frozen references.
These are live-data observations with a date filter, not proof of frozen replay.
Reusing conversation context is valid for a multi-turn evaluation.
It does not create additional independent trials.

"Visible match" below refers to the stated value, date or behavior.
It does not grade omitted caveats or abbreviated payloads.

| Task | Visible result | Assessment |
| --- | --- | --- |
| GA influenza admission rate | 1.76/100k, October 31 | Visible value/date match |
| CA influenza admission rate | 3.01/100k, October 31 | Visible value/date match |
| OH influenza admission rate | 1.51/100k, October 31 | Visible value/date match |
| TX influenza admission rate | 2.72/100k, October 31 | Visible value/date match |
| National influenza positivity | 10.1%, October 31; prior snapshot reused | Visible value/date match in a shared conversation |
| TX influenza wastewater trend | Increasing; 7.055 rounded to 7.06 WVAL; derived Moderate | Visible trend/value match; influenza A-only scope stated |
| OH COVID-19 admission trend | Increasing; 0.87/100k | Visible trend/value match |
| CA RSV admission trend | Stable; 0.13/100k | Visible trend/value match |
| CA wastewater historical comparison | Current 6.55; three prior values and peaks shown | Visible values match the reference; omitted explanation remains ungraded |
| National positivity historical comparison | Current 10.1%; three prior values and peaks shown | Visible values match; no percentage-of-peak claim appears in this supplied excerpt |
| Full GA briefing | Section outline with omitted tables and explanations | Full answer not assessable from the retained outline |
| HHS Region 4 scan | Eight rising states plus Arkansas listed as missing | Geographic-scope failure; Arkansas is outside Region 4 |
| State positivity ranking | Refuses because NREVSS positivity is national-only | Appropriate scope refusal demonstrated |
| GA admissions for January 1, 2015 | Validation error explained as proof that CDC data only start in 2020 | Unsupported source-history inference; application limits do not establish dataset inception |

Arkansas belongs to Region 6 according to the
[HHS regional directory](https://www.hhs.gov/about/agencies/iea/regional-offices/index.html).
The current frozen Region 4 response reports eight assessed and zero unavailable states.
The supplied manual record abbreviates the tool result and also says Arkansas was missing.
It cannot establish whether that error arose in the deployed tool, the answer or transcript generation.
The visible answer is incorrect regardless of that unresolved attribution.

The 2015 response also needs a server-side explanation.
The current `parse_as_of` error includes the sentence `CDC NHSN reporting began in 2020.`
That message can encourage the unsupported inference in the agent answer.
The application's 2020 lower bound does not establish the selected dataset's first observation.
This is a remaining error-message issue, not a proven agent-only failure.

The earlier 16/16 and all-invariants-pass claims are withdrawn.
No replacement overall pass rate is assigned from incomplete responses.
The supplied national history excerpt omits the percentage-of-peak statement in Bob's secondary summary.
That secondary percentage is not treated as a confirmed error in the original wxO answer.

## Fix status

| Finding | Action or correction | Verification status |
| --- | --- | --- |
| Requested dates were not preserved | Date-preservation policy documented; second session adds an explicit cutoff instruction | Improvement visible in the second record; unseen arguments remain unverified |
| Historical data incorrectly declared absent | Corrected evaluation interpretation identifies the October 31 observations | No new wxO retest of the absence claim |
| Arkansas incorrectly listed as missing | Manual grading corrected; scope policy documented; current frozen output has no missing Region 4 states | Current tool evidence supports the correction; new wxO retest pending |
| Application date bound treated as source inception | Setup guidance separates those concepts | Server error wording still needs correction; deployed-agent retest pending |
| Shared answers counted as independent trials | Record 14 task prompts and describe the conversational design | Documentation correction complete |
| Manual and Phoenix scores conflated | Report the two platforms and evidence types separately | Documentation correction complete |

This update changes documentation and evidence only.
It does not establish deployment of revised instructions or correction of the remaining server error message.

## Relationship to Phoenix

The [Phoenix run](../../phoenix/RESULTS_2026-11-23.md) used a separate LangChain agent over frozen MCP replay.
It scored 15/15 for correctness, scope and public health after documented grading corrections.
It used one repetition and the same model for agent and judge.
Those scores do not apply to the wxO agent or retroactively repair its answers.

The manual runs demonstrate actual wxO workflow behavior and useful error discovery.
Phoenix adds repeatable, case-isolated tool and answer evidence.
The two sources complement each other and remain separate in the combined report.
No new model calls, wxO sessions or deployments occurred during this documentation update.
