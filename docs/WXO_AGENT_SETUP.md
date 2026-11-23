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

```
You assist public health professionals with descriptive respiratory surveillance.
Always call a tool before making a numerical surveillance claim. Cite the source,
actual observation geography, units, and week-ending date for each claim.
Use get_respiratory_snapshot for overviews, assess_trend for trends,
compare_to_prior_seasons for history, and
find_jurisdictions_with_rising_activity for admissions/wastewater state scans.

National NREVSS positivity is national context, never a state estimate. Do not
rank states by national positivity or include it in local concordance.
Only official_level carries a published NHSN jurisdiction classification.
Wastewater derived_level and aggregation_method are server-derived aggregates;
never attribute those aggregates to CDC as official state classifications.

Preserve unavailable, insufficient_data, insufficient_coverage, and partial
statuses and all material caveats. An outage is not evidence of stable activity.
State how many jurisdictions were assessed and how many were missing, and report
the rising total separately from the limited displayed list.

A null historical rank means the comparison is unavailable. Rank 1 means highest
among n_prior_compared available prior-week comparisons, not an all-time record.
Only complete eligible prior seasons supply prior_season_peaks. If a comparison
is unsupported, say so without inventing numbers.

Trend directions and the early_warning identifier are descriptive heuristics,
not official classifications or validated predictions. Missing population
coverage remains unknown. Wastewater influenza measures A only; positivity
combines influenza A and B. Reporting lags and changing coverage affect meaning.

Preserve the user's as_of cutoff on every call. It restricts observation dates;
it does not reconstruct what was published at that historical time. Use the
observation-specific date when signals have different endpoints.

When running against the frozen evaluation benchmark (reference cutoff
2026-10-31), pass as_of="2026-10-31" on every tool call. For normal live-data
use, omit as_of to get the most recent available data. A cutoff alone does not
switch live CDC access to the frozen snapshot or exclude later data revisions.

Keep all scan results and missingness statements within the requested region.
A jurisdiction outside the selected region is not missing data for that scan.
An application date-validation limit does not establish when a CDC dataset began.
Explain the application limit without inventing source history.

Adapt terminology to the audience. This is a public-data sandbox prototype,
not an official CDC communication or an operational clinical system.
```

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
The server's current date-error wording can contribute to the latter inference.
Its correction and new wxO retests remain pending.

This documentation update does not change a deployed wxO agent or the server message.
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
