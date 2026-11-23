# Demo script — Respiratory Season Situational Awareness MCP Server

**Venue:** GSA "Model Context Protocol Server and SI Agent Government Hackathon"
**Platform:** IBM watsonx Orchestrate (local MCP toolkit, stdio transport)
**Target duration:** ~4 minutes
**as_of pin:** `2026-10-31` (frozen snapshot — ensures reproducible values)

---

## Pre-flight checklist (do before the demo)

- [ ] wxO agent open in browser, `respiratory_mcp_local` toolkit attached
- [ ] System prompt v2 loaded (from `eval/phoenix/prompts/system_prompt_v2.txt`)
- [ ] New chat session started — cache pre-warmed with one test call
- [ ] Notes open: GA 1.76/100k Low ↑, CA 3.01/100k Moderate ↑, FL leads R4 at 5.53
- [ ] `as_of="2026-10-31"` instruction ready to paste as the opening message

---

## Beat 1 — Set the scene (0:00–0:20)

**Say:**
> "It's Friday afternoon. You're a state epidemiologist and you need to write this week's respiratory situation report. You open watsonx Orchestrate, which is connected to our MCP server pulling live public CDC data. Let's start by pinning to the week ending October 31st so our demo values are reproducible."

**Type in wxO chat:**
```
For all tool calls in this session, use as_of="2026-10-31" unless I specify otherwise.
```

---

## Beat 2 — National baseline snapshot (0:20–0:55)

**Say:**
> "First, what's happening nationally? The server hits three CDC datasets in parallel — NHSN hospital admissions, NWSS wastewater, and NREVSS test positivity — and returns a single structured snapshot with provenance attached."

**Type:**
```
Give me a national flu overview for the week ending October 31, 2026.
```

**Expected tool call:** `get_respiratory_snapshot(jurisdiction="USA", pathogens=["influenza"], as_of="2026-10-31")`

**Point out in the response:**
- Hospital admissions: 2.49/100k, CDC level **Low**, trend **Increasing**
- Test positivity: **10.1%** nationally, also increasing
- Wastewater: **stable** at national level — `early_warning` concordance pattern
- Every number cites dataset ID (`vdzy-6i9v`, `seuz-s2cv`, `atcp-73re`) + week-ending date

> "Notice the server flags an `early_warning` pattern — two signals rising, wastewater stable. It doesn't call that a forecast. It's a descriptive pattern, and the caveat is right there in the output."

---

## Beat 3 — State drill-down with trend (0:55–1:35)

**Say:**
> "Now let's drill into Georgia. I want the full picture — signals, trend, and the supporting data series."

**Type:**
```
Brief me on flu in Georgia through October 31, 2026. Include local signals, national context, and hospital trend caveats.
```

**Expected tool calls:**
1. `get_respiratory_snapshot(jurisdiction="GA", pathogens=["influenza"], as_of="2026-10-31")`
2. `assess_trend(jurisdiction="GA", pathogen="influenza", signal="hospital_admissions", as_of="2026-10-31")`

**Point out in the response:**
- GA hospital admissions: **1.76/100k**, CDC level **Low**, trend **Increasing +89%**
- Wastewater: **1.70 wval**, derived level Very Low, trend **Stable**
- Test positivity: **10.1% — national only**, correctly scoped as USA context, not a GA estimate
- Trend series shows: 0.73 → 0.70 → 0.94 → **1.76** — four consecutive weeks
- No prior-season NHSN rank — correctly withheld because NHSN history only starts Nov 2024

> "The agent correctly says positivity is national context, not a Georgia number. That's a critical distinction the server enforces — it never substitutes a national estimate for a state value."

---

## Beat 4 — Historical comparison (1:35–2:10)

**Say:**
> "How does this compare to prior flu seasons? California has richer wastewater history, so let's use that."

**Type:**
```
Compare California flu wastewater activity to the three prior seasons through October 31, 2026.
```

**Expected tool call:** `compare_to_prior_seasons(jurisdiction="CA", pathogen="influenza", signal="wastewater", prior_seasons=3, as_of="2026-10-31")`

