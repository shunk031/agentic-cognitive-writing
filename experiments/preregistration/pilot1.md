# Pilot 1 preregistration: process selection after a requirement change

Pilot 1 decides whether Agentic CogWriter's `Monitor` preserves untargeted content after a mid-composition requirement change better than a fixed `Planning`, `Translating`, `Reviewing` cycle, without incorporating the change less often or breaking more requirements. The pilot runs A4 `Agentic CogWriter`, A6 `Fixed-order`, and A6s, which is A6 plus a two-sentence skip rule, twice on each of the 14 Stage 0 items, 84 two-turn runs in all. The decision is GO only when G1, A4 preserves more than A6, and G2, A4 is not worse than A6 and A6s on incorporation and breaks, both pass on the exact sign-flip tests fixed below. G3, A4 against A6s, decides how the claim is worded, not whether the pilot passes.

Every rule here is fixed before any Pilot 1 run. The analysis code is [`pilot1.py`](../src/agentic_cogwriter/analysis/pilot1.py), whose constants carry the margins and levels stated below.

## Claim under test

After a mid-composition requirement change, Agentic CogWriter's `Monitor` selects only the processes the change needs, so it incorporates the change while preserving content the change does not target, whereas a fixed `Planning`, `Translating`, `Reviewing` cycle rewrites untargeted content.

Prior work motivates the measure: in **Mr Dre**[^1], deep-research agents revising a report regressed on 16% to 27% of content they had already covered.

## Design

The three arms share the generator, the role skills, the runner, and the turn-2 change block; only the `Monitor` skill, and so the invocation that follows the change block, differs.

| Arm | `Monitor` skill                                                                                      | Change from the integration branch |
| --- | ---------------------------------------------------------------------------------------------------- | ---------------------------------- |
| A4  | [`agentic-cog-writer`](../../plugin/skills/agentic-cog-writer/SKILL.md)                              | none                               |
| A6  | [`cognitive-writing-fixed-order`](../plugin/skills/cognitive-writing-fixed-order/SKILL.md)           | none                               |
| A6s | [`cognitive-writing-fixed-order-skip`](../plugin/skills/cognitive-writing-fixed-order-skip/SKILL.md) | A6 plus the skip rule              |

**A6s.** The A6s skill differs from the A6 skill only in its name and in two sentences appended to step 2: "Skip `Translating` when the latest `Planning` report added no goal that lacks prose. The pass then continues with `Reviewing`." The rule restates as a fixed rule the selection the `Monitor` showed in Stage 0, where 9 of 14 A4 runs ran no turn-2 `Translating`. The condition wrapper is [`a6s_plugin.toml`](../conditions/a6s_plugin.toml), and the test `test_skip_skill_is_the_fixed_order_skill_with_the_pilot1_rule` in [`test_runner_contracts.py`](../tests/test_runner_contracts.py) pins the exact difference from A6, so the text is frozen with this preregistration.

**Items.** The items are the 14 Stage 0 items and no others: the 8 `term` and 6 `remove` items that [`requirement_change.py`](../src/agentic_cogwriter/requirement_change.py) generates from 8 DoLoMiTes[^2] prompts of the non-evaluation smoke pool. A `term` change forbids a required word in one section and requires another; a `remove` change retires one section. Stage 0 used these items only for a diagnostic of unedited A4, one run each, and no skill was edited after Stage 0. In Stage 0, all 14 runs passed the fidelity gate, 13 incorporated the change, none broke an unchanged requirement that had passed turn 1, and 3 of the 12 multi-section runs changed an untargeted section. Two `term` items, `dolomites-296.term` and `dolomites-626.term`, have a single section, so they have no untargeted section and enter only the comparisons of incorporation, breaks, and cost.

**Runs.** Each arm runs each item twice, with the runner's `--followup-file` second turn, giving 28 runs per arm. The three arms' runs interleave in one batch, so time-varying service behavior affects all arms alike. A run that fails before the generator starts, such as a container start without disk space, is re-queued; a run that starts is never rerun.

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

Comparisons are paired by item: an arm's value for an item is the mean of its gate-passing runs, and the item difference is A4's value minus the other arm's. An item enters a comparison when both arms have a value. The statistic is the exact sign-flip permutation test of the mean item difference: the differences minus the null value are given every one of the 2^n sign assignments, and the p-value is the share of assignments whose sum is at least as extreme as the observed one. The sign-flip test is chosen over a paired t interval because U is mostly zero for A4 in Stage 0, which a normal approximation fits poorly.

## Gates and decision

Two hard gates decide GO. A minimum item count applies to every gate comparison; a comparison below it fails.

- **G1, A4 preserves more than A6.** Either U is lower for A4 by at least 0.15, with a two-sided p below 0.025 at a null of zero, or S is higher for A4 by at least 0.05, with the same test. Each route uses half of a 0.05 level, so the family of two is Bonferroni-corrected. G1 needs at least 10 of the 12 multi-section items.
- **G2, A4 is not worse than A6 or A6s.** Against each of A6 and A6s, a one-sided test at p below 0.025 rejects that C is lower for A4 by 0.15 or more, and another rejects that B is higher for A4 by 0.05 or more. All four tests must reject. G2 needs at least 12 of the 14 items. A difference of 0.15 in C is about two of 14 items losing the change.

**Decision.** GO when G1 and G2 pass; otherwise NO-GO.

**G3, A4 against A6s.** G3 is reported descriptively for U, S, and both parts of K, with item means and two-sided p-values, and it fixes the claim's wording. Its outcome applies the G1 rule in both directions:

