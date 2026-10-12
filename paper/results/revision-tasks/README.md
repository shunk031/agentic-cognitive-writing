# Revision-task results

When a mid-task change forces a revision, the full system (A4) is not separable from the Fixed-order ablation (A6): A4 wins 18, loses 19, and ties 22 of 59 prompts (exact sign test p = 1.0). A4 wins more often than Staged (A2) and Single-pass (A1), but only the A4 versus A1 contrast reaches p < 0.05. The adaptive `Monitor` did respond to the change: it returned to `Planning` in 57 of 59 second turns and regenerated goals in 33. Fixed-order also returns to `Planning` by construction, however, and the two systems' revised documents are judged equivalent.

[`results.json`](results.json) is the output of the `report` subcommand of [`run_revision.py`](../../../experiments/revision-tasks/run_revision.py), applied to the experiment pre-specified in the [design README](../../../experiments/revision-tasks/README.md) with the frozen changes in [`changes.jsonl`](../../../experiments/revision-tasks/changes.jsonl). The file names prompts by their public benchmark IDs and contains no local paths.

## Pairwise outcomes

The judge is `gpt-5.6-sol` with the [`pairwise-revision-v1.md`](../../../experiments/prompts/judges/pairwise-revision-v1.md) template. Each prompt is judged in both presentation orders, and an order-inconsistent outcome counts as a tie. Counts are from A4's side, and the win rate excludes ties.

| Contrast | Prompts | Wins | Losses | Ties | Win rate | Sign-test p |
| -------- | ------: | ---: | -----: | ---: | -------: | ----------: |
| A4 vs A6 |      59 |   18 |     19 |   22 |    0.486 |       1.000 |
| A4 vs A2 |      59 |   27 |     16 |   16 |    0.628 |       0.126 |
| A4 vs A1 |      59 |   33 |     14 |   12 |    0.702 |       0.008 |

Per benchmark, A4 against A6 is 7 to 5 with 7 ties on WritingBench, 2 to 8 with 10 ties on HelloBench, and 9 to 6 with 5 ties on DoLoMiTes. No benchmark or change-type cell reaches p < 0.05 for that contrast. [`results.json`](results.json) holds the per-benchmark, per-change-type, and per-prompt outcomes for all three contrasts.

## Turn-2 process behavior

A4's second turn usually restarts a single `Planning`, `Translating`, and `Reviewing` cycle with regenerated goals, while A6 runs its fixed cycle without regenerating goals. The table counts completed runs. A turn-2 event is any trace event absent from the saved turn-1 trace.

| Measure                              |  A4 |  A6 |
| ------------------------------------ | --: | --: |
| Completed runs                       |  59 |  60 |
| Turn 2 switches to `Planning`        |  57 |  52 |
| Turn 2 records `goal_regenerated`    |  33 |   7 |
| Turn 2 delegates a `Planning` role   |  57 |  53 |
| Turn 2 records no trace events       |   0 |   6 |
| Turn-2 sequence is exactly one cycle |  41 |  37 |

Goal regeneration in A4 shows no association with the A4 versus A6 outcome: A4 wins 11, loses 11, and ties 11 of the 33 prompts with regeneration, and wins 7, loses 8, and ties 11 of the 26 prompts without it.

## Completion and deviations from the plan

Every condition completed all 60 prompts except A4, which completed 59. A4's run on writingbench-0559 failed turn-1 trace validation twice, so every A4 contrast covers 59 prompts. The following decisions differ from, or add to, the pre-specified plan:

- **Output budget.** After the smoke test showed second turns approaching the single-turn cap, the shared output budget for a two-turn run was doubled to 128,000 tokens before the full run. The smoke runs were therefore excluded, and all 60 prompts were regenerated.
- **Reruns.** Each run that failed turn-1 validation was rerun once, in every condition. This applied to one A4 run, three A6 runs, and six A1 runs. Every rerun completed except A4 writingbench-0559. Container starts that failed for lack of host disk space made no model calls and were re-queued.
- **Turn-2 trace split.** Some sessions rewrote their trace file during turn 2, so turn-2 events are identified by absence from the turn-1 copy rather than by position. All 119 traces retain every turn-1 event.
- **A1.** A1 was added because A4, A6, and A2 finished before the pre-specified 03:00 JST threshold. The A4 versus A1 contrast is an additional exploratory comparison outside the two pre-specified contrasts.

## Limitations

The experiment is exploratory, uses one generation per prompt and condition, and applies no multiplicity correction. The generator `gpt-5.6-luna` and the judge share the GPT family, and a different judge family could disagree. One model wrote the mid-task changes, and they may not represent real revision requests. Each change arrives after a complete first version, so the design tests revision of a finished document rather than a change during drafting.
