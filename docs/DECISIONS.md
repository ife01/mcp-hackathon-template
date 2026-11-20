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
