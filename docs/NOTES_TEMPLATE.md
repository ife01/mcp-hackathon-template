# Template Convention Notes

Reference notes captured during Build 0.2. Covers everything the domain code needs
to know about the template before touching it.

---

## 1. Tool / Prompt / Resource registration pattern

All three primitives follow the **one-file-per-item + aggregator** pattern:

```
src/example_server/
  tools/
    __init__.py          ← register_tools(mcp): calls each module's register(mcp)
    example_tool.py      ← exposes register(mcp); contains one @mcp.tool function
  prompts/
    __init__.py          ← register_prompts(mcp)
    example.py           ← exposes register(mcp); contains one @mcp.prompt function
  resources/
    __init__.py          ← register_resources(mcp)
    example.py           ← exposes register(mcp); contains one @mcp.resource function
```

**To add a new tool/prompt/resource:**
1. Create `src/<pkg>/tools/my_tool.py` with a `register(mcp: FastMCP) -> None` function.
2. Import and call `my_tool.register(mcp)` in `tools/__init__.py`.

The `@mcp.tool` decorator accepts a `name=` and an `annotations=` dict
(`readOnlyHint`, `destructiveHint`, `idempotentHint`, `openWorldHint`, `title`).
The function's docstring is what the LLM reads to decide when to call the tool — keep
it precise and ≤120 words.

Prompts return a `str` (user message) or `list[dict]` (multi-turn starter).
Resources use a URI scheme: static `@mcp.resource("resp://path")` or parameterized
`@mcp.resource("resp://path/{param}")`.

---

## 2. Package layout mapping (template → resp_mcp)

| Template path | Our path | Notes |
|---|---|---|
| `src/example_server/` | `src/resp_mcp/` | Rename folder + update pyproject.toml |
| `src/example_server/app.py` | `src/resp_mcp/server.py` | Keep thin; build FastMCP instance here |
| `src/example_server/config.py` | `src/resp_mcp/config.py` | Add SOCRATA_APP_TOKEN, CACHE_TTL, etc. |
| `src/example_server/models.py` | `src/resp_mcp/models/` | Split into common.py + tool_io.py |
| `src/example_server/utils.py` | `src/resp_mcp/clients/socrata.py` | Replace generic fetch_json with hardened Socrata client |
| `src/example_server/routes.py` | `src/resp_mcp/routes.py` | Keep /health + /version unchanged |
| `src/example_server/tools/` | `src/resp_mcp/tools/` | Same pattern; 4 tool files |
| `src/example_server/prompts/` | `src/resp_mcp/prompts/` | Same pattern; 2 prompt files |
| `src/example_server/resources/` | `src/resp_mcp/resources/` | Same pattern; 3 resource files |
| `main.py` | `main.py` | Update import from `resp_mcp.server` |
| `tests/` | `tests/unit/` `tests/contract/` `tests/live/` | Expand layout as per plan |

**pyproject.toml changes needed (Build 0.4):**
- `[project].name` → `respiratory-mcp-server`
- `[project.scripts]` entry → `resp-mcp-server = "resp_mcp.server:main"`
- `[tool.hatch.build.targets.wheel].packages` → `["src/resp_mcp"]`

---

## 3. Transport selection

| Scenario | How transport is chosen |
|---|---|
| Local dev (Claude Desktop, Bob, MCP Inspector) | `mcp_transport=stdio` (default) → `mcp.run(transport="stdio")` |
| Explicit local HTTP test | `MCP_TRANSPORT=streamable-http` in env → HTTP on `MCP_HOST:MCP_PORT` (default `0.0.0.0:8000`) |
| Cloud (IBM Code Engine, cloud.gov) | Platform injects `PORT` or `DATABRICKS_APP_PORT` → `app.py` auto-selects HTTP on that port |
| wxO local MCP toolkit (stdio inside Orchestrate) | `deploy/ibm/local-mcp-toolkit/server.py` calls `mcp.run(transport="stdio")` |

**For this project:** wxO remote toolkit (streamable-HTTP on Code Engine) is preferred
for a production-like demo. Local MCP toolkit (stdio) is the fallback if Code Engine
credentials are unavailable during the hackathon. Decision logged in DECISIONS.md.

The MCP endpoint is at `/mcp`; health check is at `/health` (required by cloud hosts).

---

## 4. Eval README expectations

`eval/README.md` describes a **stub** — the template ships no harness.

Expected final layout (to be built in Phase 4):
```
eval/
  cases.yaml              ← 25 pinned evaluation cases (5 per category)
  ground_truth.py         ← independent ground truth computed from eval/snapshot/
  run_eval.py             ← runs cases against wxO agent, saves transcripts
  RESULTS.md              ← scored results (before/after improvement pass)
  README.md               ← existing stub; update with as_of date + eval summary
  snapshot/               ← frozen data slice from Build 0.3
  transcripts/            ← per-case JSON transcripts from run_eval.py
```

The template references an Arize Phoenix / LangChain harness pattern
(`eval/phoenix/`). Our plan uses a custom `run_eval.py` against the wxO agent
evaluation API (or manual transcripts as fallback). We do not use Phoenix unless
the wxO batch eval API is unavailable.

---

## 5. Deploy targets and submission requirements

### IBM watsonx Orchestrate (primary)
Three kits in `deploy/ibm/` — lowest to highest overhead:

1. **`local-mcp-toolkit/`** (stdio inside Orchestrate)
   - Run `bash deploy/ibm/local-mcp-toolkit/register-toolkit.sh`
   - Needs: ADK (`pip install ibm-watsonx-orchestrate`), wxO instance URL + API key
   - Script stages a flattened `_stage/` dir (no `src/` prefix) so the package is
     importable at runtime; avoids 413 errors from uploading the whole repo.
   - `toolkit.yaml` controls name, description, command, and tool filter (`"*"` = all).

2. **`code-engine-git-build/`** (streamable-HTTP, builds from Git)
   - Needs: IBM Cloud CLI + code-engine plugin, IBM Container Registry authority

3. **`prebuilt-image/`** (streamable-HTTP, deploys prebuilt image)
   - Needs: Code Engine project; no ICR access required

**Our plan choice:** start with `local-mcp-toolkit/` for Build 0.1 smoke test;
target `prebuilt-image/` or `code-engine-git-build/` for the Phase 5 container demo.

### cloud.gov (bonus)
`manifest.yaml` at repo root. Deploy with `cf push`. Buildpack sets `PYTHONPATH=src`.

### Submission
- `server.json` — MCP registry metadata (name, description, repo URL, remote URL)
- `manifest.yaml` — cloud.gov manifest
- `deploy/ibm/local-mcp-toolkit/toolkit.yaml` — wxO toolkit import config
- Git tag `v1.0-hackathon` required (Build 5.5)

---

## 6. Security posture (template baseline)

- No authentication on the MCP endpoint by default (public-data hackathon posture).
- `utils.py` / `fetch_json` enforces relative path validation, blocks SSRF via
  host/IP checks, disables redirects by default.
- Secrets go in `.env` (git-ignored); document vars in `.env.example`.
- `uv.lock` pins all transitive deps.

Our server adds: outbound domain allowlist, SoQL enum-only construction, input
length/character bounds, single-flight cache (see Build 1.1).
