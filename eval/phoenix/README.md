# Phoenix Evaluation Harness — Respiratory MCP Server

## Overview

This directory contains the LLM-as-judge evaluation harness for the Respiratory
Season Situational Awareness MCP Server.

**Benchmark:** 15 frozen-data questions (10 multi-call + 5 public health / robustness)
**as_of date:** `2026-10-31`
**Snapshot:** `eval/snapshot/` — 11 frozen CDC fixture files

## Directory layout

```
eval/phoenix/
├── agent.py               # RespMcpAgent — LangChain + MCP + Phoenix traces
├── create_dataset.py      # CLI: upload CSV dataset to Phoenix
├── run_experiment.py      # CLI: run an experiment (agent + judges)
├── serve.py               # Start local Phoenix server
├── datasets.yaml          # Dataset registry
├── judges/
│   ├── __init__.py
│   ├── correctness_judge.py   # match_expected_response (correct/incorrect)
│   └── relevance_judge.py     # check_answer_scope (within_scope/out_of_scope)
├── prompts/
│   ├── system_prompt_v1.txt   # Basic domain analyst + data rules
│   └── system_prompt_v2.txt   # + explicit scope boundaries
└── datasets/
    └── respiratory-eval-0/
        └── examples/
            └── respiratory-eval-0.csv   # 15 benchmark questions
```

## Setup

```bash
# Install eval dependencies
uv sync --group dev

# Copy .env.example → .env and fill in model credentials
cp .env.example .env
```

Required `.env` variables:

| Variable | Purpose |
|---|---|
| `USAI_BASE_URL` | Model API base URL (e.g. `https://your-gateway.example.com`) |
| `USAI_API_KEY` | Bearer API key for the model gateway |
| `AGENT_MODEL` | Model ID for the agent-under-test |
| `JUDGE_MODEL` | Model ID for LLM-as-judge (keep distinct from agent) |
| `JUDGE_BASE_URL` | (Optional) separate judge base URL |
| `JUDGE_API_KEY` | (Optional) separate judge API key |

## Deterministic baseline (no model needed)

```bash
uv run python eval/run_eval.py
```

Runs 25+ grounding, schema, and error-handling checks directly against the MCP
server using frozen snapshot data. No model credentials required.

## Credential-free preflight

```bash
# Validate CSV structure (no Phoenix, no model)
uv run python eval/phoenix/create_dataset.py --dataset-name respiratory-eval-0 --dry-run

# Validate imports and env vars
uv run python eval/phoenix/run_experiment.py --dry-run

# Verify MCP server starts and tools load (no model)
uv run python eval/phoenix/agent.py --check-mcp
```

## Running the full evaluation

### Step 1: Start Phoenix (separate terminal)

```bash
uv run python eval/phoenix/serve.py
# UI at http://localhost:6006
```

### Step 2: Upload the dataset (one-time)

```bash
uv run python eval/phoenix/create_dataset.py --dataset-name respiratory-eval-0
# Record the returned dataset version ID
```

### Step 3: Run one v2 experiment first

```bash
uv run python eval/phoenix/run_experiment.py \
    --dataset-name respiratory-eval-0 \
    --dataset-version-id <VERSION_ID> \
    --system-prompt-version v2 \
    --repetitions 1
```

### Step 4: Review in Phoenix UI

Open http://localhost:6006 — inspect per-question traces, judge verdicts, and
tool call sequences before expanding to multi-repetition runs.

### Step 5: v1/v2 comparison (3 repetitions each — agree with human first)

```bash
uv run python eval/phoenix/run_experiment.py \
    --dataset-name respiratory-eval-0 \
    --dataset-version-id <VERSION_ID> \
    --system-prompt-version v1 \
    --repetitions 3

uv run python eval/phoenix/run_experiment.py \
    --dataset-name respiratory-eval-0 \
    --dataset-version-id <VERSION_ID> \
    --system-prompt-version v2 \
    --repetitions 3
```

## Benchmark question categories

| Category | Count | Description |
|---|---|---|
| A: Direct lookup | 4 | Single jurisdiction, single signal, current week |
| B: Trend | 5 | Is it increasing/stable/decreasing? |
| C: Season comparison | 1 | Current vs prior seasons |
| D: Multi-signal synthesis | 1 | All three signals for one jurisdiction |
| E1: National scan | 1 | Which states are rising? |
| PH: Public health scope | 3 | NREVSS geography, WW classification, temporal gap |
| Robustness | 2 | Bad input error, no-forecast scope boundary |

## Public health evaluation checks (critical)

The judges are explicitly instructed to mark **INCORRECT** if:

- National NREVSS positivity is attributed to a specific state
- Server-computed NWSS site aggregates are described as official CDC classifications
- Numbers don't match the source, pathogen, geography, units, or observation date
- Missing/unavailable data is implied to mean zero or stable activity
- Scan totals (n_jurisdictions_scanned) differ from displayed rising rows but are conflated
- Trend descriptions become forecasts or individual medical predictions
- Observation cutoffs are presented as historical publication vintages

## Scoring

Each experiment reports:
- `match_expected_response`: correct / incorrect per question
- `check_answer_scope`: within_scope / out_of_scope per question

Summary metrics in `eval/RESULTS.md` after the eval run.
