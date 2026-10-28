# Pilot 1 preregistration: process selection after a requirement change

Pilot 1 decides whether Agentic CogWriter's `Monitor` preserves untargeted content after a mid-composition requirement change better than a fixed `Planning`, `Translating`, `Reviewing` cycle, without incorporating the change less often or breaking more requirements. The pilot runs A4 `Agentic CogWriter`, A6 `Fixed-order`, and A6s, which is A6 plus a two-sentence skip rule, twice on each of the 14 Stage 0 items, 84 two-turn runs in all. The decision is GO only when two gates pass: G1, A4 preserves more than A6 by a margin on an exact sign-flip test, and G2, A4's incorporation and break rates are within stated margins of A6's and A6s's. G3, A4 against A6s, decides how the claim is worded, not whether the pilot passes.

The pilot is small and its evidence is weak in one direction. No measurement yet shows A4 preserving more than `Fixed-order`, and A6's rate of rewriting untargeted sections under the current checker is unknown. G1 has 80% power only if A6 rewrites untargeted sections in about half of its runs or more, so a NO-GO at this size says to redesign before scaling the claim, not that the claim is false.

Every rule here is fixed before any Pilot 1 run. The margins, the A6s rule, and the power assumptions were set after seeing Stage 0 data on these same items; Stage 0 runs are not pilot runs and enter no pilot statistic. The analysis code is [`pilot1.py`](../src/agentic_cogwriter/analysis/pilot1.py), whose constants carry the margins, item list, skill hashes, and seed stated below.

## Claim under test

After a mid-composition requirement change, Agentic CogWriter's `Monitor` selects only the processes the change needs, so it incorporates the change while preserving content the change does not target, whereas a fixed `Planning`, `Translating`, `Reviewing` cycle rewrites untargeted content.

Prior work motivates the measure: in **Mr Dre**[^1], deep-research agents revising a report regressed on 16% to 27% of content they had already covered.

## Prior evidence

No earlier measurement favors A4 on preservation, and none measures A6 with the current checker on a run that followed its procedure more than once.

