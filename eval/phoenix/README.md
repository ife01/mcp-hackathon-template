# Phoenix respiratory agent evaluation

This harness follows .agents/skills/mcp-eval/SKILL.md: an agent uses MCP tools,
independent frozen-data answers remain hidden, semantic judges score its final
response, and Phoenix stores datasets, experiments and traces. It complements
the earlier deterministic tool baseline in ../run_eval.py.

## What is implemented

- RespiratoryAgent, with a fresh frozen-data MCP subprocess and fresh conversation
  per case. The model chooses its calls; it is not fed expected call plans.
- Ten independently answerable, read-only, multi-call benchmark questions plus
  five supplemental public health/robustness cases. The scope-refusal case may
  correctly use no tools. Each question has one scalar answer and asks for a
  brief cited explanation. Questions are in datasets/respiratory-eval-0/evaluation.xml;
  the CSV and hidden reference facts are kept next to it.
- Independent references generated from snapshot_v2 using ../ground_truth.py;
  hashes and actual source coverage are verified. Complete seasons alone supply
  peaks; unavailable NHSN history requires abstention.
- Versioned v1/v2 prompts, separate AGENT_MODEL/JUDGE_MODEL settings, zero
  temperature, a bounded graph, serial agent tasks and at most two concurrent
  semantic judges. Different judge and agent models are preferred; using the same
  endpoint/model is recorded explicitly rather than concealed.
- Correctness, scope/relevance, and public health LLM-as-judge evaluators using
  Phoenix ClassificationEvaluator. The latter also applies deterministic gates.
- Dataset create/validate CLI, version-pinned experiment CLI, JSON evidence records,
  source/data/prompt identity, and OTLP traces. API/provider errors remain execution
  errors; they are never turned into a passing score or a model correctness result.

## Compatibility adaptation to the skill

