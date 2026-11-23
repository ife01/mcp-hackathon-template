# Decision Log

All deviations from the build plan are recorded here with a date and rationale.

## 2026-11-23 — Integrate the user's original manual wxO records

Preserved both supplied conversation files unchanged, with file hashes and a separate case review.
These generated records take precedence over Bob's secondary summary where they differ.
The records remain valid manual integration evidence despite abbreviated payloads and failed answers.

The first questions explicitly supplied the historical date.
Later-week answers represent date-preservation failures, not missing user instructions.
The second record contains 14 task prompts, plus a preamble and a transcript-generation request.
Overlapping benchmark mappings do not create 16 independent trials.

Documented the Region 4 geography error and the unsupported source-inception inference.
The current server error itself states that NHSN reporting began in 2020.
Its wording can influence the agent and remains a runtime issue to correct.
This documentation update does not claim that correction or a new wxO retest.

Removed the unvalidated 2/5 manual aggregate from the active summary.
Retained the withdrawal of the secondary summary's 16/16 claim.
Visible successes and failures remain separate from unassessable excerpts.
Phoenix scores apply only to its separate LangChain agent and frozen-data experiment.
No original records, frozen references, runtime prompts or model scores were changed.

## 2026-11-23 — Reuse existing organizational model access

The user identified an existing local homework configuration for an organizational gateway.
Read its authentication implementation without changing the homework files.
Copied only required gateway configuration into the respiratory project's ignored .env.
No credentials or private gateway identities enter Git or the serializable model configuration.

Added an evaluation-only Azure adapter with client-credential token refresh and a subscription header.
The synthetic tool/schema check passed. Both roles use the existing configured small model.
Experiment metadata records same-model judging; it is a limitation, not independent validation.

The 15-case v2 run produced all answers without agent errors.
Initial grading had 17 throttled calls and three false numeric-check failures.
Added request spacing, bounded 429 retry and regression-tested numeric corrections.
Resumed only missing judgments and rescored the affected grading logic.
No agent answers, references, prompts or frozen data changed.
All 120 final metric records are present, with no remaining execution errors.
Correctness, scope and public health each score 15/15 on this single run.

The report preserves initial grading, revised grading, source identities and limitations.
Full offline verification passes 369 tests at 94% server coverage.
See eval/phoenix/RESULTS_2026-11-23.md for the evidence.

## 2026-11-22 — Follow-up evidence and portability audit

Read Bob's local Build_Summary HTML and fetched main through 0beed5e. Historical
entries below retain their reported date labels and reviewer conclusions; this
entry supersedes their 16/16 and all-invariants-pass claims. D5 incorrectly treats
Arkansas as missing from Region 4; it belongs to Region 6, and the actual frozen
tool response reports 8 assessed / 0 unavailable. Shared-session answer reuse
and missing raw traces prevent a validated replacement aggregate score.

Corrected the README's local concordance explanation to exclude national
positivity. Date cutoffs on live CDC queries do not select frozen data. Capture
coverage of 29 NHSN weeks does not establish the source's earliest history.
Corrected the demo and evaluation guidance to preserve these distinctions.

Preserve exact snapshot_v2 bytes with .gitattributes rather than manually
rewriting manifest newlines. The committed manifest already has CRLF and its
existing identity remains unchanged. Reject incomplete or duplicate benchmark
case inventories. Add credential-free benchmark, replay and agent/transport
integration checks to CI. Geographic scope is explicit in the public health judge.

The user has wxO service access but no model API access. Real Phoenix semantic
scoring remains not run; a rigorous manual wxO procedure is documented instead.
The local HTML embedded an exposed PAT; it was redacted without copying the
credential into Git. No provider calls, new deployments or registry publication
were performed. Details and verification are in POST_BOB_REVIEW.md.



## 2026-11-23 — Build 4.3/4.4: Second wxO live run — 16/16 pass after as_of fix

**What happened:** Second manual wxO agent walkthrough. Session opened with the
instruction `"For all tool calls in this session, use as_of="2026-10-31"."` All tool
calls correctly used the frozen cutoff throughout. 16 of 25 cases.yaml cases were
explicitly exercised; the remaining 9 are covered by the deterministic tool baseline.

**Result:** 16/16 ✅ — 100% pass rate. Full scorecard in eval/RESULTS.md.

**Improvement vs run 1:** 40% → 100% pass rate. The single root-cause fix (instructing
the agent to pass `as_of`) resolved all run-1 date/value mismatches. No tool code changes
were required.

**Notable observations:**
- Agent called `get_respiratory_snapshot(USA)` proactively as a national baseline,
  then correctly scoped positivity as "national only" in all state briefings.
