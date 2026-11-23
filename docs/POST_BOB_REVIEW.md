# Post-Bob review — 2026-11-22

> Code follow-up 2026-11-23: the shared date-error wording is corrected and covered across all four tools.
> Later status: v3 passed 386 tests and the targeted API checks. The user also supplied a successful six-question manual retest.
> See [current submission status](SUBMISSION_CHECKLIST.md). Earlier pending statements below are historical.

> Source update 2026-11-23: the user supplied both original manual wxO records.
> The [case review](../eval/transcripts/wxo/MANUAL_REVIEW_2026-11-23.md) supersedes earlier source attribution and question counts.
> The original questions explicitly requested dates. The server's date-error wording can contribute to the source-inception error.
> Historical observations below remain dated review notes, not the latest combined evaluation report.

> Update 2026-11-23: organizational model access is now configured locally. A real Phoenix run completed all 15 cases.
> See [the results and limitations](../eval/phoenix/RESULTS_2026-11-23.md). Earlier statements about unavailable model access describe the prior review.

Reviewed GitHub main through 0beed5e and the supplied local
Build_Summary/respiratory-mcp-project-summary.html. The implementation is a
working descriptive-surveillance prototype. Automated agent performance is
still unmeasured; the submission should state that clearly.

## Findings and fixes

| Finding | Action |
| --- | --- |
| Region 4 manual answer calls Arkansas missing and receives PASS | Corrected grading/reporting: Arkansas is in Region 6. The frozen tool response has eight assessed and zero unavailable states. Retained the original summary with an audit warning. |
| README attributes Georgia concordance to national positivity | Corrected explanation: local admissions rise while local wastewater is stable; national positivity is excluded. The returned early_warning pattern itself is unchanged. |
| Live `as_of` queries described as frozen/reproducible | Clarified that date filters do not exclude revisions or activate replay. Frozen references must not replace actual live responses during a demo. |
| Source history inferred from a short capture | Distinguished 29 captured NHSN weeks from source inception and the reporting-transition comparability caveat. |
| Manifest hash depends on exact CRLF bytes | Added Git attributes to preserve snapshot_v2 bytes under all checkout newline settings, retaining the existing reference hash. Removed the need for manual newline conversion. |
| A custom benchmark CSV could omit difficult questions | Reject incomplete case inventories and duplicate XML IDs; added regression coverage. |
| CI only ran lint/tests | Added frozen installs, complete dataset validation, deterministic replay, actual MCP transport and scripted agent checks, plus a tool-evidence artifact. |
| HTML handoff embeds an exposed PAT | Redacted the local copy and marked it superseded. No token copied into Git; revoke it in GitHub. |
| Docker verification claims conflate different tests | Labeled RHEL container results as Bob-reported and distinguished the transport script's subprocess/in-process checks from a running-container test. |

Geography was checked against the
[HHS regional directory](https://www.hhs.gov/about/agencies/iea/regional-offices/index.html).
No production analytical thresholds, raw snapshot data or expected answers were
changed. Existing raw tool evidence is retained; the wxO summary is human-written,
not a raw provider export.

## Verified locally

- Full suite: **360 passed**, 94% server line coverage. Two upstream ldap3/pyasn1
  deprecation warnings remain. Windows temporary-file/process restrictions
  required approved execution outside the sandbox.
- Frozen tool baseline: **25/25 cases, 155/155 assertions**.
- Phoenix dataset and experiment dry-runs: all **15 cases**, no credentials or
  model calls. Snapshot manifest hash remains
  `806ca24b42709a745858cec8684021d7a2cbf0a25ce732c75731801deb20c05a`.
- Git clean-filter regression checks: exact manifest bytes preserved with
  core.autocrlf false, true and input. This is not a claim of a local Linux run.
- Actual stdio MCP and in-process HTTP ASGI transport verification passed.
- Scripted LangChain agent: two frozen MCP tool calls, outage isolation and
  Phoenix evaluator contracts passed. No live model or wxO call was made.
- Ruff lint/format, offline lock consistency and whitespace checks passed.

Reproduce using the commands in VERIFICATION.md and eval/phoenix/README.md.
The updated workflow is configured to run credential-free checks on Ubuntu.
After pushing the fixes, GitHub's public API lists CI as active but reports zero
workflow runs for the entire repository. A remote pass is therefore unverified.
The workflow also supports manual dispatch. In GitHub's Actions tab, allow fork
workflows if prompted, check repository Actions permissions, then select CI and
Run workflow on main. Do not describe local verification as a GitHub CI pass.

## Remaining work with current access

The user has a wxO service URL/key and no model API gateway. Use the
[manual wxO procedure](WXO_AGENT_SETUP.md#evaluation-without-a-model-api) with
fresh conversations and complete retained evidence. Do not reuse the old 16/16
score. Include scope refusal, missingness, cutoff preservation and failed-source
scenarios only when the relevant conditions are actually exercised. Live access
alone cannot reproduce a controlled all-source outage.

The provided sample evaluation document recommends a no-tool comparison,
repetitions, latency/cost tracking and human review. A manual wxO comparison can
disable the toolkit in a separate agent with the same visible configuration;
record any model/configuration differences and do not claim causal tool lift
when they are uncontrolled. Those measurements have not been performed here.
The sample is guidance, not evidence that every example metric is mandatory.

Real Phoenix agent/judge experiments require a compatible model API. The existing
wxO key is not interchangeable. No additional service purchase is assumed.
The implementation uses LangChain's native MCPAdapter over stdio, contrary to
the HTML summary's statement that it uses native HTTP ClientSession.

Before submission, rehearse against the actual toolkit and inspect all displayed
claims. Confirm the final tag references the intended commit and that required
slides, recording and submission-form fields are complete. The old
v1.0-hackathon tag is not moved by this review. Current event requirements and
deadline were not verified: the GSA event page could not be retrieved during
this audit. No new deployment or public image publication was performed.
