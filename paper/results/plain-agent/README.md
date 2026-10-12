# Plain coding agent

These files report the exploratory A11 condition, which gives the same Codex harness the task prompt and one neutral working-draft instruction, with no skill content. A4 beats A11 on the pooled prompt set with a 57.2% win rate, a narrower margin than A4's 68.1% over A9. The gap comes from WritingBench and HelloBench. On DoLoMiTes, A11 is at parity with A4. The [conditions README](../../../experiments/conditions/README.md#a11-plain-agent) defines A11 and quotes its instruction.

[`a11-pairwise.json`](a11-pairwise.json) holds, per benchmark and pooled over the three benchmarks, the prompt-collapsed win, loss, and tie counts for A4 versus A11. Each entry also gives the win rate over non-tied prompts with its Wilson 95% interval, the exact two-sided sign-test p-value, and the tie-as-half score, (wins + ties / 2) / scored prompts. A4 is the left condition, so its wins are counted. The file also records completion counts, median output words per condition and benchmark under the runner's frozen word rule, A11's mean Codex token usage per completed run, and A11's draft-file behavior.

| Benchmark    | Wins | Losses | Ties | Win rate | Wilson 95% interval | Exact sign-test p |
| ------------ | ---: | -----: | ---: | -------: | ------------------: | ----------------: |
| WritingBench |   46 |     28 |   22 |    0.622 |         0.508–0.724 |             0.047 |
| HelloBench   |   39 |     23 |   37 |    0.629 |         0.505–0.738 |             0.056 |
| DoLoMiTes    |   34 |     38 |   26 |    0.472 |         0.361–0.586 |              0.72 |
| Pooled       |  119 |     89 |   85 |    0.572 |         0.504–0.637 |             0.044 |

A11 always writes a draft file but seldom revises it. All 300 completed runs wrote the document to a workspace file before returning it. In 244 runs the agent wrote that file once and returned it. The other 56 runs wrote the same file two or more times: 16 on DoLoMiTes, 11 on HelloBench, and 29 on WritingBench. Most repeated writes follow a word or character count and adjust length. The counts come from the `file_change` items and file-writing shell commands in each run's Codex event stream, excluding `.writing/assumptions.md` and the trace file.

| Measure                          | WritingBench | HelloBench | DoLoMiTes |  Pooled |
| -------------------------------- | -----------: | ---------: | --------: | ------: |
| A11 median output words          |        5,052 |      1,453 |       766 |   1,719 |
| A4 median output words           |        4,690 |      1,753 |       734 |   1,835 |
| A11 mean input tokens            |      144,837 |     92,514 |    68,265 | 101,872 |
| A11 mean cached input tokens     |      121,698 |     73,654 |    54,724 |  83,359 |
| A11 mean output tokens           |       15,061 |      6,179 |     3,936 |   8,392 |
| A11 mean reasoning output tokens |          649 |        376 |       483 |     503 |

A11 was generated once, on the 300-prompt evaluation set of generation run 1, with the same generator model, reasoning effort, Codex CLI version, output budget, timeout, and retry policy as A1. The A4 outputs are the existing run-1 outputs. Three A11 runs failed the trace gate on the first pass because the agent appended the one-line harness record twice, omitted it, or wrote it as malformed JSON. Each was retried once, and every retry completed, so all 300 A11 prompts have a completed output. Seven A4 run-1 prompts have no completed output, so the contrast covers 293 prompts.

Judging matches the run-1 pairwise setup: `gpt-5.6-sol` with the provider-default reasoning effort, seed 20260908, presentation seed 20260908, a 4,096-token output limit, two retries, both presentation orders, and the [`pairwise-v1`](../../../experiments/prompts/judges/pairwise-v1.md) prompt. A prompt counts as a win only when both presentations agree on the same winner; any disagreement counts as a tie. A11 is outside the Holm-corrected confirmatory family, and these p-values are unadjusted.
