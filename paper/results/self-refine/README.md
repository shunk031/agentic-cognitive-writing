# Budget-matched Self-Refine

These files report the exploratory A10 condition, a single-session Self-Refine baseline that writes a draft and then runs two feedback and refine rounds, with its round count calibrated so that its generation budget approximates Agentic CogWriter's. A4 beats A10 on the pooled prompt set even though A10 spends about 12 percent more output-plus-reasoning tokens per document, so spending a matched budget on plain self-feedback does not reproduce A4's advantage. The [conditions README](../../../experiments/conditions/README.md#a10-budget-matched-self-refine) defines A10 and records the round-count calibration.

[`a10-pairwise.json`](a10-pairwise.json) holds, per benchmark and pooled over the three benchmarks, the prompt-collapsed win, loss, and tie counts for the contrast A4 versus A10. Each entry also gives the win rate over non-tied prompts with its Wilson 95% interval, the exact two-sided sign-test p-value, and the tie-as-half score, (wins + ties / 2) / scored prompts. A4's wins are counted. The file also records the round count, completion counts, median output words per condition and benchmark measured with the runner's frozen word rule, and mean output-plus-reasoning tokens per completed document, over all completed runs and over the prompts where both conditions completed.

| Scope        | Wins | Losses | Ties | Win rate | Wilson 95% interval | Exact sign-test p |
| ------------ | ---: | -----: | ---: | -------: | ------------------: | ----------------: |
| Pooled       |  137 |     70 |   85 |    0.662 |         0.595–0.723 |        3.7 × 10⁻⁶ |
| WritingBench |   59 |     16 |   21 |    0.787 |         0.681–0.864 |        6.1 × 10⁻⁷ |
| HelloBench   |   45 |     24 |   30 |    0.652 |         0.534–0.754 |             0.015 |
| DoLoMiTes    |   33 |     30 |   34 |    0.524 |         0.403–0.642 |              0.80 |

**Budget.** The round count k = 2 was fixed on calibration prompts outside the scored set, where it averaged 13,689 output-plus-reasoning tokens per document against A4's run-1 mean of 13,374. On the scored set, A10 averages 15,015 tokens per completed document and A4 averages 13,343, or 14,984 and 13,348 over the 292 prompts where both completed. A10 therefore received about 12 percent more generation budget than A4, which favors A10 in this contrast. A10's documents are shorter in words than A4's, with pooled medians of 1,391 and 1,835 words.

**Runs.** A10 was generated once, on the 300-prompt evaluation set of generation run 1, with the same generator model, reasoning effort, Codex CLI version, output budget, timeout, and retry policy as A4. The A4 outputs are the existing run-1 outputs. Eleven A10 runs failed the trace contract, logging more or fewer Draft, Feedback, and Refine events than the two rounds require, and each was retried once. Ten retries completed, so 299 of 300 A10 prompts have a completed output. Seven A4 run-1 prompts have no completed output, so the contrast covers 292 prompts.

**Judging.** Judging matches the run-1 pairwise setup: `gpt-5.6-sol` with the provider-default reasoning effort, seed 20260908, presentation seed 20260908, a 4,096-token output limit, two retries, both presentation orders, and the [`pairwise-v1`](../../../experiments/prompts/judges/pairwise-v1.md) prompt. A prompt counts as a win only when both presentations agree on the same winner; any disagreement counts as a tie. A10 is outside the Holm-corrected confirmatory family, and these p-values are unadjusted.
