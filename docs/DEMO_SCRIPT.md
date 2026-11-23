# Demo script — Respiratory Season Situational Awareness MCP Server

**Venue:** GSA "Model Context Protocol Server and SI Agent Government Hackathon"
**Platform:** IBM watsonx Orchestrate (local MCP toolkit, stdio transport)
**Target duration:** ~4 minutes
**Observation cutoff:** `2026-10-31`. The normal wxO toolkit uses live CDC data;
values may change after revisions even with this cutoff. Frozen reference values
below are illustrations, not guaranteed live responses.

---

## Pre-flight checklist (do before the demo)

- [ ] wxO agent open in browser, `respiratory_mcp_local_v3` toolkit attached
- [ ] Active RSA policy loaded (from `docs/WXO_AGENT_POLICY.txt`)
- [ ] New chat session started — cache pre-warmed with one test call
- [ ] Notes open: GA 1.76/100k Low ↑, CA 3.01/100k Moderate ↑, FL leads R4 at 5.53
- [ ] `as_of="2026-10-31"` instruction ready to paste as the opening message

---

## Beat 1 — Set the scene (0:00–0:20)

**Say:**
> "It's Friday afternoon. You're a state epidemiologist preparing a respiratory situation report. This wxO agent calls our MCP server for public CDC data. We'll use an October 31 observation cutoff. Live revisions can still change the values; our separate frozen replay is the reproducible benchmark."

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
- Wastewater: report the returned value, trend and actual observation date; describe the returned concordance pattern rather than assuming one
- Every number cites dataset ID (`vdzy-6i9v`, `seuz-s2cv`, `atcp-73re`) + week-ending date

> "Concordance is a descriptive combination of available signals, with geography and dates checked. It is not a forecast. For state briefings, national positivity is excluded from local concordance."

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
- No prior-season NHSN rank when the capture has insufficient comparison history; do not claim that the dataset itself starts at the reporting transition

> "The agent correctly says positivity is national context, not a Georgia number. That's a critical distinction the server enforces — it never substitutes a national estimate for a state value."

---

## Beat 4 — Historical comparison (1:35–2:10)

Before using this beat, verify the returned peak value and season against the actual tool payload.
A supplemental wxO test mislabeled a national positivity peak; that explanation defect remains unresolved.
The latest successful six-question manual retest did not cover historical peak comparisons.
If the peak explanation is wrong, disclose it and use only the verified returned prior-week values.

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

> "This value is about 37% of the highest complete prior-season peak in the reference capture. That does not predict this season's eventual peak. Rank 1 means highest against three available prior-week values, not an all-time record."

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
- **No missing Region 4 states in the frozen reference**: 8 requested, 8 assessed, 0 unavailable. Arkansas is in Region 6 and must not be listed as missing from Region 4.
- Total rising (8) distinguished from displayed count

> "The tool reports assessment and missingness counts within the requested region. Here all eight Region 4 states were assessed. In other cases, missing data must not be treated as stable activity."

---

## Beat 6 — Error handling (2:40–3:05)

**Say:**
> "Let's stress-test the scope boundaries."

**Type:**
```
Rank states by rising flu test positivity.
```

**Expected:** Agent explains the unsupported scope, either directly or after the tool returns its scope error — "NREVSS test positivity is national-only; state-level ranking is not supported."

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
> "To summarize: one MCP server, three CDC datasets, four tools. It runs locally over stdio or as a container over streamable HTTP. 386 automated tests, 25 frozen tool cases with 155 passing assertions, captured wxO checks and a subsequent six-question manual answer retest. The separate Phoenix benchmark has its own results and limitations. The server is read-only, uses only public unauthenticated CDC endpoints, enforces an outbound domain allowlist, and builds SoQL from validated enums only — no raw user strings reach the query layer.

> It's a prototype — not an official CDC product or a clinical system. It demonstrates a source-cited surveillance workflow; analyst time savings have not been measured."

---

## Fallback values (if live CDC data differs from frozen reference)

Live data may differ even with `as_of="2026-10-31"`. These are frozen reference
values only. Label them as recorded examples; never substitute them for the
actual tool response during a live demonstration:

| Jurisdiction | Signal | Value | Level | Trend |
|---|---|---|---|---|
| GA | Flu hospital admissions | 1.76/100k | Low | Increasing +89% |
| CA | Flu hospital admissions | 3.01/100k | Moderate | Increasing +84% |
| OH | Flu hospital admissions | 1.51/100k | Low | Increasing +81% |
| TX | Flu hospital admissions | 2.72/100k | Low | Increasing +48% |
| USA | Flu test positivity | 10.1% | — | Increasing +65% |
| CA | Flu wastewater | 6.55 wval | — | Increasing; rank 1/3; 37% of peak |
| FL | Flu hospital admissions | 5.53/100k | Moderate | Increasing (R4 #1) |
