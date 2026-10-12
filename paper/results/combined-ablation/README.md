# Combined loop-only ablation

These files report the exploratory A12 condition, which removes the goal network, adaptive process order, and subagents together while keeping the `Monitor`, the persistent `.writing/` draft, and the role skills. A12 shows no detectable difference from A4 on the pooled prompt set and beats A2, which is consistent with the hypothesis that the `Monitor` working over a persistent draft, rather than any of the three removed components, carries A4's advantage over A2. The [conditions README](../../../experiments/conditions/README.md#a12-loop-only) defines A12, lists the executed source skill versions, and records every edit.

[`a12-pairwise.json`](a12-pairwise.json) holds, per benchmark and pooled over the three benchmarks, the prompt-collapsed win, loss, and tie counts for the contrasts A4 versus A12 and A12 versus A2. Each entry also gives the win rate over non-tied prompts with its Wilson 95% interval, the exact two-sided sign-test p-value, and the tie-as-half score, (wins + ties / 2) / scored prompts. The left condition of each contrast label is the one whose wins are counted. The file also records completion counts, median output words, mean output-plus-reasoning and uncached input tokens per attempted run, and the A12 process-path summary.

| Contrast | Wins | Losses | Ties | Win rate | Wilson 95%  | Exact sign-test p |
| -------- | ---: | -----: | ---: | -------: | ----------- | ----------------: |
| A4:A12   |   96 |     92 |  104 |    0.511 | 0.440–0.581 |              0.83 |
| A12:A2   |  141 |     62 |   96 |    0.695 | 0.628–0.754 |        3.0 × 10⁻⁸ |

The A12 advantage over A2 is concentrated in WritingBench, where A12 wins 68 of 83 decided prompts, and in DoLoMiTes, where A12 wins 44 of 67; on HelloBench, the A12 versus A2 difference is not significant (29 wins, 24 losses, p = 0.58). No benchmark shows a significant A4 versus A12 difference; the smallest p-value is 0.27, on HelloBench.

A12 runs almost always make one `Planning`, `Translating`, then `Reviewing` pass and stop. Of the 299 completed runs, 288 trace exactly one such pass, 297 end after `Reviewing`, and one returns from `Reviewing` to `Translating`; no run spawns a subagent or records a goal event. A12 therefore tests one prompt-fixed pass by the `Monitor` over a persistent draft rather than repeated passes.

| Condition | Completed | Median words | Mean output + reasoning tokens | Mean uncached input tokens |
| --------- | --------: | -----------: | -----------------------------: | -------------------------: |
| A2        |       300 |        1,510 |                         10,728 |                     21,822 |
| A4        |       293 |        1,835 |                         13,374 |                     46,860 |
| A12       |       299 |        1,671 |                         11,071 |                     24,244 |

A12 was generated once, on the 300-prompt evaluation set of generation run 1, with the same generator model, reasoning effort, Codex CLI version, output budget, timeout, and retry policy as A4. The A4 and A2 outputs are the existing run-1 outputs. Three A12 runs failed, two on trace timestamp validation and one on the retrieval tripwire, and each was retried once; the retrieval failure recurred, so 299 of 300 A12 prompts have a completed output. Seven A4 run-1 prompts have no completed output, so the A4 versus A12 contrast covers 292 prompts.

Judging matches the A9 pairwise setup: `gpt-5.6-sol` with the provider-default reasoning effort, seed 20260908, presentation seed 20260908, a 4,096-token output limit, two retries, both presentation orders, and the [`pairwise-v1`](../../../experiments/prompts/judges/pairwise-v1.md) prompt. A prompt counts as a win only when both presentations agree on the same winner; any disagreement counts as a tie. A12 is outside the Holm-corrected confirmatory family, and these p-values are unadjusted.