The installed MCP SDK is 2.x with FastMCP 4. The skill's legacy
langchain-mcp-adapters MultiServerMCPClient fails to import with that SDK because
RequestContext was removed. This harness uses LangChain's maintained
`langchain.mcp.MCPAdapter` with an explicit StdioTransport, the same MCP server and
create_agent workflow. That namespace is currently marked beta; dependencies are
locked, and the actual stdio connection and graph have been verified.
No installed library is monkey-patched and no protocol is replaced by a fake.
See the [LangChain MCP documentation](https://docs.langchain.com/oss/python/langchain/mcp).
The alternative would be a separate MCP-1 environment; it is not required here.

## Before configuring .env: what model access is needed?

A model gateway is the programmatic API through which this harness calls a model.
It can be an agency USAi/internal gateway or another service implementing the
OpenAI Chat Completions request/response and tool-calling formats. A chat website,
chat subscription login, or wxO agent service URL is not sufficient information.
For example, [USAi documents an OpenAI-compatible API](https://www.usai.gov/api/).

Get these non-secret details from the service console or administrator:

| Detail | Configuration |
| --- | --- |
| Complete API base URL (or gateway origin) | USAI_BASE_URL |
| Exact agent model/deployment ID with function/tool calling | AGENT_MODEL |
| Exact judge model/deployment ID | JUDGE_MODEL |
| Authentication method | This adapter currently supports a standard Bearer API key |
| Extra headers, project/tenant ID, API version, proxy/certificate requirements | Tell us before configuring; an additional provider adapter may be needed |

Store the secret locally as USAI_API_KEY in the ignored repository-root .env.
Do not paste it into chat or commit it. The legacy USAI_* variable names work for
other compatible providers too. JUDGE_BASE_URL/JUDGE_API_KEY optionally override
judge access; otherwise the same gateway/key is reused. AGENT_MODEL and JUDGE_MODEL
are intentionally separate. No default model name is guessed because deployments
vary. Neither a wxO URL nor a wxO API key is required for this local agent workflow.
IBM watsonx.ai or other native APIs with token exchange/project IDs may require a
provider-specific adapter; a wxO key must not simply be substituted as a model key.

The agent model must support ordinary Chat Completions tool calls and temperature
0. The judge must support JSON-schema structured output or forced function calls,
also at temperature 0. Use a context window sufficient for the returned tool
records (32k tokens is a practical starting point for these cases). The harness
rejects oversized judge inputs rather than silently truncating evidence.
A real model run consumes your provider quota; no such calls have been made during
implementation. Model selection and provider capability remain to be confirmed.

USAI_BASE_URL may be a complete base ending /api/v1, /v1 or /openai/v1; no second
suffix is added. For a bare origin, USAI_API_PATH defaults to /api/v1. Do not append
/chat/completions to the base. TLS verification stays enabled, and custom clients
do not implicitly use environment proxies. Tell us if your service requires one.

For a local Phoenix server, no Phoenix credential is needed. For hosted Phoenix,
also provide PHOENIX_ENDPOINT, PHOENIX_COLLECTOR_ENDPOINT and PHOENIX_API_KEY if
required. These are separate from the model service credentials.

## Install and pre-flight without credentials

From the repository root:

```shell
uv sync --frozen --group dev
uv run python eval/phoenix/build_dataset.py
uv run python eval/phoenix/create_dataset.py --list
uv run python eval/phoenix/create_dataset.py --dataset-name respiratory-eval-0 --dry-run
uv run python eval/phoenix/run_experiment.py --dry-run
uv run python eval/phoenix/agent.py --check-mcp
uv run python scripts/verify_phoenix_harness.py
```

The last two need permission to create local subprocess pipes. They make no model
API calls. The scripted verifier is explicitly marked verification_only and cannot
pass the benchmark evidence gate. Ordinary tests disable automatic Phoenix and
LangSmith pytest plugins, block unmocked HTTP, and keep temporary data in .pytest_tmp.

The dataset builder uses only the fixed snapshot; it does not download live data.
Changing the snapshot or references requires rebuilding and reviewing XML/CSV.
Validation requires the complete XML case inventory; a custom CSV cannot silently
drop difficult questions. Git attributes preserve snapshot bytes across Windows
and Linux. Do not rewrite the manifest's newlines to repair a hash mismatch.
The older 25-case ../run_eval.py tool suite is preserved, not passed off as an
agent evaluation.

## Run Phoenix, upload the dataset, and evaluate

Start a local loopback-only server with storage in the ignored root .phoenix:

```shell
uv run python eval/phoenix/serve.py
```

Open http://localhost:6006 yourself to review results. HTTP OTLP is available at
http://localhost:6006/v1/traces and gRPC at port 4317. The server helper avoids
public binding, disables its built-in agent assistant/telemetry, and uses the
installed Phoenix CLI. Stop it with Ctrl+C when finished.

After root .env has real model settings, run from eval/phoenix/ as in the skill:

```shell
uv run create_dataset.py --dataset-name respiratory-eval-0
uv run run_experiment.py --dataset-name respiratory-eval-0 --system-prompt-version v2 --repetitions 1
```

Capture the dataset_version_id printed by creation. Pin it for comparisons:

```shell
uv run run_experiment.py --dataset-name respiratory-eval-0 --dataset-version-id YOUR_VERSION_ID --system-prompt-version v1 --experiment-description "Baseline prompt" --repetitions 3
uv run run_experiment.py --dataset-name respiratory-eval-0 --dataset-version-id YOUR_VERSION_ID --system-prompt-version v2 --experiment-description "Public health constraints" --repetitions 3
```

Both prompt variants use the same frozen data and expected answers. Keep judge
model fixed across experiments. Commands also accept --project-name,
--phoenix-endpoint and --experiment-description. create_dataset.py additionally
supports --phoenix-name and --csv-path. --no-validate skips only remote dataset
comparison; it never bypasses local snapshot checks or configuration validation.

Review failing responses and per-question traces in Phoenix. Redacted configuration
metadata and outputs are written under ignored eval/phoenix/runs; API keys are not
included. The agent task receives only query and case_id, never the reference
answers. Case IDs select isolated outage scenarios; they do not preload answers.

## Metrics and public health checks

| Metric | Definition |
| --- | --- |
| answer_correctness | Semantic judge compares answer AND explanation with independent facts; accepts harmless formatting, rounding and valid unit conversions |
| answer_scope | Descriptive surveillance is in scope; appropriate refusal of individual predictions is also in scope |
| public_health | Semantic grounding/caveat judge, with deterministic evidence gates |
| tool_action_coverage | Fraction of required analytical actions completed, accepting valid alternative tools; not call-level precision |
| argument_validity | Completed calls preserving the fixed cutoff without unexpected input/tool errors; intended typo/outage errors are allowed |
| answer_anchor | Requested first-line scalar format; supplementary formatting metric, not a substitute for semantic correctness |
| evidence_integrity | Snapshot identity and overlapping independent source/value/date/geography/unit checks; verification-only outputs are rejected |
| numeric_support | Numeric-token support with ordinary rounding/scaling; semantic attribution is still judged separately |

The public health judge checks national versus state geography; source-assigned
versus derived levels; dates and native units; rank/peak denominators; missing,
partial and unavailable states; scan totals versus displayed rows; unsupported
forecasts; and the distinction between observation cutoffs and publication
vintages. It treats retrieved text and answers as evidence, not grading instructions.
A number appearing somewhere in a tool result is not sufficient semantic grounding.

The independent rule calculations validate implementation, not the epidemiologic
validity of heuristic thresholds. Human review of methods and representative
answers is still needed. Do not claim predictive performance from these tests.

## Verification status

Credential-free checks passed: dataset XML/CSV/sidecar/hash validation; actual
LangChain graph with two frozen stdio calls; isolated complete-source outage;
real ChatOpenAI/Phoenix judge HTTP contracts under mocks; ClassificationEvaluator
and Score integration; local Phoenix dataset upload/version readback and experiment
storage for 15 verification tasks; and OTLP export/readback of 20 scripted spans.
The temporary server was stopped. Storage experiments use a verification-only
label and contain no model scores. Real agent/judge scores await configured model
access. Exact test totals and commands are in docs/VERIFICATION.md at the repo root.
