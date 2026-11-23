# Verification record

## Date-validation message correction — 2026-11-23

The shared error now describes 2020-01-01 as the application's supported lower date bound.
It no longer asserts when CDC reporting or a selected dataset began.
Regression checks exercise the actual MCP response from all four tools.
They also preserve acceptance of the boundary date.

The full offline suite passes **372 tests**, with **94% server line coverage**.
Two upstream ldap3/pyasn1 deprecation warnings remain.
The frozen tool baseline still passes **25 cases / 155 checks**.
No new paid model calls or wxO deployments were used for this fix.
The existing Phoenix result retains its original code identity and scores.
See [the targeted wxO retest guide](WXO_TARGETED_RETEST.md) for deployment and follow-up evidence.


## Manual wxO records integrated — 2026-11-23

The user supplied the original generated records for two earlier wxO evaluations.
Unchanged copies and SHA-256 hashes are under eval/transcripts/wxo/originals.
The [case review](../eval/transcripts/wxo/MANUAL_REVIEW_2026-11-23.md) covers five first-run questions and 14 second-run task prompts.

The records demonstrate wxO integration, date-handling improvement and appropriate scope refusals.
They also expose historical-cutoff failures, an out-of-region missingness claim and unsupported source-history inference.
The server's current date-error wording can contribute to the latter claim.
The message was corrected in a later code change documented below.
The deployed wxO toolkit still needs the update and a retest.

Originals retain their omissions and generated instructions as evidence only.
They do not constitute complete provider trace exports or independent repeated trials.
No replacement overall manual accuracy rate is assigned.
The separate Phoenix 15/15 result does not certify wxO performance.

This update changes documentation and evidence, not application behavior.
No new evaluation, deployment or paid model request occurred.
Documentation checks cover source hashes, question counts, relative links and credential exclusion.

## Organizational gateway evaluation — 2026-11-23

The full offline suite passes **369 tests** with **94% server line coverage**.
Two upstream ldap3/pyasn1 deprecation warnings remain.
New tests cover Azure authentication, credential-safe model serialization,
structured judging, deployment validation, throttling retry and numeric grading.

The live synthetic gateway check passed a tool round trip and structured judgment.
A later Phoenix run completed 15 fresh frozen-data case sessions.
Correctness, scope and public health each scored **15/15 pass**.
All 120 metric records are present, including one not-applicable tool-coverage score.
No agent errors, remaining judge errors or missing evaluations remain.

The initial 17 rate-limited judgments and three numeric grading errors remain
in the evidence. Recovery reused the same agent outputs.
Phoenix returned 249 stored spans. A targeted credential check found no matches.
The agent and judge used the same model; this is one repetition without a no-tool baseline.
Read [the full report](../eval/phoenix/RESULTS_2026-11-23.md) for evidence and limits.

## Latest follow-up verification — 2026-11-22

After reviewing Bob's updates, the full suite passes **360 tests** with **94%
server line coverage** and two upstream deprecation warnings. Frozen replay
still passes **25 cases / 155 checks**. Both Phoenix dry-runs, actual stdio and
HTTP ASGI transport checks, and the scripted agent integration pass. Git newline
settings false/true/input preserve the original snapshot manifest identity.
Ruff lint/format, lock consistency and whitespace checks pass.

See [POST_BOB_REVIEW.md](POST_BOB_REVIEW.md) for fixes and evidence limitations.
Historical sections below describe their original verification sessions; they
do not establish completed Phoenix real-model scoring. The user has no model API
access, and no new provider calls were made during this review.

## Automated tests

Environment: Windows, CPython 3.11.15, locked FastMCP 4.0.11 dependencies.

`python -m pytest tests/ -q -p no:cacheprovider --cov=resp_mcp --cov-report=term`

**327 passed; 94% overall line coverage.** Analytics aggregate coverage exceeds
90%; the Socrata client is 95%. The suite blocks unmocked HTTP by default. Test
cache output was disabled because of a workspace permission issue. The old
sleep-based cache-expiry test now uses a controlled clock, avoiding timer flakes.

Regression coverage includes actual advertised schemas, national geography,
local concordance exclusion, valid distinct wastewater sites, modal ties,
complete-season peak denominators, unavailable ranks, actual fallback dates,
53-week boundaries, latest-four-week continuity, small-count propagation,
missing-count notes, stale observations, negative/non-finite numbers, positivity
above 100%, total query deadlines, hard row caps, and scan missingness/totals.

## Code and schema checks

`ruff check .` passes. `ruff format --check .` passes. `git diff --check` passes.
The formatter also resolves the pre-existing failures. Exported model schemas and
actual registered input schemas are under docs/schemas; reproduce them with
`python scripts/export_schemas.py`.

