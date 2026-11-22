# wxO setup and live evaluation

For the repository mcp-eval skill workflow, use [the Phoenix harness](../eval/phoenix/README.md).
That local LangChain agent needs a model API key, not wxO credentials. The rest of
this document applies only to a separate evaluation of an actual wxO agent.

Local tests and frozen tool replay need no wxO credentials. Live integration and
agent scoring require the sandbox instance/service URL, agent ID, authentication
type (for example IBM IAM), and a suitably scoped API key. Store the key in the
ignored root .env file or the service credential mechanism; do not paste it into
a committed file, evaluation case, or transcript. .env.example lists placeholders.
No live wxO session has been verified during this preparation.

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
cold/warm latencies and the server/model/agent versions. These checks remain
pending until service access is configured.

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
when practical. Use eval/RESULTS.md for the tool baseline and pending agent metrics.

Required next inputs: WXO_INSTANCE_URL, WXO_AGENT_ID, WXO_AUTH_TYPE, and a key
configured locally as WXO_API_KEY (or the platform's supported credential store).
The live runner/auth adapter should be selected after the service type is known;
no authentication flow has been guessed or exercised here.
