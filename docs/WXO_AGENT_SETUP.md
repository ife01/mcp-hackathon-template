# wxO Agent Setup — Respiratory Season Situational Awareness

This document describes how to configure an IBM watsonx Orchestrate (wxO) Agent Builder
agent that is backed by this MCP server.  It mirrors the behaviour of the
`weekly_respiratory_briefing` and `regional_hotspot_review` prompts so that the wxO agent
behaves correctly even when it does not invoke MCP Prompts natively.

---

## 1. Register the MCP server as a toolkit

### Remote (Streamable HTTP — preferred for deployed/containerised server)

```bash
orchestrate toolkits add \
  --name respiratory-mcp \
  --type mcp \
  --url http://<HOST>:8080/mcp \
  --transport streamable-http
```

Or through **AI Gateway → MCP servers**, paste the same URL and choose
*Streamable HTTP*.

### Local (stdio — for development on the same VM)

```bash
orchestrate toolkits add \
  --name respiratory-mcp \
  --type mcp \
  --command "uv run python main.py" \
  --package-root /path/to/Respiratory_MCP \
  --transport stdio
```

Verify that `tools/list` returns in < 5 s (well under wxO's 30 s timeout):

```bash
orchestrate toolkits list --name respiratory-mcp
```

---

## 2. Available tools

| Tool | When wxO should call it |
|---|---|
| `get_respiratory_snapshot` | "What is happening with flu/COVID/RSV in \<jurisdiction\> this week?" |
| `assess_trend` | "Is \<pathogen\> getting better or worse in \<jurisdiction\>?" |
| `compare_to_prior_seasons` | "How does this season compare with previous years?" |
| `find_jurisdictions_with_rising_activity` | "Which states / regions are seeing rising activity right now?" |

---

## 3. System prompt / agent instructions

Paste the following block verbatim into **Agent Builder → Instructions** (or the
equivalent system-prompt field).  These rules mirror the `weekly_respiratory_briefing`
prompt so the agent behaves correctly even without native MCP Prompt support.

```
You are a respiratory disease situational-awareness assistant for public health
professionals.  You have access to four tools that query real-time CDC public data:
get_respiratory_snapshot, assess_trend, compare_to_prior_seasons, and
find_jurisdictions_with_rising_activity.

Rules you MUST follow on every response:

1. ALWAYS call a tool before stating any number.  Never invent, estimate, or recall
   respiratory surveillance figures from your training data.

2. CITE PROVENANCE in every answer.  For every numeric claim, state:
   - the dataset name (from tool output's provenance.dataset_name)
   - the week-ending date (from tool output's provenance.latest_week_ending or
     the observation's week_ending)
   Example: "Hospital admissions were 1.4 per 100 k (NHSN, week ending 2025-10-18)."

3. REPRODUCE CAVEATS verbatim.  If the tool output contains a caveats list or a
   status of "insufficient_data" / "unavailable", include those caveats in your
   answer, clearly labelled "Data caveats:".

4. NEVER soften or omit an "insufficient_data" or "unavailable" status.  If a signal
   is unavailable, say so explicitly rather than ignoring it.

5. FOR TREND QUESTIONS, use assess_trend.  Do not compute trends yourself from
   snapshot numbers.

6. FOR SEASON COMPARISONS, use compare_to_prior_seasons.  Do not compare seasons
   yourself.

7. FOR NATIONAL SCANS or "which states are rising", use
   find_jurisdictions_with_rising_activity with appropriate pathogen and signal
   arguments.

8. AUDIENCE MATTERS.  When the user indicates a lay audience, avoid jargon and
   explain abbreviations (WVAL, MMWR week, per 100 k).  When the user indicates an
   epidemiologist audience, preserve technical precision.

9. This server is a PROTOTYPE using public aggregate CDC data.  It is NOT a
   real-time clinical or operational system.  Include this disclaimer in any
   output intended for public distribution.

10. If the user asks about a jurisdiction you are unsure of, pass the name as-is
    to the tool — the server will suggest corrections for misspellings.
```

---

## 4. Suggested opening turn for the wxO Chat demo

> "Give me a weekly respiratory briefing for Georgia.  Include flu, COVID-19, and RSV,
> and note any trend concerns."

Expected tool call sequence:
1. `get_respiratory_snapshot(jurisdiction="GA", pathogens=["influenza","covid19","rsv"])`
2. `assess_trend(jurisdiction="GA", pathogen="influenza", signal="hospital_admissions")`
   (wxO may chain additional trend calls per pathogen based on snapshot output)

---

## 5. `toolkit.yaml` reference

```yaml
name: respiratory-mcp
description: >
  Real-time flu, COVID-19, and RSV situational awareness for public health
  professionals.  Uses CDC NHSN, NWSS, and NREVSS public data.
transport: streamable-http
url: http://localhost:8080/mcp
auth: none
read_only: true
```

Adjust `url` to point at your deployed container or sandbox endpoint before
registering for the wxO demo.

---

## 6. Known limitations

| Limitation | Mitigation |
|---|---|
| wxO may not invoke MCP Prompts natively | System prompt in §3 duplicates prompt logic |
| wxO tools/list timeout = 30 s | tools/list requires zero network calls by design |
| NREVSS is national-only | Tool outputs include `geography_level: "national"` caveat |
| NWSS gaps for some territories (e.g., Puerto Rico) | Returns `status: "insufficient_coverage"` with explanation |
| Data lags 1–2 weeks | `provenance.latest_week_ending` is always surfaced in output |
