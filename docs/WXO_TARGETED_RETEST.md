# Targeted wxO retest before submission

The local server fix separates the application date limit from CDC dataset history.
All four tools return the corrected message for an unsupported early date.
The updated package is active in wxO as `respiratory_mcp_local_v2`.
RSA uses its four tools. The complete six-question retest remains pending.

## Verified reimport on November 23, 2026

The first upload changed stored files but left the old error active.
A new toolkit registration succeeded, and RSA received the four new tool references.
RSA kept its existing instructions and model settings. The original toolkit remains as a backup.

The deployed source is commit `8f5fabb`. Runtime dependencies use exact versions from `uv.lock`.
A live RSA run completed at `2026-11-23T15:24:03Z` with model `groq/openai/gpt-oss-120b`.
Its actual `assess_trend` call used Georgia, influenza, hospital admissions and `as_of="2015-01-01"`.
The tool returned the corrected application-limit error. The final answer preserved that distinction.
See the [sanitized run evidence](../eval/transcripts/wxo/2026-11-23-v2-date-boundary.json).

This directed smoke test confirms the runtime correction for question 6.
It does not establish a pass for the natural-language retest or questions 1–5.
The Phoenix results remain separate evidence.

Refresh the wxO page and select **RSA** for further tests.
Start a new conversation and check that its tools come from `respiratory_mcp_local_v2`.

## What you need

- Your existing wxO sandbox service URL and API key.
- The machine or Bob environment with the IBM Orchestrate ADK installed.
- The latest checkout of this repository.
- Access to edit the wxO agent and its attached `respiratory_mcp_local` tools.
- A way to retain complete tool details and final answers.

The organizational model gateway key is not required for these wxO sessions.
Keep the wxO key in the local credential mechanism or hidden registration prompt.

## Future toolkit registration

The current RSA tools use the versioned registration described above.
The commands below recreate the original template name, `respiratory_mcp_local`.
They do not update the active versioned registration.
After any future registration, attach the intended new tools to the agent.

Run these commands in Bash on the machine used for toolkit registration:

```bash
git pull --ff-only origin main
git rev-parse HEAD
set -a
source deploy/ibm/local-mcp-toolkit/.env
set +a
export TOOLKIT_NAME=respiratory_mcp_local
bash deploy/ibm/local-mcp-toolkit/register-toolkit.sh
```

The ignored toolkit `.env` needs `WXO_INSTANCE_URL`, `WXO_ENV_NAME` and `TOOLKIT_NAME`.
If `WXO_API_KEY` is absent, the script requests it with hidden input.
The toolkit name must match `toolkit.yaml`.
Reimport uploads the changed server package; a GitHub push alone does not update wxO.
The script removes and recreates the named toolkit.

In the wxO agent editor, check the attached tools after reimport.
Reattach the new toolkit tools if the old references no longer resolve.
Save or publish the agent version used for testing, as appropriate for your sandbox.
Record that version and the Git commit printed above.

## Agent instructions for the retest

Keep the public health policy in [WXO_AGENT_SETUP.md](WXO_AGENT_SETUP.md#agent-instructions).
For this live retest, omit its benchmark-only paragraph that fixes every call to October 31.
Do not add a session-wide cutoff message.
The questions themselves must supply the dates.

Use these rules in the agent instructions:

```text
Preserve dates specified in natural-language questions.
Pass the requested observation cutoff as as_of on every tool call.
Do not substitute later observations or hard-code a benchmark date.
If no cutoff was requested, use the most recent available data.

Limit regional scan answers and missingness statements to the requested region.
Use returned assessment counts and unavailable_jurisdictions.
Do not treat a state outside the region as missing.
Distinguish total rising jurisdictions from the displayed list.

A date-validation boundary is an application limit.
It does not establish when a CDC dataset began or whether earlier records exist.
Explain an unsupported date without inventing source history or a replacement value.
```

## Six questions

Start a fresh conversation for each question.
Do not supply expected answers or tool-call plans to the agent.

1. What was the influenza hospital admission rate in Georgia for the week ending October 31, 2026?
2. Is influenza increasing or decreasing in Georgia as of October 31, 2026?
3. What does national test positivity show for influenza as of October 31, 2026?
4. Which US states had rising influenza hospital admissions as of October 31, 2026?
5. Which HHS Region 4 states had rising flu admissions through October 31, 2026? Report missing data and the total before limiting.
6. Georgia flu admissions as of January 1, 2015.

## Review criteria

| Questions | Required evidence |
| --- | --- |
| 1–4 | Every actual call preserves `as_of="2026-10-31"`. Reported observations do not exceed that cutoff. Answers agree with actual tool payloads. |
| 5 | `hhs_region=4` and the requested cutoff reach the scan. Counts match the payload. Arkansas is outside the region and is not listed as missing. |
| 6 | The tool returns `invalid_input` with the application limit `2020-01-01`. The answer explains that limit without asserting CDC dataset inception. |

Region 4 contains AL, FL, GA, KY, MS, NC, SC and TN.
Only missing jurisdictions inside the selected scope count as missing for that scan.
The frozen reference has eight assessed and zero unavailable Region 4 states.
Live responses can change after revisions or source outages.
Grade live numerical answers against their actual tool payloads, not fixed reference values.
An explicit date filter does not turn live CDC access into frozen replay.

## Evidence to retain

For each question, retain:

- The exact user prompt and timestamp with timezone.
- The tool names and complete input arguments.
- Complete structured tool responses, including dates, counts, statuses and provenance.
- The complete final answer.
- A pass, fail or unverified decision with a short reason.

Also record the agent version, visible model ID, toolkit name and Git commit.
Mark an unavailable model ID as unknown.
Use an export or the tool-details view when available.
Do not replace the evidence with an agent-generated summary.
Remove credentials before sharing files.

These six retests do not replace or invalidate the earlier manual evaluations.
They check the known failures after the toolkit and instruction update.
Only the directed date-boundary smoke test above has new live wxO evidence.
Do not report the full six-question retest as complete without its records.
