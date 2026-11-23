# Security and data handling

This repository is a read-only hackathon prototype using public aggregate CDC
data. It does not request line-level records, PII, PHI, or internal CDC access.
No production authorization or operational readiness is implied.

---

## Data posture

**Read-only public aggregate data only.** All three CDC datasets (`vdzy-6i9v`
NHSN, `atcp-73re` NWSS, `seuz-s2cv` NREVSS) are publicly accessible without
authentication on `data.cdc.gov`. The server never writes, updates, deletes, or
submits anything.

**No PII or PHI.** All data are jurisdiction- or site-level aggregates published
by CDC. No patient-level, individual-level, or facility-level records are requested
or returned. The server enforces `$limit` caps and does not page beyond 50,000
rows; any query that hits the cap returns a structured error rather than partial
data.

---

## Outbound request controls

### Enforced domain allowlist

Every outbound request URL host is validated against an exact-match allowlist
before the request is sent. The default allowlist is:

```
data.cdc.gov
api.us.socrata.com
```

Configured in [`src/resp_mcp/config.py`](src/resp_mcp/config.py) as
`ALLOWED_DOMAINS`. Any host not on this list raises `SecurityError` and the
request is never made. Tool inputs cannot supply, override, or expand this list.
HTTP redirects and environment proxies are disabled on the `httpx.AsyncClient`.

### SoQL construction — enums and codes only

The Socrata query layer (`clients/socrata.py`) builds `$where` clauses
exclusively from:
- validated `Pathogen` / `Signal` enum values,
- jurisdiction codes resolved through `reference/jurisdictions.py`,
- ISO 8601 date strings from Python `datetime.date` objects.

No raw user-supplied strings are interpolated into SoQL. String literals that
must appear in queries pass through a quoting helper that escapes single quotes.
This prevents SoQL injection regardless of agent or user input content.

### Input length and character bounds

All free-text tool inputs (jurisdiction names, aliases) are validated before
any difflib matching or logging:
- Empty strings are rejected.
- Strings longer than 64 characters raise a clean validation error.
- Control characters are stripped before any downstream processing.

Pydantic models on all tool inputs enforce type, range, and enum constraints
before any source adapter is called.

### Request timeouts and caps

| Parameter | Value |
|---|---|
| Per-request timeout | 6 seconds |
| Total query deadline (incl. retries + pagination + cache lock) | 20 seconds |
| Hard row cap per paginated query | 50,000 rows |
| Cache TTL | 3,600 seconds (1 hour) |
| Max retries on 429/5xx/timeout | 3 (exponential backoff + jitter) |

Reaching the row cap produces an error; partial data is never silently analyzed.

### Single-flight cache

Concurrent streamable-HTTP requests for the same uncached Socrata query are
coalesced by a per-key `asyncio.Lock` (single-flight pattern). Only one upstream
request is made; subsequent callers wait for the same result. This prevents
thundering-herd stampedes when a wxO agent issues parallel tool calls.

---

## Credential handling

**No credentials are required for local tests or frozen replay.** The optional
`SOCRATA_APP_TOKEN` raises rate limits from ~1 req/s to ~10 req/s but is never
mandatory. It must be placed in the gitignored root `.env` file and must never
appear in commits, screenshots, evaluation transcripts, or prompt text.

wxO credentials (`WXO_INSTANCE_URL`, toolkit names, agent IDs) must also remain
in the gitignored `.env` and `deploy/ibm/local-mcp-toolkit/.env` files. The
`.gitignore` excludes both.

The MCP endpoint itself has no built-in authentication layer. Keep it inside an
authorized sandbox and behind appropriate platform authentication or network
controls when connecting remote clients. Do not expose it on a public network.

---

## Deployment posture

**Sandbox-only.** No deployment to any public endpoint was performed as part of
this project. All verification runs are local.

- Container examples bind the host port to loopback (`127.0.0.1:8080`).
- The cloud.gov `manifest.yaml` creates no public route by default.
- Nothing in this repository has been registered with a public registry or
  granted production CDC access.

Before any deployment: review the access controls, confirm the platform network
boundary, and obtain appropriate authorization from the responsible authorities.

---

## Dependency pinning

All runtime and development dependencies are recorded in `uv.lock`. Container
installs use `--frozen` to install from the exact locked versions. This prevents
supply-chain drift between development and deployment environments.

To verify the lock is in sync:

```shell
uv lock --check
```

---

## Error handling and information leakage

Unexpected exception details and upstream CDC response bodies are not returned to
MCP clients. Structured error types (`UpstreamUnavailable`, `UpstreamBadRequest`,
`UpstreamRateLimited`, `UnknownJurisdiction`) carry only safe, pre-defined messages.
Application logs record exception categories and dataset identifiers, never raw
upstream bodies or full query URLs with tokens.

---

## Stdout discipline (stdio transport)

MCP stdio transport uses stdout for protocol messages. All application logging
(including errors and debug output) is directed exclusively to stderr by
`configure_logging()` in `config.py`. No `print()` calls exist in server code.
This is enforced in the test suite by a zero-stdout check during tool calls.

---

## Reporting vulnerabilities

Report suspected vulnerabilities privately to the repository maintainer. Do not
include secrets, sensitive records, or reproduction payloads in a public issue.
The upstream GSA template's security policy applies to GSA-operated systems; this
fork is not represented as a GSA-operated service.