- Small-number guard applied correctly for CA RSV (0.13/100k → stable despite +47% ratio).
- Prior-season NHSN rank correctly withheld for GA and OH (insufficient history).
- AR missing from HHS Region 4 scan correctly flagged as "missing, not evidence of stability".

**Decision:** Build 4.3/4.4 complete. No code changes needed. eval/RESULTS.md updated with
second-run scorecard and before/after comparison. Transcript saved to
eval/transcripts/wxo/run2_2026-11-23.md.

---


## 2026-11-22 — Build 3.5: First wxO live run — `as_of` not passed; values correct for live data

**What happened:** First five-question wxO agent walkthrough via local MCP toolkit
(stdio transport, `respiratory_mcp_local`, ca-tor instance). Agent used live CDC
data because no `as_of` parameter was passed in the prompts.

**Observed discrepancies vs. frozen reference (as_of 2026-10-31):**

| Q | Metric | Reference (2026-10-31) | Agent (2026-11-14 live) | Delta |
|---|---|---|---|---|
| Q1 | GA flu admissions/100k | 1.76 | 2.47 | +0.71 — later week |
| Q3 | National flu positivity | 10.1% | 11.8% | +1.7pp — later week |
| Q4 | Rising states count | Reference at 2026-10-31 | 44 at 2026-11-14 | Different week |

**What was correct:** Q2 (trend direction = increasing), Q5 (refused forecast).
All public health invariants passed: national positivity cited as national-only;
numeric claims grounded with dataset ID and week-ending date; trend labeled heuristic.

**Root cause:** The wxO agent instructions (docs/WXO_AGENT_SETUP.md §3) did not
include the `as_of="2026-10-31"` rule that `system_prompt_v2.txt` already contains.

**Fix:** Added explicit `as_of` instruction to WXO_AGENT_SETUP.md under agent
instructions. For live production use the agent's behavior (most recent data) is
correct and expected. The `as_of` parameter is only required for reproducible
deterministic evaluation against the frozen benchmark.

**Decision:** No tool code changes needed. The discrepancies are expected behavior
for a live-data run, not tool bugs. Results recorded in eval/RESULTS.md.

---


## 2026-11-20 — Build 4.1: langchain-mcp-adapters excluded; native mcp 2.x HTTP transport used

**What changed:** The build plan and mcp-eval skill both reference `langchain-mcp-adapters` for
connecting the LangChain eval agent to the MCP server. This package was not added.

**Why:** `fastmcp>=4.x` (required by this project) depends on `mcp>=2.3.0`. All published
versions of `langchain-mcp-adapters` (up to 0.3.2 as of 2026-11-20) require `mcp<2.0.0`.
These are mutually exclusive at the package level and cannot coexist in the same virtualenv.
Specifically, `langchain-mcp-adapters` imports `mcp.server.fastmcp` (removed in mcp 2.x),
`mcp.shared.context.RequestContext` (renamed to DispatchContext), and `mcp.shared.session`
(module removed entirely). No shim can repair a missing module.

**Decision:** The eval agent uses the **native mcp 2.x Python client** (`mcp.ClientSession`
with `streamable_http_client`) to connect to a running server over streamable-HTTP, then
wraps the tool definitions as LangChain `StructuredTool` instances manually. This is a
functional equivalent of langchain-mcp-adapters for the HTTP transport case. The agent
requires the MCP server to be started separately before evaluation (see eval/phoenix/README.md).

**Impact:** eval/phoenix/agent.py does not import langchain-mcp-adapters. The `--check-mcp`
flag verifies the server is reachable using the native client. Functionality is unchanged.

---

---

## 2026-11-20 — Build 0.1: MCP Inspector replaced with curl-based MCP handshake

**What changed:** The plan calls for verifying `example_search_datasets` via MCP Inspector
(`npx @modelcontextprotocol/inspector`). Inspector could not be used for this purpose.

**Why:** Two incompatibilities with the VM environment:
- Inspector v1 (≤0.15.0) crashes on Node 20 with `ERR_PARSE_ARGS_INVALID_OPTION_VALUE`
  due to a flag-parsing regression introduced in that Node version.
- Inspector v2 (≥2.0.0) requires Node ≥22; the VM has Node 20.

**Decision:** Verified tool invocation using a direct 3-step MCP streamable-HTTP handshake
(`initialize → tools/list → tools/call`) via curl against `http://localhost:8000/mcp`.
All three steps succeeded with correct JSON-RPC responses:
- `initialize` → session ID returned, server name "Example MCP Server", protocol 2024-11-05
- `tools/list` → `example_search_datasets` listed with full schema
- `tools/call` → 5 placeholder results returned for query "transportation", `isError: false`

**Impact:** Acceptance criteria met equivalently. Inspector can be revisited if Node is
upgraded to ≥22 later in the project.

---

## 2026-11-20 — Build 0.1: wxO Early Integration Check deferred