## Frozen-data evaluation

`python eval/run_eval.py` passes **25/25 cases and 155/155 checks** against
snapshot_v2, with independent reference calculations and per-case JSON traces.
Hashes are verified before execution, and recorded run identities appear in
eval/RESULTS.md. This is a tool baseline, not LLM/agent evaluation.

The new public-data capture uses complete pagination and bounded chunks. The
original extracts are retained. Through 2026-10-31, NHSN returned only 29 weeks;
NWSS and NREVSS capture 175 weeks per pathogen for the recorded series. All new
raw-data files are gzip-compressed without information loss and below 2 MB each.

## MCP transport checks

`python scripts/verify_transports.py` passed:

- Real stdio subprocess: initialize, list four tools, three resources and two
  prompts, call an invalid jurisdiction, and read the methods resource.
- In-process streamable HTTP ASGI: initialize, tools/list, tools/call and /health.

Windows blocked subprocess pipe creation inside the restricted sandbox; the
same script passed after approved execution outside that restriction. These
checks make no CDC requests and do not establish a live wxO connection.

## Packaging and integration limits

The Python wheel builds successfully with uv, including an offline rebuild from
cached build dependencies. The Dockerfile now copies its entrypoint and uses
uv.lock with frozen runtime installation. Local/Databricks deployment references
use resp_mcp.server and local-toolkit dependencies include epiweeks and pyyaml.

Docker engine: Docker 29.10.0 on RHEL 9 (el9_6 x86_64).

```
docker build -t respiratory-mcp .          # 76 packages installed from uv.lock in 5.3s
docker run --rm -p 127.0.0.1:8080:8080 respiratory-mcp
curl http://127.0.0.1:8080/health          # → 200 OK {"status":"healthy","service":"respiratory-mcp-server"}
```

`scripts/verify_transports.py` separately checks the following; it does not
connect to a running Docker endpoint:
- stdio subprocess: initialize, list 4 tools / 3 resources / 2 prompts, call, read resource **PASS**
- HTTP ASGI in-process: initialize, tools/list, tools/call, /health **PASS**

No CDC network calls, external deployment, or public registry action occurred.
The cloud.gov manifest creates no public route.

wxO local MCP toolkit `respiratory_mcp_local` re-registered (2026-11-23) against
instance `api.ca-tor.watson-orchestrate.cloud.ibm.com` via `orchestrate toolkits import`
with updated `toolkit.yaml` description. Live wxO import confirmed successful.
Two manual wxO walkthroughs are recorded in eval/RESULTS.md. Follow-up audit
found a material geography error in the originally passing answer and withdrew
the aggregate pass claim. Local tests and frozen tool evaluation need no wxO
credentials.

## Phoenix agent harness verification (2026-11-22)

The mcp-eval implementation is in eval/phoenix, with 15 frozen-data questions:
10 multi-call comparisons and five public health/robustness cases. References
remain hidden from the agent. Correctness, scope and public health semantic
judges complement deterministic evidence checks; prompt versions are recorded.

With the locked evaluation dependencies installed, the full command above now
passes **355 tests with 94% server line coverage**. This coverage percentage
measures resp_mcp, not the evaluation harness. The 28 new tests cover dataset
integrity, configuration, reference drift, evidence and public health gates,
and actual ChatOpenAI/Phoenix judge clients with mocked HTTP. Two upstream
ldap3/pyasn1 deprecation warnings remain. Windows restricted temporary-file
access required approved execution outside the sandbox for the full suite.

Both create_dataset.py and run_experiment.py --dry-run pass without credentials,
uploads or model calls. The frozen tool suite still passes 25 cases / 155 checks.
Ruff lint/format, offline lock consistency and git diff whitespace checks pass.

Additional integration verification passed:

- agent.py --check-mcp: actual frozen stdio MCP tools and a tool response.
- scripts/verify_phoenix_harness.py: actual LangChain graph, two scripted tool
  calls, per-case source outage, ClassificationEvaluator
  templating and Score contract. These are scripted verification, not scores.
- scripts/verify_phoenix_storage.py against a temporary loopback Phoenix server:
  upload/readback/version validation of all 15 cases and experiment storage of
  15 explicitly labeled verification tasks, with no model scores.
- verify_phoenix_harness.py --collector-endpoint http://localhost:16006/v1/traces:
  OTLP export and persisted readback of 20 scripted spans.

The temporary Phoenix server was stopped. Its files stay in ignored .phoenix.
No real model API requests, wxO requests, deployment or publication occurred.
Real agent/judge performance, provider compatibility and provider latency remain
unmeasured until model endpoint, model IDs and authentication are configured.
See eval/phoenix/README.md and .env.example for the required local settings.
