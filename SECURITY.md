# Security and data handling

This repository is a read-only hackathon prototype using public aggregate CDC
data. It does not request line-level records, PII, PHI, or internal CDC access.
No production authorization or operational readiness is implied.

## Request boundaries

Only fixed public CDC/Socrata origins are allowed by the data client. Tool inputs
cannot supply an outbound URL. SoQL values come from validated reference codes,
pathogens, and dates; string literals are escaped. Redirects and environment
proxies are disabled. Query deadlines, retries, a 50,000-row cap, and per-key
single-flight caching bound request behavior. Reaching the cap produces an error.

The test suite blocks unmocked HTTP requests by default. Live tests require the
live marker and RUN_LIVE=1. Snapshot capture is an explicit network operation;
offline replay has no network fallback and verifies file hashes.

## Access and credentials

The MCP endpoint has no built-in authentication. Keep it in an authorized sandbox
and behind appropriate platform authentication/network controls when connecting
remote clients. Do not expose it publicly. Container examples bind the host port
to loopback; the cloud.gov manifest creates no route by default. No deployment was
performed as part of evaluation preparation.

Keep wxO API keys and optional Socrata tokens in environment variables or the
ignored root .env file. Never include keys in commits, prompts, screenshots, or
evaluation transcripts. The service URL, agent ID, and authentication type are
needed to configure a future live-agent evaluation; local checks require none.

## Errors and integrity

Unexpected exception contents and upstream response bodies are not returned to
clients. Application error logs use exception categories and source identifiers,
not upstream bodies or query URLs. Treat all tool inputs and retrieved content as
untrusted. Keep access controls and log retention consistent with the sandbox.
Dependencies are recorded in uv.lock; container installs use the frozen lock.

Published NHSN categories, server-derived wastewater aggregates, national context,
missing coverage, and unavailable sources are distinguished. Data lags and
prototype thresholds limit interpretation; see docs/METHODS.md.

Report suspected vulnerabilities privately to the repository maintainer. Do not
include secrets or sensitive records in a public issue. The upstream template's
GSA policy applies to GSA-operated systems; this fork is not represented as a
GSA-operated service.
