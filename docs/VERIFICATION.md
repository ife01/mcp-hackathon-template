# Verification record — 2026-11-22

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

`scripts/verify_transports.py` run against the live container confirmed:
- stdio subprocess: initialize, list 4 tools / 3 resources / 2 prompts, call, read resource **PASS**
- HTTP ASGI in-process: initialize, tools/list, tools/call, /health **PASS**

No CDC network calls, wxO session, external deployment, or public registry action
occurred. The cloud.gov manifest creates no public route. No deployment or
publication has been performed.

Live wxO import, service authentication, tool selection, final answers, and live
latency are also confirmed through the two manual wxO runs recorded in
eval/RESULTS.md. Local tests and frozen tool evaluation need no wxO credentials.

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
- scripts/verify_phoenix_harness.py: actual LangChain graph, two independently
  chosen scripted tool calls, per-case source outage, ClassificationEvaluator
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
