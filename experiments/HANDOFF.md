# Experiment redesign handoff

This file records the state, decisions, and working rules for the CogWriter experiment redesign, so that a new session can continue without the earlier conversation. Update this file whenever a decision or milestone changes.

## Current state

- **Target.** The submission target is the next ARR cycle. The [ARR dates page](https://aclrollingreview.org/dates) lists no exact deadline after the October 2026 cycle, whose deadline of October 12, 2026 has passed. The next published entry is the ACL 2027 commitment deadline, given as "January 2027" with no day yet. Plan to that date, and move the plan earlier if a December 2026 cycle is published.
- **Artifact.** The skills-only plugin under [`plugin/`](../plugin/) was rebuilt and merged to main through [shunk031/agentic-cognitive-writing#148](https://github.com/shunk031/agentic-cognitive-writing/pull/148), [shunk031/agentic-cognitive-writing#150](https://github.com/shunk031/agentic-cognitive-writing/pull/150), and [shunk031/agentic-cognitive-writing#151](https://github.com/shunk031/agentic-cognitive-writing/pull/151). The `Monitor` delegates to fresh `Planning`, `Translating`, and `Reviewing` agents with fixed scopes and writes only `history.md`. The Planner replaces goals that conflict with the task. The Reviewer corrects existing prose and reports missing goals or sections. A goal covers a requirement only if the goal names the requirement's section.
- **Plugin measurement.** The plugin was measured on ten DoLoMiTes[^1] prompts with a seeded missing section, ten runs each, from harness records with independent verification. `Planning` ran before the missing section was written in 100 of 100 runs, and the requested counts were met in 99. No `Monitor` edit to `goals.md` occurred in the 350 runs since that rule, no Planner merged goals, and no Reviewer wrote a section. The remaining failure type is a Reviewer splitting a one-paragraph section into per-item lines, seen in one run of 100. The PR 151 body and its "All runs" comments hold the details and every run table.
- **Runtime branch.** The `cw` runtime branch from the earlier redesign (`cogwriter-cw`) is closed by the author's decision; the merged skills-only plugin is the only artifact. The branch stays for reference.
- **Superseded PR.** [shunk031/agentic-cognitive-writing#144](https://github.com/shunk031/agentic-cognitive-writing/pull/144), the incremental prompt fix, is open and superseded by the redesign. Keep it open until the author decides.
- **Not yet rebuilt.** The baselines (A3, B1), the generated ablations, and token accounting are not yet rebuilt. The fidelity gate is merged through [shunk031/agentic-cognitive-writing#154](https://github.com/shunk031/agentic-cognitive-writing/pull/154).
  - **Ablation skills.** The A5, A6, and A8 experiment skills still describe themselves as variants of the previous agentic-cog-writer contract. For example, A6 expects per-goal keep, develop, and regenerate verdicts that the rebuilt Reviewer no longer produces. The ablations therefore do not match the rebuilt A4 until slice 2 rewrites them.
  - **Skill text.** Several baseline and ablation skills still tell the agent to repeat the full text in its final message, and one says the runner enforces this; the runner no longer scores that message. Slice 2 rewrites those skills.
  - **Codex staging.** The runner's Codex staging copies only skill directories. The staging omits the plugin's Codex adapter files, the agent definitions, `config.toml`, and the rules under [`plugin/codex/`](../plugin/codex/), on which the rebuilt plugin depends.
  - **A4 trace requirement.** The runner's A4 condition in [`conditions/a4_plugin.toml`](conditions/a4_plugin.toml) still requires trace events in `process.jsonl`, including goal events. The rebuilt `Monitor` writes only `.writing/history.md`.
  - **A4 final response.** The scored output is `draft.md` itself for every draft-product condition ([shunk031/agentic-cognitive-writing#156](https://github.com/shunk031/agentic-cognitive-writing/pull/156)). The Claude Code invocation path is out of scope under [D14](#decisions).
  - **Runner-contract tests.** Five runner-contract tests fail on main because they encode the previous plugin's contracts. [shunk031/agentic-cognitive-writing#152](https://github.com/shunk031/agentic-cognitive-writing/pull/152) fixes them and is not merged yet.
- **Measurement scope.** All measurements so far come from seeded states on one benchmark with one model and one reasoning effort. Natural runs, other benchmarks, and the runner path are unmeasured.

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
- **Merges.** A merge needs the author's explicit approval for that specific PR.
- **Public files.** Never put private paths, hostnames, or credentials in repository files.

## Next steps

1. Make CI green: update or delete the five runner-contract tests that encode the previous plugin's contracts.
2. Done: the fidelity gate was added to the runner, as the working rules define it, and tested against the recorded defects, merged through [shunk031/agentic-cognitive-writing#154](https://github.com/shunk031/agentic-cognitive-writing/pull/154).
3. Rebuild slices 2 to 4 on the merged plugin, Codex only: baselines, ablations, and runner gates and token accounting. Run each slice through the same loop before any scoring: a small batch, fidelity from harness records, independent verification, and one change at a time.
   - Done: `draft.md` is the scored deliverable, via [shunk031/agentic-cognitive-writing#156](https://github.com/shunk031/agentic-cognitive-writing/pull/156).
4. Run a pilot through the runner path on non-evaluation prompts and publish its fidelity report. Then freeze the design.
5. Settle the deferred dataset-protocol decisions of the evaluation task sets ([D12](#decisions)) and the cost of the full rerun with the author. Then run the full rerun.
6. Update the paper only after the rerun, and replace every figure with results from the executed study.

[^1]: Chaitanya Malaviya, Priyanka Agrawal, Kuzman Ganchev, Pranesh Srinivasan, Fantine Huot, Jonathan Berant, Mark Yatskar, Dipanjan Das, Mirella Lapata, and Chris Alberti. "DOLOMITES: Domain-Specific Long-Form Methodical Tasks." Transactions of the Association for Computational Linguistics, 2025. https://doi.org/10.1162/tacl_a_00727