**Point out in the response:**
- Current (2026-27, week 17): **6.55 wval**
- Rank vs prior: **#1** — highest of the three comparable weeks
- 37% of the highest prior-season peak (17.5 wval in 2024-25)
- Prior peaks clearly shown: 2023-24: 15.96, 2024-25: 17.51, 2025-26: 11.09
- Caveat: wastewater is server-derived, not CDC official; influenza A only

> "Early in the season at 37% of peak — it's rising but not at peak levels yet. Rank 1 means highest of these three comparisons — not an all-time record. The denominator and the exclusions are always visible."

---

## Beat 5 — Regional hotspot scan (2:10–2:40)

**Say:**
> "Now the scan tool — which states in HHS Region 4 are rising? This fetches all states in one Socrata query and groups in memory."

**Type:**
```
Which HHS Region 4 states had rising flu admissions through October 31, 2026? Report missing data and the total before limiting.
```

**Expected tool call:** `find_jurisdictions_with_rising_activity(pathogen="influenza", signal="hospital_admissions", hhs_region=4, as_of="2026-10-31")`

**Point out in the response:**
- **8/8 Region 4 states rising** — FL leads at 5.53/100k Moderate
- Full table: FL → AL → MS → KY → TN → SC → NC → GA
- AR noted as **missing** — the agent says "missing, not evidence of stability"
- Total rising (8) distinguished from displayed count

> "The server never equates a missing data point with no activity. That's a public health safety rule baked into the tool output."

---

## Beat 6 — Error handling (2:40–3:05)

**Say:**
> "Let's stress-test the scope boundaries."

**Type:**
```
Rank states by rising flu test positivity.
```

**Expected:** Agent refuses without calling a tool — "NREVSS test positivity is national-only; state-level ranking is not supported."

Then type:
```
Give me a flu forecast for Georgia next week.
```

**Expected:** Agent declines — "These tools provide retrospective surveillance summaries. Forecasting is outside their scope."

> "The agent knows what it can't do. No invented numbers, no hallucinated forecasts. The tool descriptions are precise enough that wxO picks the right tool — or correctly refuses — without any extra scaffolding."

---

## Beat 7 — Caveats and provenance (3:05–3:35)

**Say:**
> "Every output has provenance. Let's look at what that means for a real situation report."

**Point to any tool response and highlight:**
- `dataset_id` + `dataset_name` + URL on every signal
- `latest_week_ending` — the actual observation date, not today
- `official_level` only on NHSN — never on wastewater
- `derived_level` on NWSS — labeled server-derived
- Trend labeled as "4-week heuristic, not an official CDC classification"
- `as_of` caveat: "filters observation weeks in data retrieved now; does not reconstruct what was published at that historical time"

> "An epidemiologist writing a situation report can cite exactly where every number came from and what its limitations are — without having to look any of that up themselves."

---

## Beat 8 — Wrap-up (3:35–4:00)

**Say:**
> "To summarize: one MCP server, three CDC datasets, four tools. It runs locally over stdio or as a container over streamable HTTP. 355 automated tests, 25-case deterministic evaluation at 100%, two live wxO agent runs. The server is read-only, uses only public unauthenticated CDC endpoints, enforces an outbound domain allowlist, and builds SoQL from validated enums only — no raw user strings reach the query layer.

> It's a prototype — not an official CDC product, not a clinical system. But it demonstrates what a well-scoped, well-caveated MCP server can do for a public health analyst who needs to write a situation report in 20 minutes instead of two hours."

---

## Fallback values (if live CDC data differs from frozen reference)

If you run without `as_of="2026-10-31"` and live data differs, these are the
frozen reference values to cite:

| Jurisdiction | Signal | Value | Level | Trend |
|---|---|---|---|---|
| GA | Flu hospital admissions | 1.76/100k | Low | Increasing +89% |
| CA | Flu hospital admissions | 3.01/100k | Moderate | Increasing +84% |
| OH | Flu hospital admissions | 1.51/100k | Low | Increasing +81% |
| TX | Flu hospital admissions | 2.72/100k | Low | Increasing +48% |
| USA | Flu test positivity | 10.1% | — | Increasing +65% |
| CA | Flu wastewater | 6.55 wval | — | Increasing; rank 1/3; 37% of peak |
| FL | Flu hospital admissions | 5.53/100k | Moderate | Increasing (R4 #1) |
