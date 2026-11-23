# IBM Bob evaluation handoff

> Update 2026-11-23: organizational model access is now configured locally. A real Phoenix run completed all 15 cases.
> See [the results and limitations](../eval/phoenix/RESULTS_2026-11-23.md). Earlier statements about unavailable model access describe the prior review.

The public health correctness fixes and Phoenix evaluation harness are ready for
provider configuration and real-model evaluation. Start with
[the harness guide](../eval/phoenix/README.md) and
[verification evidence](VERIFICATION.md).

## Verified before handoff

- 355 automated tests passed; server line coverage is 94%.
- Frozen tool baseline: 25 cases and 155 checks passed.
- Phoenix dataset and experiment dry-runs passed for 15 questions.
- Actual MCP stdio, LangChain graph, Phoenix local dataset/experiment storage and
  trace export/readback were verified with scripted responses and mocked model
  HTTP. These are infrastructure checks, not real-model accuracy scores.
- Ruff lint/format, lock consistency and whitespace checks passed.

## Next steps

1. Run `uv sync --frozen --group dev` from the repository root.
2. Confirm the provider's Chat Completions API base URL, tool-capable agent model
   ID, structured-output judge model ID and authentication method. The current
   adapter uses a standard Bearer API key. Native watsonx.ai authentication may
   require a provider adapter; wxO credentials are separate.
3. Configure an ignored root `.env` using `.env.example`. Never commit secrets.
4. Start `uv run python eval/phoenix/serve.py` in one terminal.
5. Upload with `uv run python eval/phoenix/create_dataset.py --dataset-name respiratory-eval-0`.
6. Record the returned dataset version ID. Run
   `uv run python eval/phoenix/run_experiment.py --dataset-name respiratory-eval-0 --dataset-version-id YOUR_VERSION_ID --system-prompt-version v2`.
7. Review every execution/judge error and failed public health check in Phoenix.
   Compare v1/v2 on the same dataset version and judge model; use three
   repetitions for a stronger final comparison.

Preserve snapshot_v2 and independent references. Do not feed expected answers
to the agent or count scripted verification as benchmark results. Do not replace
missing historical ranks with fabricated values, treat national positivity as
state evidence, or present derived wastewater categories as official state
classifications. Review representative outputs against docs/METHODS.md.

The native LangChain MCP adapter replaces the skill's incompatible legacy
adapter; the reason and verification are documented in the harness guide.
No model credentials, local Phoenix database or local verification-run outputs
are included in this handoff. Real model performance and live wxO integration
remain unmeasured.
