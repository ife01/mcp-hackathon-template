# Submission checklist — November 23, 2026

This checklist supersedes the earlier Build 5.5 readiness claims.
The user confirmed an end-of-business submission extension for November 23.
Use the organizer's participant instructions for the final submission channel and receipt.

## Required deliverables

GSA lists a GitHub repository, presentation slide deck and evaluation documentation.
See the [official event deliverables](https://www.gsa.gov/super-intelligence/si-community-of-practice/events-and-training/mcp-server-and-si-agent-government-hackathon).
The public page does not list a recording as a separate required deliverable.
Follow any additional participant-specific instructions.

| Item | Current evidence | Remaining action |
| --- | --- | --- |
| Complete documented repository | Public repository; code and evidence on main | Use the final main commit in the submission |
| Evaluation documentation | [Combined results](../eval/RESULTS.md), frozen baseline, Phoenix results, API traces and manual wxO retests | Include this link; preserve the separate evidence labels |
| Presentation slide deck | No PPTX or presentation PDF found in this checkout | Complete or locate the deck and attach it as instructed |
| Submission delivery | No portal receipt or final submission confirmation observed | Send the required links and files through the organizer's channel; retain the receipt |

The deck must cover the problem, solution, technical approach and key decisions, and demonstration of functionality.
A live public production deployment is not required; the event scope is a sandbox prototype.

## Verified technical state

| Check | Latest supported result |
| --- | --- |
| Regression suite | 386 passed; two upstream dependency deprecation warnings |
| Frozen tool evaluation | 25/25 cases and 155/155 assertions |
| wxO runtime | RSA uses respiratory_mcp_local_v3, source 13d68fa; package and bindings verified |
| National scan follow-up | Four captured post-fix answers match their actual 43 returned members and counts |
| Trend attribution follow-up | Three independent captured trend answers attribute the heuristic to the application |
| Latest manual UI retest | Six targeted visible-answer reviews pass; raw tool details were not supplied |
| Phoenix | Separate 15-case frozen-agent run; original scores and limitations unchanged |
| Remote GitHub CI | Public API still reports zero workflow runs as of this check; no remote pass claimed |
| Existing v1.0-hackathon tag | Points to old commit 27c232255c95fe530e9415ec531e87732cf19aa3; excludes later fixes |

See [scan verification](WXO_SCAN_FIX_2026-11-23.md) and the [successful manual retest](../eval/transcripts/wxo/2026-11-23-manual-success/REVIEW.md).
Historical Docker, transport and coverage results retain their original scope in [VERIFICATION.md](VERIFICATION.md).
They were not rerun for this documentation update.

## Final packaging and rehearsal

- [ ] Complete or locate the required slide deck.
- [ ] Enable fork Actions if needed, then run the CI workflow on final main. The reason for zero runs is not confirmed.
- [ ] Link the final main commit, or create a new submission tag after the last change. Do not submit the stale tag as current.
- [ ] Rehearse with RSA and the v3 toolkit using the current policy. Check source dates and visible claims.
- [ ] Disclose the historical peak-denominator explanation defect. Verify that feature before demonstrating peak comparisons.
- [ ] Include repository, deck and evaluation links in the organizer's submission process and retain confirmation.

CI and an immutable commit/tag improve verification and reproducibility; the event page does not list them as separate deliverables.
A recording is needed only if the participant submission instructions request one.

## Claims to retain accurately

The successful manual retest covers six related questions in one conversation.
It does not establish six independent trials, fresh tool calls or an overall wxO accuracy rate.
The API traces independently verify the earlier targeted calls and responses.
The model can still reformat generated display blocks and reuse prior conversation evidence.
The supplemental historical peak-labeling error remains unresolved; the latest six questions did not test it.
Phoenix uses a different agent and frozen replay. Its scores do not transfer to wxO.
No measured analyst time savings, independent holdout accuracy or clinical validity is claimed.
