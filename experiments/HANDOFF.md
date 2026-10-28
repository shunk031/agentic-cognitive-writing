# Experiment redesign handoff

This file records the state, decisions, and working rules for the CogWriter experiment redesign, so that a new session can continue without the earlier conversation. Update this file whenever a decision or milestone changes.

## Status

No tested setting shows A4 `Agentic CogWriter` better than A6 `Fixed-order` on quality, work, or edit locality. The preregistered Pilot 1 ended NO-GO, and its premise, that a fixed cycle rewrites content a requirement change does not target, does not hold for the rebuilt plugin. The [Evidence](#evidence) section gives each measurement condition, and the paper's [code-to-system map](../paper/sec/09_prompt_configuration.tex) names the condition codes.

- **Pilot 1: NO-GO.** On non-evaluation requirement-change items, A4 and `Fixed-order` changed a mean 0.174 and 0.160 of untargeted sections, a difference of +0.014 with p = 0.969, and kept a mean untargeted similarity of 0.945 and 0.991, a difference of -0.046 with p = 0.992. Neither preservation route of the G1 gate passed. Incorporation was 0.964 in both arms, no arm broke a requirement, and turn-2 tokens were 441,962 and 510,400 with p = 0.255.
- **Outcome: not met.** No scored run of the rebuilt arms exists. In the two-turn requirement-change runs of 2026-10-12, which used the executed study's skills after [shunk031/agentic-cognitive-writing#139](https://github.com/shunk031/agentic-cognitive-writing/pull/139) removed their instructions to ask or tell the user, A4 against `Fixed-order` gave 18 wins, 19 losses, and 22 ties.
- **Mechanism: not met.** In the 24 gate-passing runs of the rebuilt A4 on ordinary non-evaluation prompts, no run returned from `Reviewing` to `Planning` and none replaced a goal, against the executed study's 4.1% and 0.5%. In the 14 Stage 0 runs with a requirement change, 2 returned from `Reviewing` to `Planning` within a turn and 2 replaced a goal after review.
- **Cost against a skip rule.** Against A6s, which is `Fixed-order` plus a rule that skips `Translating` when `Planning` added no goal that lacks prose, A4 used 0.79 fewer turn-2 delegations, with p = 0.035, and 134,790 fewer turn-2 tokens, with p = 0.042.
- **Fidelity: met for the ordinary-prompt and Pilot 1 setups.** Pilot 1 counted 27, 26, and 28 of 28 runs for A4, `Fixed-order`, and A6s, above the preregistered minimum of 26, and excluded three with stated reasons. The current gate, re-run on copies of 27 runs of the rebuilt A4 on ordinary non-evaluation prompts, passes 24 and rejects three. Fidelity is a property of the implementation, not support for the paper's claim.

## Pending decision

Under the NO-GO consequence of the Pilot 1 preregistration, the author decides between two directions:

- **Redesign.** Redesign the method and its test before scaling the claim.
- **Benchmark and analysis.** Write a benchmark-and-analysis paper that reports the requirement-change testbed and its incorporation, break, and locality measures, with these results as they are.

No scored run happens before that decision, and no skill is tuned on the 14 Pilot 1 items.

A survey of prior work found no accepted paper that isolates an LLM-chosen order of planning, drafting, and reviewing against a fixed order under the same generator. The nearest work is WebThinker[^1], WriteHERE[^2], and IS-CoT[^3]. The method's name also risks confusion with CogWriter[^4].

## Current state

- **Target.** The submission target is the next ARR cycle. The [ARR dates page](https://aclrollingreview.org/dates) lists no exact deadline after the October 2026 cycle, whose deadline of October 12, 2026 has passed. The next published entry is the ACL 2027 final ARR submission date, given as "January, 2027" with no day yet. Plan to that date, and move the plan earlier if a December 2026 cycle is published.
- **Main.** Main was reverted to its state before the redesign through [shunk031/agentic-cognitive-writing#179](https://github.com/shunk031/agentic-cognitive-writing/pull/179), by the author's decision that unfinished work must not be in main. All redesign work lives on the integration branch `rerun-arr2027`.
- **Artifact.** The skills-only plugin under [`plugin/`](../plugin/) was rebuilt through [shunk031/agentic-cognitive-writing#148](https://github.com/shunk031/agentic-cognitive-writing/pull/148), [shunk031/agentic-cognitive-writing#150](https://github.com/shunk031/agentic-cognitive-writing/pull/150), and [shunk031/agentic-cognitive-writing#151](https://github.com/shunk031/agentic-cognitive-writing/pull/151), and is on the integration branch only. The `Monitor` delegates to fresh `Planning`, `Translating`, and `Reviewing` agents with fixed scopes and writes only `history.md`. The Planner replaces goals that conflict with the task. The Reviewer corrects existing prose and reports missing goals or sections. A goal covers a requirement only if the goal names the requirement's section.
- **Runtime branch.** The `cw` runtime branch from the earlier redesign (`cogwriter-cw`) is closed by the author's decision; the rebuilt skills-only plugin is the only artifact. The branch stays for reference.
- **Rebuilt conditions.** The integration branch holds the rebuilt A4, the ablations A5 `No-goals`, A6, A7 `Single-writer`, and A8 `Single-context`, and the baselines A2 `Staged`, A3 `Task-planning`, and B1 `Exploratory-1`, the paper's CogWriter-style exploratory baseline. A1 `Single-pass` keeps its skill, because its final response is its deliverable. Token accounting is not yet rebuilt.
- **Paper build.** The A5 rename breaks the paper build on `rerun-arr2027`, because [`09_prompt_configuration.tex`](../paper/sec/09_prompt_configuration.tex) still displays the A5 skill under its removed path.
- **Runner.** The runner isolates every Codex child's HOME, and the fidelity gate rejects skill reads outside the per-run Codex home; a relative read after a `cd` is a known limit of the gate. The scored output is `draft.md` itself for every draft-product condition, through [shunk031/agentic-cognitive-writing#156](https://github.com/shunk031/agentic-cognitive-writing/pull/156). The Claude Code invocation path is out of scope under [D14](#decisions).
- **Rebuild pull requests.** These pull requests are merged into the integration branch:
  - **Child input.** [shunk031/agentic-cognitive-writing#165](https://github.com/shunk031/agentic-cognitive-writing/pull/165) starts the generator child with stdin closed.
  - **Mechanism report.** [shunk031/agentic-cognitive-writing#166](https://github.com/shunk031/agentic-cognitive-writing/pull/166) reports mechanisms from Codex harness records, and [shunk031/agentic-cognitive-writing#168](https://github.com/shunk031/agentic-cognitive-writing/pull/168) bounds unknown delegation starts by ended delegations.
  - **Output language.** [shunk031/agentic-cognitive-writing#167](https://github.com/shunk031/agentic-cognitive-writing/pull/167) states the manifest's output language in every condition, and [shunk031/agentic-cognitive-writing#169](https://github.com/shunk031/agentic-cognitive-writing/pull/169) counts Latin words in the language check.
  - **Gate checks.** [shunk031/agentic-cognitive-writing#170](https://github.com/shunk031/agentic-cognitive-writing/pull/170) seeds the `Monitor` history and closes two fidelity gate gaps, and [shunk031/agentic-cognitive-writing#171](https://github.com/shunk031/agentic-cognitive-writing/pull/171) catches bundled in-place switches and variable write targets.
  - **A7.** [shunk031/agentic-cognitive-writing#172](https://github.com/shunk031/agentic-cognitive-writing/pull/172) rebuilds A7 as the single-context skill with one-paragraph `Translating` steps.
  - **A2.** [shunk031/agentic-cognitive-writing#173](https://github.com/shunk031/agentic-cognitive-writing/pull/173) rebuilds A2 to write each stage and score `draft.md`.
  - **A3.** [shunk031/agentic-cognitive-writing#174](https://github.com/shunk031/agentic-cognitive-writing/pull/174) rebuilds A3 with closed skill-reading task agents.
  - **B1.** [shunk031/agentic-cognitive-writing#175](https://github.com/shunk031/agentic-cognitive-writing/pull/175) rebuilds B1 with closed skill-reading planning and segment agents.
  - **Construct checks.** [shunk031/agentic-cognitive-writing#177](https://github.com/shunk031/agentic-cognitive-writing/pull/177) skips patch text in skill reads, checks the A2 stages, and counts A7 steps.
- **Requirement-change testbed.** The integration branch holds the follow-up turn in the same Codex session from [shunk031/agentic-cognitive-writing#182](https://github.com/shunk031/agentic-cognitive-writing/pull/182), the change generator and two-turn checkers from [shunk031/agentic-cognitive-writing#183](https://github.com/shunk031/agentic-cognitive-writing/pull/183), the Pilot 1 preregistration and analysis from [shunk031/agentic-cognitive-writing#184](https://github.com/shunk031/agentic-cognitive-writing/pull/184), and the resume turn's workspace-write sandbox from [shunk031/agentic-cognitive-writing#180](https://github.com/shunk031/agentic-cognitive-writing/pull/180).
- **Fidelity notes.** A `Monitor` occasionally mistypes a child id in `close_agent` and leaves the child open, and one `Monitor` edited `task.md`; each case excluded a Pilot 1 run.
- **On hold.** The B2 `Exploratory-2` rebuild, [shunk031/agentic-cognitive-writing#176](https://github.com/shunk031/agentic-cognitive-writing/pull/176), and the A3 follow-up, [shunk031/agentic-cognitive-writing#178](https://github.com/shunk031/agentic-cognitive-writing/pull/178), are paused while the claim is decided.

## Evidence

Every result comes from one model and one reasoning effort, and no result shows the method ahead of `Fixed-order`. Each setting has its own measurement condition:

- **Pilot 1.** A4, `Fixed-order`, and A6s, two runs each on 14 items, as the [Pilot 1 preregistration](preregistration/pilot1.md) from [shunk031/agentic-cognitive-writing#184](https://github.com/shunk031/agentic-cognitive-writing/pull/184) fixes. Each item is a non-evaluation DoLoMiTes[^5] smoke-pool prompt with one mid-composition requirement change, a term swap or a section removal. The requirement-change checker and the harness records give every measure, and each comparison is an exact sign-flip test over item means. Three runs were excluded: an A6 `Monitor` wrote `task.md`, and an A4 and an A6 `Monitor` each left a child open after mistyping its id. An independent re-computation from the raw records found no discrepancy. The run records are outside the repository, and the preregistration's analysis command computes the statistics from them.
- **Stage 0.** The unedited A4, one run on each of the same 14 items, as a diagnostic that enters no Pilot 1 statistic. The `Reviewing` counts use the same-turn rule that [shunk031/agentic-cognitive-writing#184](https://github.com/shunk031/agentic-cognitive-writing/pull/184) added to the mechanism report.

- **Ordinary prompts.** The rebuilt A4, run through the runner on 27 ordinary non-evaluation prompts and measured from harness records with the mechanism report. The runs used the runner as of [shunk031/agentic-cognitive-writing#165](https://github.com/shunk031/agentic-cognitive-writing/pull/165), before [shunk031/agentic-cognitive-writing#167](https://github.com/shunk031/agentic-cognitive-writing/pull/167) stated the output language and before [shunk031/agentic-cognitive-writing#170](https://github.com/shunk031/agentic-cognitive-writing/pull/170) seeded `history.md` and made `Monitor` shell writes a gate rejection. The gate counts come from the gate after [shunk031/agentic-cognitive-writing#170](https://github.com/shunk031/agentic-cognitive-writing/pull/170), re-run on copies of the runs: it rejects two runs for `Monitor` writes to `goals.md` or `draft.md` and one for a `Monitor` shell `touch` of the state files. The gate at run time rejected a different third run, for a failed skill read that the later gate skips.
- **Seeded defect.** The A4 skills at the head of [shunk031/agentic-cognitive-writing#151](https://github.com/shunk031/agentic-cognitive-writing/pull/151), which equal those on `rerun-arr2027`, run directly from seeded states rather than through the runner and gate, on ten DoLoMiTes prompts with one section removed, ten runs each. The [shunk031/agentic-cognitive-writing#151](https://github.com/shunk031/agentic-cognitive-writing/pull/151) body and its "All runs" comments hold every run table.
- **Requirement change.** Runs on 2026-10-12 of the executed study's A4 and `Fixed-order` skills as revised by [shunk031/agentic-cognitive-writing#139](https://github.com/shunk031/agentic-cognitive-writing/pull/139), which replaced their instructions to ask or tell the user with a fixed assignment; the role skills are unchanged, and the executed study's own runs used the earlier text. The runs cover 59 prompts with a second turn that changes the requirements, A4 against `Fixed-order`. The [revision-task results](https://github.com/shunk031/agentic-cognitive-writing/blob/92f497d12e73c5512eb1a898e8536458aae23e20/paper/results/revision-tasks/README.md) and [`results.json`](https://github.com/shunk031/agentic-cognitive-writing/blob/92f497d12e73c5512eb1a898e8536458aae23e20/paper/results/revision-tasks/results.json) on the `exp-revision-tasks` branch hold the counts. `Fixed-order` also returns to `Planning` by construction: A6 switches to `Planning` in 52 of its 60 turn-2 runs and delegates `Planning` in 53, so A4's 57 of 59 is not evidence of the mechanism.

| Setting | Measure | Result |
| --- | --- | --- |
| Pilot 1 | Mean share of untargeted sections changed, A4 and `Fixed-order` | 0.174 and 0.160; difference +0.014, p = 0.969 |
| Pilot 1 | Mean untargeted similarity, A4 and `Fixed-order` | 0.945 and 0.991; difference -0.046, p = 0.992 |
| Pilot 1 | Mean incorporation, A4 and `Fixed-order` | 0.964 and 0.964 |
| Pilot 1 | Broken requirements, every arm | 0 |
| Pilot 1 | Mean turn-2 tokens, A4 and `Fixed-order` | 441,962 and 510,400; p = 0.255 |
| Pilot 1 | Turn-2 delegations, A4 minus A6s | -0.79; p = 0.035 |
| Pilot 1 | Turn-2 tokens, A4 minus A6s | -134,790; p = 0.042 |
| Pilot 1 | Counted runs, A4, `Fixed-order`, and A6s | 27, 26, and 28 of 28 |
| Stage 0 | Runs passing the fidelity gate | 14 of 14 |
| Stage 0 | No turn-2 `Translating` | 9 of 14 |
| Stage 0 | Change incorporated | 13 of 14 |
| Stage 0 | Broken requirements | 0 |
| Stage 0 | `Reviewing` followed by `Planning` in the same turn | 2 of 14 |
| Stage 0 | Goal replacement after review | 2 of 14 |
| Ordinary prompts | Runs passing the fidelity gate | 24 of 27 |
| Ordinary prompts | `Planning` before the first `Translating` | 24 of 24 |
| Ordinary prompts | Exactly one `Planning` delegation | 24 of 24 |
| Ordinary prompts | Process sequence `Planning`, `Translating`, `Reviewing` | 22 of 24 |
| Ordinary prompts | Process sequence `Planning`, `Translating`, `Reviewing`, `Translating`, `Reviewing` | 2 of 24 |
| Ordinary prompts | `Reviewing` followed by `Planning` | 0 of 24 |
| Ordinary prompts | Goal replacement | 0 of 24 |
| Seeded defect | `Planning` before the removed section was written | 100 of 100 |
| Seeded defect | `Reviewing`, then `Planning`, before the section was written | 69 of 100 |
| Seeded defect | Gap found first by the first Reviewer | 54 of 100 |
| Seeded defect | Gap found first by the `Monitor`, planning first or stating the gap | 31 and 15 of 100 |
| Requirement change | Pairwise judgments, A4 against `Fixed-order` | 18 wins, 19 losses, 22 ties |
| Requirement change | Turn 2 switches to `Planning`, A4 and `Fixed-order` | 57 of 59 and 52 of 60 |

An uncommitted re-analysis of the requirement-change runs found that turn-2 process calls, tokens, and edit locality were not lower for A4 than for `Fixed-order`. That re-analysis is not reproducible from the repository.

## Measured defects of the executed study

Audits of the executed runs found the following defects. The redesign must not reintroduce any of them, and any future paper text must disclose them.

- **Forked context.** Monitor spawns used `fork_context:true`. Children inherited the Monitor prompt and often re-entered the Monitor workflow. The paper's "delegation fallback" count (218 of 886 A4 runs) mostly records such children, not the Monitor performing roles itself.
- **Role skills not loaded.** Codex never injected the role skills, which were staged outside its discovery paths. Children read their own role skill in only about 60% of delegations. In-context arms (A8, A12) read all three skills in nearly every run, so the A4-versus-A12 comparison is confounded.
- **Baselines also broken.** A3 and B1 forked children, left them unclosed, and hit the six-thread limit (570 of 923 A3 runs, 313 of 321 B1 runs). A3 almost never recursed; 98% of its graphs have depth 1.
- **Retyped deliverable.** The scored output was the agent's retyped final message, not `draft.md`. It was a condensed paraphrase in 5–12% of runs of the delegating arms, about 15% shorter, and the compression fell mostly on A4.
- **Token accounting.** Token counts were wrong in four ways:

  - only the parent thread was counted;
  - running totals were summed across resumed turns;
  - reasoning tokens were counted twice;
  - children ran outside the 64k budget.

  The "matched budget" and Self-Refine compute claims are therefore unsupported.

- **Output language.** No skill stated the output language. Drift on English WritingBench prompts with Chinese topics appeared in every condition, including single-shot.
- **Host skill leak.** In the first runner smoke of the rebuilt plugin, child agents read a personal writing skill from the host user's skills directory, outside the staged plugin. This contaminated the condition; the runner now isolates the child environment and the gate rejects such reads.

## Decisions

The redesign spec lists every decision with its source. The author-level decisions are:

- **Core method (D9).**
  - `Planning` writes checkable requirements taken from the task text only, never from judge rubrics.
  - `Reviewing` judges each requirement with quoted evidence and does not edit the draft.
  - The Monitor (the LLM) selects the next process and its scope from the verdicts.
  - `draft.md` is the single deliverable.
  - Process history comes from harness records, not from logs the model writes.
- **Open questions (D10).** Every open decision in the spec takes its recommended option. A7 Single-writer is defined by the paper's construct: A8 plus one paragraph per `Translating` step, generated from the same template as the other arms.
- **Working method (D11).** Keep prompts simple, with behavior that supports the paper's claims. Be thorough. Test small and iterate quickly.
- **Evaluation task sets (D12).** Re-select benchmark prompts by criteria fixed before any results: composition tasks with explicit requirements, without long-input summarization; also report the current hard100 subsets in full. Add LongGenBench-16K. Build a requirement-revision set with mid-draft requirement changes, seeded defects, and added checkable constraints, with a generator frozen before any scored run, separate dev and test splits, checkers hidden from the `Reviewer`, and a cross-family judge. Selection never uses observed win rates. The decisions record on the `cogwriter-cw` branch holds the full text.
- **Priority (D13).** First build a system that behaves as the paper describes; cost and the dataset protocol's open decisions wait until it works.
- **Harness (D14).** The rerun uses the Codex harness only. The Claude Code path records no tool or subagent events, so the fidelity gate rejects its runs as unverifiable; rebuilding that adapter is out of scope for the next ARR cycle.
- **Smoke pool erratum.** Six of the specified smoke prompts were A10 calibration prompts. The pool is now ranks 105–112 below the calibration set plus three disjoint WritingBench prompts, as the Errata section of the specification on the `cogwriter-cw` branch records.
- **Integration (author).** Merges into `rerun-arr2027` need no author approval.
- **Main (author).** Unfinished work must not be in main, so main was reverted to its state before the redesign through [shunk031/agentic-cognitive-writing#179](https://github.com/shunk031/agentic-cognitive-writing/pull/179).

## Working rules

- **Iteration target.** Iterate only on process fidelity and on whether mechanisms are exercised. Measure both from harness records, using non-evaluation prompts only. Never inspect or tune output quality. Freeze the design after the pilot and before any scored run.
- **Iteration record.** Record every iteration in its pull request body, with the metric and run IDs that motivated the change.
- **No ad hoc fixes.** Trace every change to the spec, a paper requirement, or an author decision. A change that alters a construct or an earlier decision goes to the author first.
- **Fidelity before interpretation.** Follow the "Experiment validity" section of [`AGENTS.md`](../AGENTS.md): check fidelity from harness logs before any scored run, and test an implementation defect first whenever a process metric looks surprising.
- **Fidelity gate.** Before any scored run, a mechanical check of the harness records rejects runs that show any measured defect of the executed study: a child spawned with inherited context, a role agent that did not read its own skill, a Monitor write outside `.writing/history.md`, an unclosed child or thread-limit hit, or a scored output other than `draft.md`. The gate is code in the runner, not instruction text.
- **Integration.** Rerun work accumulates on the integration branch `rerun-arr2027`. Each change is a pull request into that branch, reviewed by an independent reviewer, and merged by the orchestrator after the review accepts it. Progress reports to the author describe results and blockers, not pull request approvals.
- **Main.** Main receives only results that support the claim, with the author's approval.
- **Reporting.** Every report opens with each readiness criterion's status and the measurement condition behind it, with unfavorable results first. Implementation fidelity is reported separately and never presented as support for the paper's claim.
- **Public files.** Never put private paths, hostnames, or credentials in repository files.

## Readiness criteria

Results are ready for the paper when the rerun shows, from harness records, that the mechanisms the executed study failed to exercise now work, and the comparisons that failed in that study succeed on runs that pass the fidelity gate. These criteria are written for the current claim, and the [pending claim decision](#pending-decision) may replace them.

- **Fidelity.** Every scored run passes the fidelity gate. Rejected runs are reported with their reasons and excluded, never silently dropped. None of the measured defects recurs.
- **Mechanism.** In unseeded runs, each behavior the method claims clears a preregistered bar for the full system: the lower bound of the 95% interval of its rate lies above the executed study's rate. Over 886 complete A4 paths, the executed study recorded `Reviewing` followed by renewed `Planning` in 4.1% and an accepted goal replacement in 0.5%, as [Table 6](../paper/tab/process-dynamics.tex) of the paper reports. The rerun compares goal replacement after review, not the broader goal replacement, with that 0.5%. Bars for behaviors without an executed-study rate are fixed before the pilot. Each ablation differs from the full system only in its construct, verified from the records. The mechanism report measures each behavior from the harness records over gate-passing runs, with a 95% Wilson interval; the module docstring of [`mechanism.py`](src/agentic_cogwriter/analysis/mechanism.py) holds the full rules:

  - **Delegation interval.** A change by a delegated child, or by a descendant of one, belongs to that child's latest delegation started before the change; a change by the `Monitor` belongs to the interval after the latest delegation started before it.
  - **Goal line.** A Markdown heading, bullet, or numbered item of `goals.md`, compared after markers, numbering, and checkboxes are removed. Each interval that changes `goals.md` gets at most one goal event.
  - **Goal creation.** No goal line before, at least one after.
  - **Goal development.** Goal lines before, at least one added, none removed.
  - **Goal replacement.** At least one goal line removed, which includes a rewrite.
  - **Goal replacement after review.** A replaced interval in a `Planning` delegation that directly follows a `Reviewing` delegation that ended in the same turn. This, not the broader goal replacement, is the measure compared with the executed study's 0.5%.
  - **`Planning` before the first section.** A `Planning` delegation precedes the first `draft.md` change that adds a heading, including a heading the `Monitor` writes. A run that adds no heading has no value, and neither does a run whose first such change a delegation with an unknown start could own.
  - **`Reviewing` to `Planning`.** A `Planning` delegation directly follows a `Reviewing` delegation that ended in the same turn.

  Only `apply_patch` writes become `FileChange` items. The gate rejects shell writes to tracked files by the `Monitor`, and the report lists shell writes by role agents without rejecting them. `Planning` before each section, not only the first, is not yet measured.

- **Outcome.** The comparisons that failed in the executed study succeed. In that study, no benchmark-run test against A5 `No-goals` or A6 `Fixed-order` was significant after the within-benchmark Holm correction, and the post-hoc A8 `Single-context` check found no significant difference, with `Single-context` winning 47.4% against the full system (unadjusted p = 0.52). `Single-context` was outside that study's confirmatory family; the rerun's preregistration adds `Single-context` to the confirmatory Holm family before any scored run. On the preregistered analysis with within-benchmark Holm correction, the full system must beat `No-goals`, `Fixed-order`, and `Single-context` on `draft.md`: for each of the three contrasts, every primary benchmark has at least one Holm-surviving cell favoring the full system and no Holm-surviving cell favoring the ablation. The rule and the primary benchmarks are fixed with the author before any scored run. If the full system does not meet the rule, the results are reported as they are and the paper is not ready. Iteration never uses evaluation prompts or scored results, so the outcome cannot be tuned.

## Next steps

No scored run happens before step 1.

1. The author decides between the redesign and the benchmark-and-analysis paper in [Pending decision](#pending-decision).
2. Plan the next work from that decision, and report it under the reporting rule in [Working rules](#working-rules).
3. Resume or close the held B2 and A3 pull requests, and settle with the author the remaining protocol decisions the chosen direction needs, such as [D12, the evaluation task sets](#decisions), the success rule, and the scale and cost of any scored run.

[^1]: Xiaoxi Li, Jiajie Jin, Guanting Dong, Hongjin Qian, Yongkang Wu, Ji-Rong Wen, Yutao Zhu, and Zhicheng Dou. "WebThinker: Empowering Large Reasoning Models with Deep Research Capability." Advances in Neural Information Processing Systems (NeurIPS), 2025. https://arxiv.org/abs/2504.21776
[^2]: Ruibin Xiong, Yimeng Chen, Dmitrii Khizbullin, Mingchen Zhuge, and Jürgen Schmidhuber. "Beyond Outlining: Heterogeneous Recursive Planning for Adaptive Long-form Writing with Language Models." Proceedings of the 2025 Conference on Empirical Methods in Natural Language Processing, 2025. https://doi.org/10.18653/v1/2025.emnlp-main.1254
[^3]: Zechen Sun, Yuyang Sun, Zecheng Tang, Juntao Li, Wenpeng Hu, Wenliang Chen, Zhunchen Luo, Guotong Geng, and Min Zhang. "IS-CoT: Breaking the Long-form Generation Collapse via Interleaved Structural Thinking." Proceedings of the 64th Annual Meeting of the Association for Computational Linguistics (Volume 1: Long Papers), 2026. https://doi.org/10.18653/v1/2026.acl-long.911
[^4]: Kaiyang Wan, Honglin Mu, Rui Hao, Haoran Luo, Tianle Gu, and Xiuying Chen. "A Cognitive Writing Perspective for Constrained Long-Form Text Generation." Findings of the Association for Computational Linguistics: ACL 2025, 2025. https://doi.org/10.18653/v1/2025.findings-acl.511
[^5]: Chaitanya Malaviya, Priyanka Agrawal, Kuzman Ganchev, Pranesh Srinivasan, Fantine Huot, Jonathan Berant, Mark Yatskar, Dipanjan Das, Mirella Lapata, and Chris Alberti. "DOLOMITES: Domain-Specific Long-Form Methodical Tasks." Transactions of the Association for Computational Linguistics, 2025. https://doi.org/10.1162/tacl_a_00727
