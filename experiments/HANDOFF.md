# Experiment redesign handoff

This file records the state, decisions, and working rules for the CogWriter experiment redesign, so that a new session can continue without the earlier conversation. Update this file whenever a decision or milestone changes.

## Current state

- **Target.** The submission target is the next ARR cycle. The [ARR dates page](https://aclrollingreview.org/dates) lists no exact deadline after the October 2026 cycle, whose deadline of October 12, 2026 has passed. The next published entry is the ACL 2027 final ARR submission date, given as "January, 2027" with no day yet. Plan to that date, and move the plan earlier if a December 2026 cycle is published.
- **Artifact.** The skills-only plugin under [`plugin/`](../plugin/) was rebuilt and merged to main through [shunk031/agentic-cognitive-writing#148](https://github.com/shunk031/agentic-cognitive-writing/pull/148), [shunk031/agentic-cognitive-writing#150](https://github.com/shunk031/agentic-cognitive-writing/pull/150), and [shunk031/agentic-cognitive-writing#151](https://github.com/shunk031/agentic-cognitive-writing/pull/151). The `Monitor` delegates to fresh `Planning`, `Translating`, and `Reviewing` agents with fixed scopes and writes only `history.md`. The Planner replaces goals that conflict with the task. The Reviewer corrects existing prose and reports missing goals or sections. A goal covers a requirement only if the goal names the requirement's section.
- **Plugin measurement.** The plugin was measured on ten DoLoMiTes[^1] prompts with a seeded missing section, ten runs each, from harness records with independent verification. `Planning` ran before the missing section was written in 100 of 100 runs, and the requested counts were met in 99. No `Monitor` edit to `goals.md` occurred in the 350 runs since that rule, no Planner merged goals, and no Reviewer wrote a section. The remaining failure type is a Reviewer splitting a one-paragraph section into per-item lines, seen in one run of 100. The PR 151 body and its "All runs" comments hold the details and every run table.
- **Runtime branch.** The `cw` runtime branch from the earlier redesign (`cogwriter-cw`) is closed by the author's decision; the merged skills-only plugin is the only artifact. The branch stays for reference.
- **Not yet rebuilt.** The baselines A2 `Staged`, A3 `Task-planning`, B1 `Exploratory-1`, and B2 `Exploratory-2`, the A7 `Single-writer` ablation, and token accounting are not yet rebuilt. The paper's [code-to-system map](../paper/sec/09_prompt_configuration.tex) names the A conditions, and B1 and B2 are the paper's CogWriter-style and STORM-style exploratory baselines. A1 `Single-pass` keeps its skill, because its final response is its deliverable. The fidelity gate is merged through [shunk031/agentic-cognitive-writing#154](https://github.com/shunk031/agentic-cognitive-writing/pull/154).
  - **Ablation skills.** The A6 `Fixed-order` and A8 `Single-context` ablations are rebuilt on main through [shunk031/agentic-cognitive-writing#161](https://github.com/shunk031/agentic-cognitive-writing/pull/161) and [shunk031/agentic-cognitive-writing#162](https://github.com/shunk031/agentic-cognitive-writing/pull/162), and the A5 `No-goals` ablation is rebuilt on the integration branch. The A7 skill still follows the previous contract.
  - **Skill text.** The A2 and A3 baseline skills and the A7 skill still require the full text in the final response, and the A3 skill says the runner enforces this; the runner no longer scores that message. The rebuild in the next steps rewrites those skills.
  - **Host skills.** Codex loads the host user's personal skills unless the child HOME is isolated; the runner now isolates every Codex child, and the gate rejects reads outside the per-run Codex home. The cd-then-relative read is a known limit of the gate.
  - **A4 final response.** The scored output is `draft.md` itself for every draft-product condition ([shunk031/agentic-cognitive-writing#156](https://github.com/shunk031/agentic-cognitive-writing/pull/156)). The Claude Code invocation path is out of scope under [D14](#decisions).
  - **Runner-contract tests.** The runner-contract tests encode the rebuilt plugin's contracts, merged into main through [shunk031/agentic-cognitive-writing#152](https://github.com/shunk031/agentic-cognitive-writing/pull/152).
- **Runner path.** With [shunk031/agentic-cognitive-writing#158](https://github.com/shunk031/agentic-cognitive-writing/pull/158) and [shunk031/agentic-cognitive-writing#159](https://github.com/shunk031/agentic-cognitive-writing/pull/159) merged, an A4 `Agentic CogWriter` run through the runner on a smoke prompt passes the fidelity gate: Planning, Translating, Reviewing in order, no forked child, each role reading its own skill from the per-run Codex home, the Monitor writing only `history.md`, and `draft.md` scored. Smoke runs of the rebuilt A6, A8, and A5 on the same prompt also pass the gate.
- **Integration branch.** Work since the rebuilt ablations accumulates on `rerun-arr2027`. The A5 `No-goals` ablation from [shunk031/agentic-cognitive-writing#163](https://github.com/shunk031/agentic-cognitive-writing/pull/163) is on that branch, not on main. Its rename breaks the paper build until the paper edit, which is one reason main stays unchanged until results are ready.
- **Measurement scope.** All rate measurements so far come from seeded states on one benchmark with one model and one reasoning effort. The runner path has only smoke runs on one prompt. Unseeded runs at scale and other benchmarks are unmeasured.

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
- **Integration (author).** Merges into `rerun-arr2027` need no author approval; only the merge into main goes to the author once the [readiness criteria](#readiness-criteria) hold.

## Working rules

- **Iteration target.** Iterate only on process fidelity and on whether mechanisms are exercised. Measure both from harness records, using non-evaluation prompts only. Never inspect or tune output quality. Freeze the design after the pilot and before any scored run.
- **Iteration record.** Record every iteration in its pull request body, with the metric and run IDs that motivated the change.
- **No ad hoc fixes.** Trace every change to the spec, a paper requirement, or an author decision. A change that alters a construct or an earlier decision goes to the author first.
- **Fidelity before interpretation.** Follow the "Experiment validity" section of [`AGENTS.md`](../AGENTS.md): check fidelity from harness logs before any scored run, and test an implementation defect first whenever a process metric looks surprising.
- **Fidelity gate.** Before any scored run, a mechanical check of the harness records rejects runs that show any measured defect of the executed study: a child spawned with inherited context, a role agent that did not read its own skill, a Monitor write outside `.writing/history.md`, an unclosed child or thread-limit hit, or a scored output other than `draft.md`. The gate is code in the runner, not instruction text.
- **Integration.** Rerun work accumulates on the integration branch `rerun-arr2027`. Each change is a pull request into that branch, reviewed by an independent reviewer, and merged by the orchestrator after the review accepts it. Progress reports to the author describe results and blockers, not pull request approvals. The author decides on merging the integration branch into main only when the results meet the readiness criteria below.
- **Public files.** Never put private paths, hostnames, or credentials in repository files.

## Readiness criteria

Results are ready for the paper when the rerun shows, from harness records, that the mechanisms the executed study failed to exercise now work, and the comparisons that failed in that study succeed on runs that pass the fidelity gate.

- **Fidelity.** Every scored run passes the fidelity gate. Rejected runs are reported with their reasons and excluded, never silently dropped. None of the measured defects recurs.
- **Mechanism.** In unseeded runs, each behavior the method claims clears a preregistered bar for the full system: the lower bound of the 95% interval of its rate lies above the executed study's rate. Over 886 complete A4 paths, the executed study recorded `Reviewing` followed by renewed `Planning` in 4.1% and an accepted goal replacement in 0.5%, as [Table 6](../paper/tab/process-dynamics.tex) of the paper reports. The rerun compares goal replacement after review, not the broader goal replacement, with that 0.5%. Bars for behaviors without an executed-study rate are fixed before the pilot. Each ablation differs from the full system only in its construct, verified from the records. The [mechanism report](https://github.com/shunk031/agentic-cognitive-writing/pull/166) measures each behavior from the harness records, by delegation interval:

  - **Delegation interval.** A change by a delegated child, or by a descendant of one, belongs to that delegation; a change by the `Monitor` itself belongs to the interval after the last delegation spawned before it.
  - **Goal line.** A non-blank line of `goals.md` that is a Markdown heading or list item. Each delegation interval that changes `goals.md` is classified by its goal lines before and after, and one interval can show several events.
  - **Goal creation.** `goals.md` first appears, or the interval gains a goal line and removes none.
  - **Goal development.** Goal lines existed before and none was removed.
  - **Goal replacement.** A goal line before is missing after, so it was removed or rewritten.
  - **Goal replacement after review.** A goal line is removed or rewritten during a `Planning` delegation that directly follows a `Reviewing` delegation. The report is being extended with this measure.
  - **`Planning` before the first section.** A section is a Markdown heading line. A `Planning` delegation precedes the first change that adds a heading to `draft.md`; a run that adds no heading has no value.
  - **`Reviewing` to `Planning`.** The delegation right after a `Reviewing` delegation is `Planning`.

  Only `apply_patch` writes become `FileChange` items, so each run lists the shell commands that mention `goals.md` or `draft.md` and look like writes; the match is textual, so a listed command may not have written. Before the pilot, the report needs two extensions: turn the textual shell-write listing into a gate rejection, and measure `Planning` before each section, not only the first.

- **Outcome.** The comparisons that failed in the executed study succeed. In that study, no benchmark-run test against A5 `No-goals` or A6 `Fixed-order` was significant after the within-benchmark Holm correction, and the post-hoc A8 `Single-context` check found no significant difference, with `Single-context` winning 47.4% against the full system (unadjusted p = 0.52). `Single-context` was outside that study's confirmatory family; the rerun's preregistration adds `Single-context` to the confirmatory Holm family before any scored run. On the preregistered analysis with within-benchmark Holm correction, the full system must beat `No-goals`, `Fixed-order`, and `Single-context` on `draft.md`: for each of the three contrasts, every primary benchmark has at least one Holm-surviving cell favoring the full system and no Holm-surviving cell favoring the ablation. The rule and the primary benchmarks are fixed with the author before any scored run. If the full system does not meet the rule, the results are reported as they are and the paper is not ready. Iteration never uses evaluation prompts or scored results, so the outcome cannot be tuned.

## Next steps

1. Check the Mechanism criterion for the full system on non-evaluation prompts, as an iteration check rather than the pilot.
   - The process-sequence analysis still reads `process.jsonl` and needs a harness-record source, which the [mechanism report](https://github.com/shunk031/agentic-cognitive-writing/pull/166) provides.
2. Rebuild the A7 `Single-writer` ablation, the A2, A3, B1, and B2 baselines, and token accounting on the integration branch with the same loop.
   - The loop is a small batch, fidelity from harness records, independent verification, and one change at a time.
3. Pilot all arms on non-evaluation prompts, check the Fidelity and Mechanism criteria, then freeze the design.
4. Settle with the author, before any scored run, the open dataset-protocol decisions of [D12, the evaluation task sets](#decisions), the Outcome success rule and its primary benchmarks, the addition of `Single-context` to the confirmatory Holm family, and the rerun's scale and cost.
5. Run the rerun and the preregistered comparisons, then check all three readiness criteria.
6. Propose merging the integration branch into main and update the paper from the results.

[^1]: Chaitanya Malaviya, Priyanka Agrawal, Kuzman Ganchev, Pranesh Srinivasan, Fantine Huot, Jonathan Berant, Mark Yatskar, Dipanjan Das, Mirella Lapata, and Chris Alberti. "DOLOMITES: Domain-Specific Long-Form Methodical Tasks." Transactions of the Association for Computational Linguistics, 2025. https://doi.org/10.1162/tacl_a_00727