- **Requirement-change runs of 2026-10-12.** The [handoff's Evidence section](../HANDOFF.md#evidence) records that an uncommitted re-analysis of these runs found turn-2 process calls, tokens, and edit locality not lower for A4 than for `Fixed-order`. The runs used the executed study's skills and a retyped deliverable, the re-analysis measured paragraphs rather than sections, and it is not reproducible from the repository, so it informs no number here.
- **Follow-up smoke.** Two A4 and two A6 runs of `dolomites-673.remove` used the plugin at [the smoke's commit](https://github.com/shunk031/agentic-cognitive-writing/commit/f7722475b309aa6c9e9f020a00e9a2395bcd11e3). The first run of each arm, A4 `0ab77414` and A6 `55f78d72`, had no turn-2 product clause and did not follow its procedure, so both are excluded from every rate. The two runs that followed their procedure, A4 `7ceb7743` and A6 `8d97acb9`, each changed every untargeted section (U = 1.0); A6's S was about 0.70. One run per arm estimates no rate.
- **Stage 0.** Unedited A4 ran once on each of the 14 items. All 14 runs passed the fidelity gate, 13 incorporated the change, none broke an unchanged requirement that had passed turn 1, and 3 of the 12 multi-section runs changed an untargeted section, a mean U of 0.11 and a mean S of 0.98. Turn 2 ran no `Translating` in 9 runs and a full `Planning`, `Translating`, `Reviewing` sequence in 5, and its tokens about equaled turn 1's.
- **Mechanism report.** This preregistration's change to the [mechanism report](../src/agentic_cogwriter/analysis/mechanism.py) counts `Reviewing` followed by `Planning`, and a goal replacement after review, only within one turn. On Stage 0's two-turn runs the change lowers `reviewing_then_planning` from 14 of 14 to 2 of 14 and `goal_replaced_after_review` from 13 of 14 to 2 of 14, because the earlier rule counted a turn-2 `Planning` that answered the change as following turn 1's last `Reviewing`.

## Design

The three arms share the generator, the role skills, the runner, and the turn-2 change block; only the `Monitor` skill, and so the invocation that follows the change block, differs.

| Arm | `Monitor` skill                                                                                      | Change from the integration branch |
| --- | ---------------------------------------------------------------------------------------------------- | ---------------------------------- |
| A4  | [`agentic-cog-writer`](../../plugin/skills/agentic-cog-writer/SKILL.md)                              | none                               |
| A6  | [`cognitive-writing-fixed-order`](../plugin/skills/cognitive-writing-fixed-order/SKILL.md)           | none                               |
| A6s | [`cognitive-writing-fixed-order-skip`](../plugin/skills/cognitive-writing-fixed-order-skip/SKILL.md) | A6 plus the skip rule              |

**A6s.** The A6s skill differs from the A6 skill only in its name and in two sentences appended to step 2: "Skip `Translating` when the latest `Planning` report added no goal that lacks prose. The pass then continues with `Reviewing`." The rule restates as a fixed rule the selection the `Monitor` showed in Stage 0, where 9 of 14 A4 runs ran no turn-2 `Translating`. The condition wrapper is [`a6s_plugin.toml`](../conditions/a6s_plugin.toml), and the test `test_skip_skill_is_the_fixed_order_skill_with_the_pilot1_rule` in [`test_runner_contracts.py`](../tests/test_runner_contracts.py) pins the exact difference from A6.

**Items.** The items are the 14 Stage 0 items and no others: the 8 `term` and 6 `remove` items that [`requirement_change.py`](../src/agentic_cogwriter/requirement_change.py) generates from 8 DoLoMiTes[^2] prompts of the non-evaluation smoke pool. A `term` change forbids a required word in one section and requires another; a `remove` change retires one section. Stage 0 used these items for a diagnostic of unedited A4, and no skill of A4 or A6 was edited after it. Two `term` items, `dolomites-296.term` and `dolomites-626.term`, have a single section, so they have no untargeted section and enter only the comparisons of incorporation, breaks, and cost.

**Runs.** Each arm runs each item twice, with the runner's `--followup-file` second turn, giving 28 runs per arm. All 84 runs follow one seeded order, given under [Fidelity requirements](#fidelity-requirements), so time-varying service behavior affects all arms alike. A run that fails before the generator starts, such as a container start without disk space, is re-queued; a run that starts is never rerun.

## Measures

All measures are of turn 2 and come from the requirement-change checker or the harness records, never from a judge or from reading outputs.

| Measure | Definition per run                                                                            | Source                                                          |
| ------- | --------------------------------------------------------------------------------------------- | --------------------------------------------------------------- |
| U       | Share of untargeted sections whose whitespace-normalized body changed or vanished             | checker `locality`                                              |
| S       | Mean word-level `SequenceMatcher` ratio of untargeted section bodies, zero for a vanished one | checker `mean_similarity`                                       |
| B       | Share of the unchanged requirements that passed after turn 1 and fail after turn 2            | checker `break_rate`                                            |
| C       | 1 when every changed requirement passes after turn 2, else 0                                  | checker `incorporated`                                          |
| K       | Turn-2 `Monitor` delegations, and turn-2 all-thread total tokens                              | mechanism report; manifest `followup.rollout_token_usage.turn2` |

The checker module docstring defines sections, targets, and each requirement. A run without a value for a measure, such as U for a single-section item, is skipped for that measure.

## Analysis

Comparisons are paired by item: an arm's value for an item is the mean of its counted runs, and the item difference is A4's value minus the other arm's. An item enters a comparison when both arms have a value. The test is the exact two-sided sign-flip permutation test of the mean item difference: the differences are given every one of the 2^n sign assignments, and the p-value is the share of assignments whose sum is at least as large in absolute value as the observed one. The sign-flip test is chosen over a paired t interval because U is mostly zero for A4 in Stage 0, which a normal approximation fits poorly. Every contrast of every measure is reported with its item count, mean difference, and p-value; only G1 and G3 use the p-value.

## Gates and decision

Two hard gates decide GO. A minimum item count applies to every gate comparison; a comparison below it fails.

- **G1, A4 preserves more than A6.** Either U is lower for A4 by at least 0.15 with p below 0.025, or S is higher for A4 by at least 0.05 with p below 0.025. Each route uses half of a 0.05 level, so the family of two is Bonferroni-corrected. G1 needs at least 10 of the 12 multi-section items.
- **G2, A4 is not worse than A6 or A6s.** G2 is a point-estimate guard, not a test: against each of A6 and A6s, A4's mean C is at least the other arm's minus 0.15, and A4's mean B is at most the other arm's plus 0.05, each over at least 12 paired items. A difference of 0.15 in C is about two of 14 items losing the change. The sign-flip tests of C and B are reported only.

**Decision.** GO when G1 and G2 pass; otherwise NO-GO.

**G3, A4 against A6s.** G3 is reported for U, S, and both parts of K, and it fixes the claim's wording. Its outcome applies the G1 rule in both directions:

| G3 outcome       | Rule                                             | Claim after a GO                                                                                                        |
| ---------------- | ------------------------------------------------ | ----------------------------------------------------------------------------------------------------------------------- |
| `monitor_better` | A4 passes the G1 rule against A6s                | The claim as stated, including that the LLM `Monitor` preserves more than a fixed skip rule                             |
| `no_difference`  | Neither arm passes the G1 rule against the other | Process selection, whether by the LLM `Monitor` or a rule, preserves content; the LLM `Monitor` is not claimed superior |
| `rule_better`    | A6s passes the G1 rule against A4                | Process selection preserves content, and a fixed rule preserves more than the LLM `Monitor`; the paper says so          |

K changes only cost statements: the paper may state that A4's turn 2 costs less than A6's or A6s's only when A4's mean item value is lower with p below 0.05, and otherwise makes no cost claim.

## Power

Because A6's U is unknown, power is given over a grid of A6 means with no central value. G1 reaches 80% power at an A6 mean U of about 0.52, against A4's Stage 0 mean of 0.11, and GO reaches it at about 0.53 with no breaks and 0.56 at a 5% break rate. At a 10% break rate GO stays below 80% at every A6 mean, because G2 alone then passes only about 79% of the time.

| A6 mean U      | equal to A4 |   0.2 |   0.4 |   0.6 |   0.8 |
| -------------- | ----------: | ----: | ----: | ----: | ----: |
| G1             |       0.003 | 0.027 | 0.476 | 0.938 | 1.000 |
| GO, no breaks  |       0.003 | 0.027 | 0.466 | 0.919 | 0.981 |
| GO, 5% breaks  |       0.003 | 0.025 | 0.431 | 0.851 | 0.904 |
| GO, 10% breaks |       0.003 | 0.021 | 0.381 | 0.745 | 0.791 |

G2 passes in about 98%, 90%, and 79% of simulated pilots at break rates of 0, 5%, and 10%, whatever A6's U, because the arms are equal on C and B in every scenario. Two consequences follow. With equal arms, GO is a 0.3% false positive. With an A4 that truly preserves more, a NO-GO is still likely when A6 rewrites in fewer than about half of its runs, and G2 alone fails one pilot in five at a 10% break rate, so a NO-GO at this size is weak evidence against the claim.

The simulation makes these assumptions:

- 14 items, 12 of them multi-section, with 2 runs per arm, analyzed by the G1 and G2 rules with S absent, so G1 passes on U only and its power is a lower bound;
- each A4 and A6s run draws U from Stage 0's 12 multi-section A4 runs: nine runs at 0, one at 1/3, and two at 1/2, a mean of 0.11; under "equal to A4" each A6 run does too;
- otherwise each A6 run either changes every untargeted section (U = 1) or none (U = 0), so A6's mean U is the probability of a rewrite, as the one procedure-following A6 smoke run suggests; an A6 that changed part of the sections in every run would give a less variable U and more power at the same mean;
- every run in every arm misses the change with Stage 0's probability of 1/14 and breaks each of three unchanged requirements with the stated probability;
- runs and items are independent, with no item effect; a positive item effect shared by the arms would raise the power;
- 2000 simulations with seed 20261029 for each cell; finer grids give G1 0.798 at 0.51 and 0.816 at 0.52.

```bash
uv run --package agentic-cogwriter python -m agentic_cogwriter.analysis.pilot1 power --a6-u equal 0.2 0.4 0.6 0.8 --break-rate 0 0.05 0.1
```

## Consequences

**GO.** The claim, worded by G3, goes to the author for the scored study. These 14 items are spent: the scored study uses other items, such as the `add` and `bullets` classes and new prompts, generated before any scored run.

**NO-GO.** The claim is not scaled without a redesign. A NO-GO is not an irreversible switch of the paper's direction: the author decides between redesigning the method and test and the benchmark-and-analysis paper, which reports the requirement-change testbed and its incorporation, break, and locality measures with these results as they are. Either way, no skill is tuned on these items.

## Fidelity requirements

A run counts only when it meets every requirement below. The analysis machine-checks each one from the run map and the run records and reports each excluded run with all its reasons; the module docstring of [`pilot1.py`](../src/agentic_cogwriter/analysis/pilot1.py) holds the exact rules.

- **Run map.** A JSON Lines map kept outside every output root lists all 84 expected runs, each with its arm, item, replicate, run directory, and checker output. The analysis refuses a map that misses or repeats an expected run or names one run directory twice. A run without a checker output, because the exposure scan refused it or the run crashed, is excluded with the reason recorded in the map.
- **Both gates.** The run's turn-1 fidelity gate and its final gate pass, which the manifest records as a scorable `fidelity_gate`.
- **Turn-2 input.** The turn-2 message and the `task.md` change block are those of the runner as merged in [shunk031/agentic-cognitive-writing#182](https://github.com/shunk031/agentic-cognitive-writing/pull/182). The analysis checks that `followup.txt` has the manifest's message hash, opens with the item's change block, and continues with the arm's own skill invocation, and that the workspace `task.md` has the manifest's task hash and is the staged task followed by the same block.
- **Resume sandbox.** The resume turn keeps the workspace-write sandbox, as [shunk031/agentic-cognitive-writing#180](https://github.com/shunk031/agentic-cognitive-writing/pull/180) enforces; the analysis checks the manifest's resume arguments.
- **Neutral output roots.** No output root or other path the generator can see names an item, a prompt, or a change class; an earlier batch leaked the change class through a directory name. The analysis excludes a run whose directory has a component naming a prompt or a change class.
- **Checker exposure scan.** The `check` command's scan passes: the workspace holds no copy of the checker module or the items file, and the harness records name neither them, the items file's hash, nor an item id.
- **Pinned skills.** The staged skills have these SHA-256 hashes, which `SKILL_HASHES` in the analysis pins:

  | Skill                                | SHA-256                                                            |
  | ------------------------------------ | ------------------------------------------------------------------ |
  | `agentic-cog-writer`                 | `f3fd53e017c993b56d660da7b577b6b3f4d43da0078caf24cbd1397dc290f543` |
  | `cognitive-writing-fixed-order`      | `74f90030fcd91d8f4e0816b01fc0eea603ca15a4902a6ca92a58bd17f32df26f` |
  | `cognitive-writing-fixed-order-skip` | `1298588eca30dbd7652abdda292c165f8268ed947e39be4647d1bf1556b7e4f7` |
  | `planning`                           | `806703406b38adf238e18b3df5fe085537f8d66735526a673bc3ebdafeffa3fc` |
  | `translating`                        | `e8b22453cda82552c15cf790dbe554461f7b21bae485742ace8ed20883276a55` |
  | `reviewing`                          | `1eaf68966c667daee6ac5b73a7979b66f245972d21ac8fea409304532b64a9dd` |

- **Pinned run commit and configuration.** Every run uses the `rerun-arr2027` commit that merges this preregistration, which the report names and passes to the analysis; every manifest records it as both plugin commits. All runs share one generator model, one reasoning effort, and one Codex version. The analysis stops otherwise.
- **Run order.** The `schedule` command shuffles the 84 runs with seed 20261029 and labels them `p1-01` to `p1-84`. Each run gets its own output root under its label, and four runs execute at a time, each started in schedule order as a slot frees.

Pilot 1 is valid only when at least 26 of 28 runs per arm count. An invalid pilot is neither GO nor NO-GO: an implementation defect is fixed from the harness records, never from outputs, and the whole pilot is run again with unchanged skills.

## Procedure

1. Generate the items outside every output root; the generator is seeded, so the items equal Stage 0's.
2. Print the run order and start the run map from it:

   ```bash
   uv run --package agentic-cogwriter python -m agentic_cogwriter.analysis.pilot1 schedule
   ```

3. Run each scheduled run in its own output root with `--manifest` set to the generated `manifest.jsonl` and `--followup-file` set to the item's `followup/<item-id>.txt`, four at a time.
4. Check each run with `requirement_change check`, writing each result outside every output root, and record each result path or refusal in the run map.
5. Compute the statistics:

   ```bash
   uv run --package agentic-cogwriter python -m agentic_cogwriter.analysis.pilot1 analyze --run-map /path/to/run-map.jsonl --items /path/to/items/items.json --commit <run commit>
   ```

The report follows the reporting rule of the [handoff](../HANDOFF.md#working-rules): the decision and each gate first, unfavorable results first, then every excluded run.

[^1]: Bingsen Chen, Boyan Li, Ping Nie, Yuyu Zhang, Xi Ye, and Chen Zhao. "Beyond Single-shot Writing: Deep Research Agents are Unreliable at Multi-turn Report Revision." Proceedings of the 64th Annual Meeting of the Association for Computational Linguistics (Volume 1: Long Papers), 2026. https://doi.org/10.18653/v1/2026.acl-long.609
[^2]: Chaitanya Malaviya, Priyanka Agrawal, Kuzman Ganchev, Pranesh Srinivasan, Fantine Huot, Jonathan Berant, Mark Yatskar, Dipanjan Das, Mirella Lapata, and Chris Alberti. "DOLOMITES: Domain-Specific Long-Form Methodical Tasks." Transactions of the Association for Computational Linguistics, 2025. https://doi.org/10.1162/tacl_a_00727
