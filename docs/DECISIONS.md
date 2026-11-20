# Decision Log

All deviations from the build plan are recorded here with a date and rationale.

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

## 2026-11-20 — Build 0.3: NHSN counts vs. rates decision

**Decision:** Use **published rates and official levels** as the primary signal:
- `totalconfflunewadmper100k` / `totalconfc19newadmper100k` / `totalconfrsvnewadmper100k`
- `totalconfflunewadmper100klevel` / `totalconfc19newadmper100klevel` / `totalconfrsvnewadmper100klevel`

Raw counts (`totalconfflunewadm` etc.) are retained in the data but used only for
the small-number guard in trend analytics (< 10 admissions average).

---

## 2026-11-20 — Build 0.3: Eval as_of date set to 2026-10-31

**Decision:** Eval snapshot frozen at **`as_of=2026-10-31`** — 2 weeks prior to
the minimum latest-available date across all three sources (all had data through
2026-11-14 as of reconnaissance on 2026-11-20). Two-week buffer ensures data
finalization across all reporting systems.

