# wxO setup and live evaluation

For the repository mcp-eval skill workflow, use [the Phoenix harness](../eval/phoenix/README.md).
That local LangChain agent needs a model API key, not wxO credentials. The rest of
this document applies only to a separate evaluation of an actual wxO agent.

Local tests and frozen tool replay need no wxO credentials. Live integration and
agent scoring require the sandbox instance/service URL, agent ID, authentication
type (for example IBM IAM), and a suitably scoped API key. Store the key in the
ignored root .env file or the service credential mechanism; do not paste it into
a committed file, evaluation case, or transcript. .env.example lists placeholders.
The user supplied two manual wxO records. The [review](../eval/transcripts/wxo/MANUAL_REVIEW_2026-11-23.md)
links unchanged originals and separates visible findings from omitted evidence.

## Connect the sandbox server

Choose the local MCP toolkit in deploy/ibm/local-mcp-toolkit or the remote sandbox
kit in deploy/ibm. All now reference resp_mcp.server. Check the kit instructions
against your installed IBM ADK version before importing. A local toolkit stages
the package and its complete runtime dependencies; a remote toolkit requires a
sandbox MCP endpoint reachable from wxO. Do not use the removed example cloud URL.
The API key for wxO does not authenticate the MCP server by itself.

Verify that tools/list exposes four tools and their actual parameter constraints.
The exact advertised schemas are exported to docs/schemas/mcp_tools.json.
Check all three resources and both prompts if the client supports them. Then call
one valid lookup, one invalid jurisdiction, and a multi-source briefing. Record
cold/warm latencies and the server/model/agent versions. Retain this evidence for
each new evaluation run.

## Agent instructions

Use this policy even if wxO does not consume MCP prompts or resources:

Copy the complete [active RSA policy](WXO_AGENT_POLICY.txt) into the agent instructions.
This file is the source for the policy deployed during the November 23 retest.
It preserves dates in individual questions and explicit session cutoffs.
It also covers regional scope, units, trend calculations and tool errors.
Do not add a fixed benchmark cutoff for normal use.

For a contextual replay of eval2, supply its original session cutoff instruction.
For independent natural-language testing, start each question in a fresh conversation.
Report these designs separately.

## Agent evaluation

Use the 25 natural-language prompts in eval/cases.yaml in fresh conversations.
The listed calls are expected reference plans; do not give them to the agent.
For deterministic scoring, the agent must connect to a sandbox server using the
same frozen snapshot. Otherwise label the run a separate live-data test.
Record actual calls and arguments, final answers, source/number/date/geography
fidelity, preserved caveats, latency, and failure handling. Run three repetitions
when practical. Use eval/RESULTS.md for tool, manual wxO and Phoenix findings.

### Recorded manual evaluations

The [manual review](../eval/transcripts/wxo/MANUAL_REVIEW_2026-11-23.md) includes five first-run questions and 14 second-run task prompts.
The first run failed to preserve dates already present in the user's questions.
The second session added an explicit cutoff instruction and shows improved date handling.
Several visible values match the frozen reference, but live queries can include later revisions.

Two second-run explanation problems remain: Arkansas is outside the requested Region 4,
and the application date bound does not establish CDC dataset inception.
The earlier server error wording could contribute to the latter inference.
The shared message is now corrected and has regression coverage across four tools.
The [targeted retest guide](WXO_TARGETED_RETEST.md) covers the toolkit update and six focused wxO questions.

The local server correction does not update an uploaded wxO toolkit automatically.
RSA now uses `respiratory_mcp_local_v3`, including the scan membership and attribution fixes.
See [the scan-fix verification](WXO_SCAN_FIX_2026-11-23.md) for current deployment details.
See [the runtime verification](WXO_RUNTIME_VERIFICATION_2026-11-23.md) for the new tests and remaining limits.
The earlier 2/5 and 16/16 overall rates are not validated aggregate scores.
The manual evaluations remain useful evidence alongside the separate Phoenix run.

## Evaluation without a model API

Use existing wxO sandbox access for a **manual assessment**. Phoenix's current
agent and semantic judges cannot use a wxO service key as a model gateway key.
No additional provider is required for this manual route.

1. Start a fresh conversation for each question in eval/cases.yaml. Give the
   agent only the natural-language question and date-preservation policy, not
   reference calls, expected values or the scoring rubric. Do not preload a
   national snapshot or reuse previous answers.
2. Record agent ID/version, model ID if visible, toolkit/server commit, transport,
   timestamp/timezone and whether the data source is live or frozen. A dated
   live query must be labeled live, even when values match snapshot_v2.
3. Save exact prompts, actual tool names/arguments, complete tool responses and
   final answers using an export if available. Redact credentials before saving.
   A reconstructed prose summary is weaker evidence and must be labeled as such.
4. Review answer correctness, tool choice, arguments, source/date/unit/geography
   fidelity, missingness, historical denominators and scope refusal separately.
   Compare live answers with their actual tool payloads; use frozen references
   for exact-value scoring only when the server actually replayed that snapshot.
5. Mark untested cases **not run**, insufficient evidence **unverified**, and
   provider/tool failures **execution error**. A matching headline value cannot
   excuse a material misleading explanation. Do not count one answer reused in
   another case as an independent successful trial.
6. Have a second reviewer inspect public health claims when available. Report the
   number attempted, with retained evidence, fully scored, passed, failed and
   unverified. For repetitions, use fresh sessions and report variability.

Critical checks: national positivity cannot support local concordance; derived
wastewater aggregates are not official state levels; outages are not stability;
rank/peak denominators need eligible history; observation dates are not publication
vintages. Missingness applies only to requested jurisdictions. The frozen Region 4
scan has eight assessed and zero unavailable states; Arkansas is in Region 6.

The earlier 16/16 walkthrough claim is superseded by the audit in eval/RESULTS.md.
Do not relabel a manual assessment as an automated Phoenix or independent batch run.
