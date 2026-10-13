# CogWriter-style baseline on the main benchmarks

These files report the exploratory B1 condition, the CogWriter-style adaptation, on the 300-prompt evaluation set of DoLoMiTes, HelloBench, and WritingBench. A4 beats B1 on every benchmark and on the pooled prompt set. B1 also fails its final-product gate more often than A4, so 34 of its 300 prompts have no completed output. The [conditions README](../../../experiments/conditions/README.md) defines B1 as the `writing-cogwriter-style` skill from the baseline package.

[`b1-pairwise.json`](b1-pairwise.json) holds, per benchmark and pooled over the three benchmarks, the prompt-collapsed win, loss, and tie counts for the contrast A4 versus B1. Each entry also gives the win rate over non-tied prompts with its Wilson 95% interval, the exact two-sided sign-test p-value, and the tie-as-half score, (wins + ties / 2) / scored prompts. A4's wins are the ones counted. The file also records completion counts, median output words measured with the runner's frozen word rule, mean tokens per attempted run, and generation attempts.

| Benchmark    | Scored prompts | Wins | Losses | Ties | Win rate | Wilson 95% interval | Exact sign-test p |
| ------------ | -------------: | ---: | -----: | ---: | -------: | ------------------: | ----------------: |
| DoLoMiTes    |             98 |   75 |     14 |    9 |    0.843 |         0.753–0.904 |       3.0 × 10⁻¹¹ |
| HelloBench   |             85 |   48 |     14 |   23 |    0.774 |         0.656–0.860 |        1.7 × 10⁻⁵ |
| WritingBench |             76 |   63 |      5 |    8 |    0.926 |         0.839–0.968 |       7.7 × 10⁻¹⁴ |
| Pooled       |            259 |  186 |     33 |   40 |    0.849 |         0.796–0.891 |       4.5 × 10⁻²⁷ |

B1 writes text of similar length to A4 but uses more tokens. The pooled median output is 1,684.5 words for B1 and 1,835 for A4. Per attempted run, B1 averages 18,011 output-plus-reasoning tokens and 55,215 uncached input tokens in the parent session, against 13,374 and 46,860 for A4. B1 delegates more, with a mean of 12.6 subagent spawns per attempted run against 3.2 for A4. The token means follow the run-1 process-summary definition, which counts the parent session's `turn.completed` usage and excludes subagent sessions.

| Condition | Completed | DoLoMiTes words | HelloBench words | WritingBench words | Pooled words |
| --------- | --------: | --------------: | ---------------: | -----------------: | -----------: |
| A4        |       293 |             734 |            1,753 |              4,690 |        1,835 |
| B1        |       266 |             829 |          1,705.5 |              4,282 |      1,684.5 |

B1 completed 100 DoLoMiTes, 86 HelloBench, and 80 WritingBench prompts. Every failed B1 run failed the runner's final-product gate:

- No `draft.md` file: 29 runs
- A final response shorter than half of the draft: 3 runs
- An empty final response: 2 runs

The first pass left 46 prompts failed. Failed prompts were retried once each in seeded random order (seed 20260908) until the run's cost cap was reached. Of the 21 retried prompts, 12 completed, and 25 failed prompts were not retried. A prompt counts only when both conditions have a completed output, so the contrast covers 259 prompts. Seven A4 run-1 prompts have no completed output.

B1 was generated once with the same generator model, reasoning effort, Codex CLI version, output budget, timeout, and runner retry policy as the run-1 conditions. The A4 outputs are the existing run-1 outputs. The B1 wrapper configuration, its shared prompt contracts, and the `writing-cogwriter-style` skill are byte-identical to the versions used in the Habermas consensus-writing pilot.

Judging matches the run-1 pairwise setup: `gpt-5.6-sol` with the provider-default reasoning effort, seed 20260908, presentation seed 20260908, a 4,096-token output limit, two retries, both presentation orders, and the [`pairwise-v1`](../../../experiments/prompts/judges/pairwise-v1.md) prompt. A prompt counts as a win only when both presentations agree on the same winner; any disagreement counts as a tie. B1 is outside the Holm-corrected confirmatory family, and these p-values are unadjusted.

[`b1-spawns.json`](b1-spawns.json) is the output of [`spawn_summary.py`](../../../experiments/src/agentic_cogwriter/analysis/spawn_summary.py) over the generation-run-1 roots for A4 and B1. It gives the mean `subagent_spawn_count` per attempted canonical run, which reproduces A4's run-1 process-summary value. Regenerate its macro with `python3 scripts/make_numbers.py --cogwriter-spawns results/cogwriter-main/b1-spawns.json` from `paper/`.
