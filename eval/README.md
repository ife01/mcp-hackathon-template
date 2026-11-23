# Evaluation

## Evaluation layers

1. Offline tool baseline: deterministic calls against frozen HTTP replay, scored
   using independent raw-data calculations in ground_truth.py. It exercises input
   validation, adapters, pagination, analytics, and output contracts. No live
   fallback or wxO/model credentials are used.
2. Phoenix + LangChain agent evaluation: implemented in [phoenix/README.md](phoenix/README.md)
   following the repository mcp-eval skill. It uses a real agent over frozen stdio
   MCP, independent hidden references, semantic judges, and public health gates.
   Its 10 multi-call benchmark questions plus five supplemental cases are separate
   from the original 25-case tool suite. The [first real-model run](phoenix/RESULTS_2026-11-23.md) completed all 15 cases.
3. Manual wxO evaluation: the user supplied two conversation records from the
   actual wxO workflow. The [manual review](transcripts/wxo/MANUAL_REVIEW_2026-11-23.md)
   preserves both files and documents failures, improvements and evidence limits.

The [wxO runtime verification](../docs/WXO_RUNTIME_VERIFICATION_2026-11-23.md) adds complete tool traces for the November 23 replays and retests.
It distinguishes original-session replay, fresh questions and remaining error-message fidelity limits.

The later [scan-fix verification](../docs/WXO_SCAN_FIX_2026-11-23.md) checks exact returned membership and application heuristic attribution on wxO v3.
It preserves actual calls and responses separately from the earlier scores.

The [successful manual v3 retest](transcripts/wxo/2026-11-23-manual-success/REVIEW.md) records six targeted visible-answer passes in a shared conversation.
It does not include new raw tool traces or change the separate Phoenix scores.

These layers complement each other. Phoenix results do not certify wxO answers.
The baseline is deliberately not reported as an agent success rate. The recorded
replay timings are not live cold/warm latency measurements.

## Run the baseline

From the repository root after `uv sync --frozen --group dev`:

```shell
uv run python eval/run_eval.py
```

The runner verifies snapshot hashes first, replays recorded data at the HTTP
boundary (including real SoQL construction and pagination), clears client cache
between cases, and writes JSON traces under eval/transcripts/tools. Failures
produce a nonzero exit. Expected-error cases must match their error category.
A-E contain five cases each: lookup, trend, season comparison, synthesis, and
robustness. Numeric comparisons use 1e-8 absolute/relative tolerance.

`ground_truth.py` imports no production code. It independently parses the raw
snapshot, calculates trends and available prior-week ranks, and checks actual
observation geography and dates. Complete-season peak behavior, missing data,
site deduplication, outages, and date boundaries also have explicit regression
examples in tests/unit/test_public_health_regressions.py. An epidemiologist should
review the method choices and reference outputs before final agent scoring.

## Frozen data

The current baseline uses **snapshot_v2**, cutoff **2026-10-31**, captured on
2026-11-22 from public CDC endpoints. capture_manifest.json records metadata,
requested dates, actual coverage, and SHA-256 hashes. Raw JSON is losslessly gzip
compressed, with each compressed file below 2 MB.

| Source | Actual captured coverage |
| --- | --- |
| NHSN states/USA/PR | 29 weeks, 2026-04-18 through 2026-10-31 |
| NHSN national scan | 9 weeks, 2026-09-05 through 2026-10-31 |
| NWSS GA/CA/OH/TX | 175 distinct weeks per pathogen, 2023-07-01 through 2026-10-31 |
| National NREVSS | 175 distinct weeks per pathogen, same interval |

Coverage counts do not prove every value or site is available. NHSN cannot support
prior-season comparisons in this snapshot; abstention is a required correct
outcome. The source was queried for history from 2023-07-01, so 29 weeks is the
history returned by this endpoint, not a fabricated 160-week history.

The original snapshot directory is retained as legacy evidence, with its actual
coverage recorded in snapshot/coverage_manifest.json. Its earlier 160-week and
13-week descriptions were inaccurate. It is not used by the current runner.

A cutoff on observation dates is not an as-published vintage. Later revisions can
appear in captured history. Waiting two weeks does not establish finalization.

## Audit or capture a new version

```shell
uv run python scripts/audit_snapshot.py eval/snapshot_v2
uv run python scripts/capture_snapshot.py --as-of 2026-10-31 --output eval/snapshot_v3
```

Capture requires live CDC access, uses full pagination and bounded date chunks,
checks required metadata fields, and refuses to overwrite an existing directory.
A failed capture leaves complete=false. Reaching a row cap fails rather than
silently accepting partial data. Change cases.yaml only after inspecting a new
manifest and rechecking the expected values. No captured dataset is assumed final.

## Optional wxO platform prerequisites and scoring

Use docs/WXO_AGENT_SETUP.md. The remaining inputs are the sandbox service URL,
agent ID, authentication type, and a key placed in a local ignored .env or the
credential mechanism provided by the service. Never put a key in cases or traces.
A sandbox MCP connection reachable by wxO must already be registered.

Run each prompt in a new conversation, preserving the fixed cutoff. Prefer three
runs per case; report the denominator if constrained to one. Record agent/model
version, instructions, server commit, snapshot manifest hash, expected versus
observed calls, answer text, and cold/warm median/p95 latency. For deterministic
agent scoring, connect the agent to a sandbox server backed by the same frozen
snapshot. Live-data scoring is a separate freshness test.

Hard failure examples: national data labeled as state data; derived wastewater
levels attributed to CDC; a record claim without historical data; an outage
summarized as no rising activity; or an unsupported forecast. Do not use a number
appearing somewhere in a tool response as sufficient grounding: it must match the
claimed geography, unit, date, and signal.
