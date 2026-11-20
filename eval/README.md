# Evaluations

This directory contains the evaluation harness, frozen data snapshot, and results
for the Respiratory Season Situational Awareness MCP Server.

## Frozen eval snapshot

**as_of date: `2026-10-31`**

This is the fixed reference date for all deterministic evaluation cases. It was
chosen as 2 weeks prior to the minimum latest-available date across all three data
sources (all sources had data through `2026-11-14` as of Build 0.3 on 2026-11-20).
Two weeks back ensures data has finalized across all reporting systems.

Frozen data slices in `eval/snapshot/`:

| File | Source | Jurisdiction |
|---|---|---|
| `nhsn_ga.json` | NHSN `vdzy-6i9v` | Georgia (GA) — 160 weeks up to 2026-10-31 |
| `nhsn_ca.json` | NHSN `vdzy-6i9v` | California (CA) — 160 weeks |
| `nhsn_oh.json` | NHSN `vdzy-6i9v` | Ohio (OH) — 160 weeks |
| `nhsn_tx.json` | NHSN `vdzy-6i9v` | Texas (TX) — 160 weeks |
| `nhsn_usa.json` | NHSN `vdzy-6i9v` | USA (national) — 160 weeks |
| `nhsn_scan_national.json` | NHSN `vdzy-6i9v` | All jurisdictions — 13 weeks up to 2026-10-31 |
| `nwss_georgia.json` | NWSS `atcp-73re` | Georgia sites — up to 2026-10-31 |
| `nwss_california.json` | NWSS `atcp-73re` | California sites |
| `nwss_ohio.json` | NWSS `atcp-73re` | Ohio sites |
| `nwss_texas.json` | NWSS `atcp-73re` | Texas sites |
| `nrevss_national.json` | NREVSS `seuz-s2cv` | National positivity — up to 2026-10-31 |

## Expected layout once built (Phase 4)

```
eval/
  cases.yaml              ← 25 pinned evaluation cases (5 per category)
  ground_truth.py         ← independent ground truth from eval/snapshot/
  run_eval.py             ← runs cases against wxO agent, saves transcripts
  RESULTS.md              ← scored results (before/after improvement pass)
  README.md               ← this file
  snapshot/               ← frozen data slice (above)
  transcripts/            ← per-case JSON transcripts from run_eval.py
```

## Evaluation categories (25 cases)

- **A. Direct lookup (5)** — single jurisdiction, single pathogen, current week
- **B. Trend (5)** — is it increasing/decreasing? over what window?
- **C. Season comparison (5)** — how does current compare to prior seasons?
- **D. Multi-step/synthesis (5)** — multi-turn, cross-signal questions
- **E. Robustness (5)** — bad input, missing data, edge cases

## Scoring metrics

- Tool selection % (correct tool chosen)
- Argument % (correct parameters passed)
- Answer correctness % (matches ground truth within tolerance)
- Grounding % (every number in final answer appears in tool output)
- Error handling % (structured error returned for bad inputs)
- Latency (median / p95 seconds)
