# Experiment redesign handoff

This file records the state, decisions, and working rules for the CogWriter experiment redesign, so that a new session can continue without the earlier conversation. Update this file whenever a decision or milestone changes.

## Current state

- **Target.** The submission target is the next ARR cycle. The [ARR dates page](https://aclrollingreview.org/dates) lists no exact deadline after the October 2026 cycle, whose deadline of October 12, 2026 has passed. The next published entry is the ACL 2027 final ARR submission date, given as "January, 2027" with no day yet. Plan to that date, and move the plan earlier if a December 2026 cycle is published.
- **Artifact.** The skills-only plugin under [`plugin/`](../plugin/) was rebuilt and merged to main through [shunk031/agentic-cognitive-writing#148](https://github.com/shunk031/agentic-cognitive-writing/pull/148), [shunk031/agentic-cognitive-writing#150](https://github.com/shunk031/agentic-cognitive-writing/pull/150), and [shunk031/agentic-cognitive-writing#151](https://github.com/shunk031/agentic-cognitive-writing/pull/151). The `Monitor` delegates to fresh `Planning`, `Translating`, and `Reviewing` agents with fixed scopes and writes only `history.md`. The Planner replaces goals that conflict with the task. The Reviewer corrects existing prose and reports missing goals or sections. A goal covers a requirement only if the goal names the requirement's section.
- **Plugin measurement.** The plugin was measured on ten DoLoMiTes[^1] prompts with a seeded missing section, ten runs each, from harness records with independent verification. `Planning` ran before the missing section was written in 100 of 100 runs, and the requested counts were met in 99. No `Monitor` edit to `goals.md` occurred in the 350 runs since that rule, no Planner merged goals, and no Reviewer wrote a section. The remaining failure type is a Reviewer splitting a one-paragraph section into per-item lines, seen in one run of 100. The PR 151 body and its "All runs" comments hold the details and every run table.
- **Runtime branch.** The `cw` runtime branch from the earlier redesign (`cogwriter-cw`) is closed by the author's decision; the merged skills-only plugin is the only artifact. The branch stays for reference.
- **Not yet rebuilt.** The baselines (A3, B1), the A7 Single-writer ablation, and token accounting are not yet rebuilt. The fidelity gate is merged through [shunk031/agentic-cognitive-writing#154](https://github.com/shunk031/agentic-cognitive-writing/pull/154).
  - **Ablation skills.** The A6 and A8 ablations are rebuilt on main through [shunk031/agentic-cognitive-writing#161](https://github.com/shunk031/agentic-cognitive-writing/pull/161) and [shunk031/agentic-cognitive-writing#162](https://github.com/shunk031/agentic-cognitive-writing/pull/162), and the A5 ablation is rebuilt on the integration branch. The A7 Single-writer skill still follows the previous contract.
  - **Skill text.** The baseline skills and the A7 Single-writer skill still tell the agent to repeat the full text in its final message, and one baseline skill says the runner enforces this; the runner no longer scores that message. The rebuild in the next steps rewrites those skills.
  - **Host skills.** Codex loads the host user's personal skills unless the child HOME is isolated; the runner now isolates every Codex child, and the gate rejects reads outside the per-run Codex home. The cd-then-relative read is a known limit of the gate.
  - **A4 final response.** The scored output is `draft.md` itself for every draft-product condition ([shunk031/agentic-cognitive-writing#156](https://github.com/shunk031/agentic-cognitive-writing/pull/156)). The Claude Code invocation path is out of scope under [D14](#decisions).
  - **Runner-contract tests.** The runner-contract tests encode the rebuilt plugin's contracts, merged into main through [shunk031/agentic-cognitive-writing#152](https://github.com/shunk031/agentic-cognitive-writing/pull/152).
- **Runner path.** With [shunk031/agentic-cognitive-writing#158](https://github.com/shunk031/agentic-cognitive-writing/pull/158) and [shunk031/agentic-cognitive-writing#159](https://github.com/shunk031/agentic-cognitive-writing/pull/159) merged, an A4 run through the runner on a smoke prompt passes the fidelity gate: Planning, Translating, Reviewing in order, no forked child, each role reading its own skill from the per-run Codex home, the Monitor writing only `history.md`, and `draft.md` scored. One smoke run each of the rebuilt A6, A8, and A5 ablations through the runner on the same prompt also passes the gate.
- **Integration branch.** Work since the rebuilt ablations accumulates on `rerun-arr2027`. The A5 ablation from [shunk031/agentic-cognitive-writing#163](https://github.com/shunk031/agentic-cognitive-writing/pull/163) is on that branch, not on main. Its rename breaks the paper's prompt display until the paper edit, which is one reason main stays unchanged until results are ready.
- **Measurement scope.** All rate measurements so far come from seeded states on one benchmark with one model and one reasoning effort. The runner path has only single smoke runs on one prompt. Unseeded runs at scale and other benchmarks are unmeasured.

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

## Working rules

- **Iteration target.** Iterate only on process fidelity and on whether mechanisms are exercised. Measure both from harness records, using non-evaluation prompts only. Never inspect or tune output quality. Freeze the design before the pilot.
- **Changelog.** Record every iteration in the changelog, with the metric and run IDs that motivated the change.
- **No ad hoc fixes.** Trace every change to the spec, a paper requirement, or an author decision. A change that alters a construct or an earlier decision goes to the author first.
- **Fidelity before interpretation.** Follow the "Experiment validity" section of [`AGENTS.md`](../AGENTS.md): check fidelity from harness logs before any scored run, and test an implementation defect first whenever a process metric looks surprising.
- **Fidelity gate.** Before any scored run, a mechanical check of the harness records rejects runs that show any measured defect of the executed study: a child spawned with inherited context, a role agent that did not read its own skill, a Monitor write outside `.writing/history.md`, an unclosed child or thread-limit hit, or a scored output other than `draft.md`. The gate is code in the runner, not instruction text.
- **Integration.** Rerun work accumulates on the integration branch `rerun-arr2027`. Each change is a pull request into that branch, reviewed by an independent reviewer, and merged by the orchestrator after the review accepts it. Progress reports to the author describe results and blockers, not pull request approvals. The author decides on merging the integration branch into main only when the results meet the readiness criteria below.
- **Public files.** Never put private paths, hostnames, or credentials in repository files.

## Readiness criteria

Results are ready for the paper when the rerun shows that the mechanisms the executed study failed to exercise now work, measured from harness records, and the preregistered comparisons are computed on runs that pass the fidelity gate.

- **Fidelity.** Every scored run passes the fidelity gate. Rejected runs are reported with their reasons and excluded, never silently dropped. None of the measured defects recurs.
- **Mechanism.** In unseeded runs, the behaviors the method claims appear in the harness records at measurable rates for the full system: `Planning` before a section is written, `Reviewing` that leads to `Planning`, and goal creation, development, and replacement. The executed study recorded `Reviewing`-to-`Planning` in 0.3% of runs and accepted goal replacement in 0.5%. Each ablation differs from the full system only in its construct, verified from the records.
- **Outcome.** The preregistered comparisons are computed on `draft.md` with the planned statistics and reported as they come out. The criterion requires valid comparisons, not a particular winner; the paper's claims follow the results.

## Next steps

1. Pilot on non-evaluation prompts through the runner for the full system and the rebuilt ablations, with unseeded runs, to check the Fidelity and Mechanism criteria before any scored run.
   - The process-sequence analysis still reads `process.jsonl` and needs a harness-record source.
2. Rebuild the A7 Single-writer ablation, the baselines (A3, B1), and token accounting on the integration branch with the same loop.
   - The loop is a small batch, fidelity from harness records, independent verification, and one change at a time.
3. Settle the dataset-protocol decisions ([D12](#decisions)) and the rerun's scale and cost with the author.
4. Run the rerun and the preregistered comparisons; check all three readiness criteria.
5. Propose merging the integration branch into main and update the paper from the results.

[^1]: Chaitanya Malaviya, Priyanka Agrawal, Kuzman Ganchev, Pranesh Srinivasan, Fantine Huot, Jonathan Berant, Mark Yatskar, Dipanjan Das, Mirella Lapata, and Chris Alberti. "DOLOMITES: Domain-Specific Long-Form Methodical Tasks." Transactions of the Association for Computational Linguistics, 2025. https://doi.org/10.1162/tacl_a_00727