| G3 outcome       | Rule                                             | Claim after a GO                                                                                                        |
| ---------------- | ------------------------------------------------ | ----------------------------------------------------------------------------------------------------------------------- |
| `monitor_better` | A4 passes the G1 rule against A6s                | The claim as stated, including that the LLM `Monitor` preserves more than a fixed skip rule                             |
| `no_difference`  | Neither arm passes the G1 rule against the other | Process selection, whether by the LLM `Monitor` or a rule, preserves content; the LLM `Monitor` is not claimed superior |
| `rule_better`    | A6s passes the G1 rule against A4                | Process selection preserves content, and a fixed rule preserves more than the LLM `Monitor`; the paper says so          |

K changes only cost statements: the paper may state that A4's turn 2 costs less than A6's or A6s's only when A4's mean item value is lower with a two-sided p below 0.05, and otherwise makes no cost claim.

## Power

The simulated power of G1 on U alone is 0.76 when each A6 run rewrites every untargeted section with probability 0.5, and falls below 0.2 when that probability is 0.3. The estimate ignores the S route, so G1's power is at least this.

| A6 rewrite probability per run |   0.2 |   0.3 |   0.4 |   0.5 |   0.7 |
| ------------------------------ | ----: | ----: | ----: | ----: | ----: |
| G1 passes on U                 | 0.035 | 0.176 | 0.469 | 0.764 | 0.993 |

The simulation makes these assumptions:

- 12 multi-section items with 2 runs per arm, analyzed by the G1 rule on U;
- each A4 run draws U from Stage 0's 12 multi-section A4 runs: nine runs at 0, one at 1/3, and two at 1/2, a mean of 0.11;
- each A6 run either rewrites every untargeted section (U = 1) or none (U = 0), as the two A6 runs of the follow-up smoke did on one `remove` item, one each; that smoke gives the central rate of 0.5, and the September-era smoke recorded rewriting but no per-run rate;
- runs and items are independent, with no item effect; a positive item effect shared by the arms would raise the power;
- 2000 simulations with seed 20261029.

```bash
uv run --package agentic-cogwriter python -m agentic_cogwriter.analysis.pilot1 power --a6-rewrite 0.2 0.3 0.4 0.5 0.7
```

## Consequences

**GO.** The claim, worded by G3, goes to the author for the scored study. These 14 items are spent: the scored study uses other items, such as the `add` and `bullets` classes and new prompts, generated before any scored run.

**NO-GO.** The paper becomes a benchmark-and-analysis paper: the requirement-change testbed and its incorporation, break, and locality measures, with these results reported as they are. No skill is tuned on these items, and the pilot is not rerun with edited skills.

## Fidelity requirements

A run counts only when it meets every requirement below; the analysis reports each excluded run with its reasons.

- **Both gates.** The run's turn-1 fidelity gate and its final gate pass, which the manifest records as a scorable `fidelity_gate`.
- **Turn-2 input.** The turn-2 message and the `task.md` change block are those of the runner as merged in [shunk031/agentic-cognitive-writing#182](https://github.com/shunk031/agentic-cognitive-writing/pull/182): the same change block for every arm, followed by the arm's own turn-1 invocation. The manifest's `followup` hashes are kept.
- **Neutral output roots.** No output root or other path the generator can see names an item, a prompt, or a change class; an earlier batch leaked the change class through a directory name. Output roots carry opaque labels such as `p1-01`, and the map from run to item is kept outside every output root.
- **Checker exposure scan.** The `check` command's scan passes: the workspace holds no copy of the checker module or the items file, and the harness records name neither them, the items file's hash, nor an item id. A run that fails the scan is excluded.
- **Same configuration.** All arms use one model, one reasoning effort, one Codex version, and one commit of the integration branch that contains this preregistration.

Pilot 1 is valid only when at least 26 of 28 runs per arm count. An invalid pilot is neither GO nor NO-GO: an implementation defect is fixed from the harness records, never from outputs, and the whole pilot is run again with unchanged skills.

## Procedure

1. Generate the items outside every output root; the generator is seeded, so the items equal Stage 0's.
2. Run each arm, item, and replicate with `--manifest` set to the generated `manifest.jsonl` and `--followup-file` set to the item's `followup/<item-id>.txt`.
3. Check each run with `requirement_change check`, writing each result outside every output root.
4. Compute the statistics:

   ```bash
   uv run --package agentic-cogwriter python -m agentic_cogwriter.analysis.pilot1 analyze --checks /path/to/checks
   ```

The report follows the reporting rule of the [handoff](../HANDOFF.md#working-rules): the decision and each gate first, unfavorable results first, then every excluded run.

[^1]: Bingsen Chen, Boyan Li, Ping Nie, Yuyu Zhang, Xi Ye, and Chen Zhao. "Beyond Single-shot Writing: Deep Research Agents are Unreliable at Multi-turn Report Revision." Proceedings of the 64th Annual Meeting of the Association for Computational Linguistics (Volume 1: Long Papers), 2026. https://doi.org/10.18653/v1/2026.acl-long.609
[^2]: Chaitanya Malaviya, Priyanka Agrawal, Kuzman Ganchev, Pranesh Srinivasan, Fantine Huot, Jonathan Berant, Mark Yatskar, Dipanjan Das, Mirella Lapata, and Chris Alberti. "DOLOMITES: Domain-Specific Long-Form Methodical Tasks." Transactions of the Association for Computational Linguistics, 2025. https://doi.org/10.1162/tacl_a_00727
