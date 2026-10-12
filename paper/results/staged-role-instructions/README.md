# Staged generation with role instructions

These files report the exploratory A9 condition, which adds the A4 `Planning`, `Translating`, and `Reviewing` role instructions to the three A2 stage prompts. A4 beats A9 on the pooled prompt set, and A9 does not beat A2, so the role instructions alone do not reproduce A4's advantage over A2. The [conditions README](../../../experiments/conditions/README.md#a9-staged-role-instructions) defines A9 and lists every role-text edit.

[`a9-pairwise.json`](a9-pairwise.json) holds, per benchmark and pooled over the three benchmarks, the prompt-collapsed win, loss, and tie counts for the contrasts A4 versus A9 and A9 versus A2. Each entry also gives the win rate over non-tied prompts with its Wilson 95% interval, the exact two-sided sign-test p-value, and the tie-as-half score, (wins + ties / 2) / scored prompts. The left condition of each contrast label is the one whose wins are counted. The file also records completion counts and median output words per condition and benchmark, measured with the runner's frozen word rule.

| Contrast | Wins | Losses | Ties | Win rate | Exact sign-test p |
| -------- | ---: | -----: | ---: | -------: | ----------------: |
| A4:A9    |  141 |     66 |   86 |    0.681 |        2.0 × 10⁻⁷ |
| A9:A2    |   85 |    100 |  115 |    0.459 |              0.30 |

A9 was generated once, on the 300-prompt evaluation set of generation run 1, with the same generator model, reasoning effort, Codex CLI version, output budget, timeout, and retry policy as A2. The A4 and A2 outputs are the existing run-1 outputs. One A9 run failed the final-product gate and was retried once, and the retry completed; all 300 A9 prompts have a completed output. Seven A4 run-1 prompts have no completed output, so the A4 versus A9 contrast covers 293 prompts.

Judging matches the run-1 pairwise setup: `gpt-5.6-sol` with the provider-default reasoning effort, seed 20260908, presentation seed 20260908, a 4,096-token output limit, two retries, both presentation orders, and the [`pairwise-v1`](../../../experiments/prompts/judges/pairwise-v1.md) prompt. A prompt counts as a win only when both presentations agree on the same winner; any disagreement counts as a tie. A9 is outside the Holm-corrected confirmatory family, and these p-values are unadjusted.
