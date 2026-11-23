# Submission checklist — November 23, 2026

Submit the repository link and separate files through the organizers' submission form.
Keep the submission receipt. A completed submission has not been confirmed here.

Repository: [ife01/respiratory-surveillance-mcp](https://github.com/ife01/respiratory-surveillance-mcp).
Submission tag: [v1.1-hackathon](https://github.com/ife01/respiratory-surveillance-mcp/tree/v1.1-hackathon).
This tag preserves the verified code and evaluation evidence. Later documentation edits appear on main.
The earlier `v1.0-hackathon` tag remains unchanged.

## Required deliverables

GSA lists a GitHub repository, presentation slide deck and evaluation documentation.
See the [official event deliverables](https://www.gsa.gov/super-intelligence/si-community-of-practice/events-and-training/mcp-server-and-si-agent-government-hackathon).
The public page does not list a recording as a separate required deliverable.
Follow any additional participant-specific instructions.

| Item | Current evidence | Remaining action |
| --- | --- | --- |
| Complete documented repository | Public repository; code and evidence included in v1.1-hackathon | Use the new submission tag link |
| Evaluation documentation | [Combined results](../eval/RESULTS.md), frozen baseline, Phoenix results, API traces and manual wxO retests | Include this link; preserve the separate evidence labels |
| Presentation slide deck | Prepared outside the repository: Respiratory-MCP-Hackathon-Submission-v2.pptx | Upload through the submission form |
| Standalone evaluation document | Prepared outside the repository: Respiratory-MCP-Hackathon-Evaluation.docx | Upload through the submission form |
| Demo video | Prepared outside the repository: Demo-compressed-corrected.mp4 | Upload the corrected copy through the submission form |
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
| Recorded GitHub CI | [Run 45219867192 passed](https://github.com/ife01/respiratory-surveillance-mcp/actions/runs/45219867192) on submission commit 9af0c35 |
| Submission tag | v1.1-hackathon includes all fixes and evaluation documentation; v1.0-hackathon remains the earlier candidate |

See [scan verification](WXO_SCAN_FIX_2026-11-23.md) and the [successful manual retest](../eval/transcripts/wxo/2026-11-23-manual-success/REVIEW.md).
The successful CI run passed lint, formatting, tests, Phoenix dry-run validation, frozen evaluation and MCP integration checks.
That run verified submission commit `9af0c35`. Later repository cleanup does not change the recorded evaluation results.

Historical Docker, transport and coverage results retain their original scope in [VERIFICATION.md](VERIFICATION.md).
They were not rerun for this documentation update.

## Final packaging and rehearsal

- [x] Prepare the slide deck and standalone evaluation document outside the repository.
- [x] Save the corrected demo outside the repository; retain the original recording.
- [x] Enable Actions and obtain a successful remote CI run; linked above.
- [x] Create the new v1.1-hackathon submission tag after the checklist update; preserve the old tag.
- [ ] Rehearse with RSA and the v3 toolkit using the current policy. Check source dates and visible claims.
- [x] Disclose the historical peak-denominator explanation defect in the submission materials.
- [x] Add a correction caption for the demo's incorrect trend-week explanation.
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

The recorded demo also contains incorrect week labels in RSA's trend explanation.
Its correction caption identifies the latest window as October 24 and 31, versus October 10 and 17.
The corresponding means are 1.350 and 0.715 admissions per 100,000, an increase of 88.8%.
This caption corrects the presentation; it does not establish a fix to the agent's explanation behavior.