**What changed:** Step 13 (import template into wxO, call tool from a test wxO agent)
has not yet been completed.

**Why:** wxO environment credentials/access not yet confirmed by the human owner.

**Decision:** Proceeding to Build 0.2. wxO integration will be completed in Build 3.5
(manual walkthrough) once domain tools are implemented. The 🛑 Human checkpoint for wxO
access remains open.

## 2026-11-20 — Build 0.2: Package layout mapping and wxO transport choice

**Layout mapping:** `src/example_server/` will be renamed to `src/resp_mcp/` in
Build 0.4. `app.py` becomes `server.py` (per the plan's architecture). `models.py`
splits into `models/common.py` and `models/tool_io.py`. `utils.py` is replaced by
the hardened `clients/socrata.py`. All other submodule paths map 1:1 (see
docs/NOTES_TEMPLATE.md §2 for the full table).

**wxO transport choice:** Streamable HTTP (remote MCP toolkit via IBM Code Engine or
prebuilt image) is the target for the Phase 5 container demo — it gives wxO a stable
public `/mcp` URL and matches the hackathon judging setup. Local MCP toolkit (stdio
inside Orchestrate) is the fallback if Code Engine credentials are unavailable during
the weekend. The local toolkit is lowest overhead and uses the same server code
unchanged (no transport change needed in `server.py`).

## 2026-11-20 — Build 0.3: NREVSS dataset ID retired; replacement selected

**What changed:** The plan listed `j8mb-3ugh` as the NREVSS dataset ID (marked
`verify`). It returns HTTP 404 as of 2026-11-20.

**Replacement datasets (both confirmed live):**
- **`seuz-s2cv`** — "Percent of Tests Positive for Viral Respiratory Pathogens" —
  national-only, all 3 pathogens (Influenza, COVID-19, RSV), updated 2026-11-20.
  **Primary NREVSS source** for test positivity.
- **`rgnm-fkqb`** — "NREVSS NAAT positivity multi-pathogen" — HHS region + national,
  SARS-COV-2 and RSV only (no influenza). State-level rows exist in schema but returned
  empty for GA/CA/OH/TX during recon. **Used as HHS-region fallback for RSV/COVID only.**

**Impact:** `seuz-s2cv` is national-only. The NREVSS adapter will return
`geography_level="national"` for all jurisdictions and include caveat
`"Test positivity data is only available at the national level from this source"`.
This matches the plan's documented fallback: `NREVSS has no state-level data → use
state's HHS region (or national)`.

---

## 2026-11-20 — Build 0.3: NWSS dataset selection

**What changed:** The plan listed `2ew6-ywp6` (NWSS Public SARS-CoV-2 Wastewater
Metric Data) as the NWSS source. This dataset is COVID-only (site-level, 2-week
rolling metrics). Three separate pathogen datasets also exist (`ymmh-divb` flu,
`45cq-cw4i` RSV), but all are raw sample-level, not aggregated.

**Decision:** Use **`atcp-73re`** — "CDC Wastewater Viral Activity Level for
SARS-CoV-2, Influenza A and RSV" — as the primary NWSS source. It covers all 3
pathogens in one dataset, provides the official `site_wval_category` (Very Low →
Very High), is updated 2026-11-20, and covers 53 state/territory jurisdictions.
It is site-level (one row per site per pathogen per week); the adapter aggregates
to state level by computing median `site_wval` across sites.

**Puerto Rico**: zero rows in `atcp-73re` — no wastewater surveillance sites.
Status → `"insufficient_coverage"`.

---

## 2026-11-20 — Build 0.3: NHSN counts vs. rates decision (vdzy-6i9v rate/level)

**Decision:** Use **published rates and official levels** from `vdzy-6i9v` as the primary signal:
- `totalconfflunewadmper100k` / `totalconfc19newadmper100k` / `totalconfrsvnewadmper100k`
- `totalconfflunewadmper100klevel` / `totalconfc19newadmper100klevel` / `totalconfrsvnewadmper100klevel`

Raw counts (`totalconfflunewadm` etc.) are retained in the data but used only for
the small-number guard in trend analytics (< 10 admissions average).

All 3 pathogens have parallel `hosprep` columns (`totalconfc19newadmhosprep`,
`totalconfflunewadmhosprep`, `totalconfrsvnewadmhosprep`) — confirmed from live data.
Values are identical per row (one hospital reporting count per week regardless of pathogen).
The adapter attaches `totalconfflunewadmhosprep` as the coverage indicator.

---

## 2026-11-20 — Build 0.3: NWSS site_wval_category aggregation strategy

**Decision:** `site_wval_category` (Very Low / Low / Medium / High / Very High) is
CDC-assigned per site and cannot be reliably derived from the numeric `site_wval`
value — fixture data shows overlapping numeric ranges between adjacent categories.

The NWSS adapter must:
1. Use `site_wval_category` **directly from source data** (never recompute from wval).
2. Aggregate to state level using **modal category** across reporting sites for `official_level`.
3. Compute **median `site_wval`** as the numeric value for trend analytics.

Observed numeric ranges (GA + CA fixtures): Very Low ≈ 0.15–2.59, Low ≈ 1.71–5.46,
High ≈ 5.53–15.40, Very High ≈ 8.62–170.15. Medium not observed — may appear at peak.

---

## 2026-11-20 — Build 0.3: Eval as_of date set to 2026-10-31

**Decision:** Eval snapshot frozen at **`as_of=2026-10-31`** — 2 weeks prior to
the minimum latest-available date across all three sources (all had data through
2026-11-14 as of reconnaissance on 2026-11-20). Two-week buffer ensures data
finalization across all reporting systems.



## 2026-11-22 — Public health correctness and evaluation preparation

This entry supersedes earlier decisions assigning modal wastewater categories
to official_level, applying national values to state observations, inferring no
sites from empty results, and treating a two-week lag as finalization.

- NREVSS observations remain USA and are national context for state queries.
  They are excluded from local concordance and cannot support state scans.
- Wastewater uses distinct valid sites; conflicting duplicates are excluded.
  The median and unique modal category are explicitly derived, not official.
  Two sites do not establish population representativeness; coverage is unknown.
- Trends require four consecutive recent weeks; no backdating over missing
  values. NHSN counts reach the small-number guard, which requires BOTH window
  means below 10. Missing counts are disclosed. The reported window is four.
- No historical data means null rank. Complete eligible seasons alone supply
  peaks. Fallbacks return the actual observation date; season boundaries and
  reporting-transition exclusions are explicit. Single signals cannot agree
  with themselves and therefore cannot establish concordance.
- Empty, insufficient-coverage, unavailable, and partially assessed results are
  distinct. Scans use one logical paginated query and report the total before
  limiting, with per-jurisdiction provenance. Source failures cannot imply zero
  rising activity. Query cap/deadline breaches return errors rather than partial
  series. Sources/pathogens in snapshots run concurrently.
- Captured a NEW snapshot_v2 through 2026-10-31 with metadata, per-pathogen
  coverage and SHA-256 hashes. Full pagination repairs short NWSS extracts.
  NHSN returned only 29 weeks from this endpoint despite requesting 2023 onward;
  valid historical abstention remains required. Original snapshots are preserved.
  Gzip keeps every raw-data artifact below the plan's 2 MB file limit.
- Added 25 deterministic tool cases, independent raw-data calculations, HTTP
  replay with no network fallback, and transcripts. These are preliminary tool
  evidence; live wxO tool selection and answer grounding have NOT been scored.
- Fixed Docker entrypoint copying and frozen installs, deployment package names,
  actual tool input schemas, and documentation. Removed an unverified remote URL
  and disabled the example cloud.gov route. No deployment or publication occurred.

Validation outcomes and explicit unverified integrations are in VERIFICATION.md.
wxO service access, human review of methods/outputs, and final agent scoring are
still separate requirements from the build plan. No credentials were requested
or stored during local preparation.


### Published category label correction

The fresh capture includes the category **Moderate**, not Medium, in NHSN and
NWSS. Input enums, minimum-level filtering, prompts, resources, and active docs
now use the observed label. Historical decision entries above retain their
original wording. NHSN coverage is also read from the requested pathogen's own
reporting fields rather than borrowing influenza coverage.

### Phoenix agent evaluation harness (2026-11-22)

Implemented the mcp-eval workflow with independent frozen snapshot_v2 references,
15 questions, versioned prompts, separate agent/judge model settings, Phoenix
datasets/experiments/OTLP traces, three semantic judges and deterministic public
health evidence checks. Only query and case ID reach the agent; expected answers
and reference facts are reserved for evaluators. Scripted verification outputs
cannot pass the evidence gate or be reported as real model results.

The skill's legacy langchain-mcp-adapters cannot import RequestContext with the
installed MCP 2.x SDK. Use the locked LangChain native MCPAdapter with the real
FastMCP stdio transport instead of downgrading the production server or patching
libraries. This namespace is beta; actual subprocess and graph verification is
recorded in VERIFICATION.md. Evaluation dependencies remain development-only.

Disable automatic Phoenix/LangSmith pytest plugins to avoid unrelated storage
initialization during ordinary tests. Keep Phoenix storage inside ignored
.phoenix, bind its helper to loopback, and use UTF-8 for Windows console output.
No .env or model credentials were created. Standard Bearer Chat Completions
model access is needed for real evaluations; wxO authentication is separate.
