# Experiment redesign handoff

This file records the state, decisions, and working rules for the CogWriter experiment redesign, so that a new session can continue without the earlier conversation. Update this file whenever a decision or milestone changes.

## Current state

- **Submission.** The author withdrew the planned ARR October 2026 resubmission after audits showed that the executed experiments did not run as designed. The paper in [shunk031/agentic-cognitive-writing#143](https://github.com/shunk031/agentic-cognitive-writing/pull/143) stays open and unmerged. Do not edit paper prose until the author asks.
- **Superseded PR.** [shunk031/agentic-cognitive-writing#144](https://github.com/shunk031/agentic-cognitive-writing/pull/144), the incremental prompt fix, is superseded by this branch. Keep it open until the author decides.
- **Merged.** [shunk031/agentic-cognitive-writing#145](https://github.com/shunk031/agentic-cognitive-writing/pull/145) added the "Experiment validity" section to [`AGENTS.md`](../AGENTS.md).
- **This branch.** `cogwriter-cw` implements the frozen redesign spec in [`docs/experiments/redesign/design.md`](../docs/experiments/redesign/design.md) in four slices:
  1. `cw` together with the A4 skill and `fidelity.py`
  2. the generated ablations
  3. the baselines
  4. the runner gates and token accounting
- **Slice 1.** Done. The first independent review rejected head 9609cf6; the fixes for its findings and a verification smoke on the replacement pool are in. A second review is pending. [`cw`](../plugin/cw/cw.py) enforces every invariant of the specification, and the A4 `Monitor` and role skills run on it. The runner writes `task.md`, stages `cw`, scores the `cw stop` snapshot, gates A4, classifies `failure.kind`, and applies the per-thread token rule. [`fidelity.py`](src/agentic_cogwriter/analysis/fidelity.py) reports from harness records. In the last of four smoke iterations, every A4 gate held on the three disjoint smoke prompts, but every first review found all requirements met, so no run returned from `Reviewing`. The four slice 1 iterations used short WritingBench tasks whose first draft met every requirement, which is the specification's ceiling risk. On the replacement pool, reviews found unmet requirements and the runs returned from `Reviewing` to `Translating` and `Planning`; one run failed the nonce gate when the `Monitor` spawned an agent outside `cw step`. Iterations 6 and 7 then limited spawns to the printed line, after which the nonce gate held in every completed run, and made `cw` list every invalid requirement line in one refusal, after which both reissues passed. The [changelog](CHANGELOG-redesign.md) records each iteration, and the specification's Errata section records the post-slice fixes to `stop cap`, reissue briefs, and turn-2 requirement sources.
- **Priority (D13).** The current priority is slices 1–4, so that every arm behaves as the specification describes. The dataset protocol draft for D12 is designed and under review, but its decisions, and any discussion of cost, wait until that system works.
- **Pending in later slices.** Until slice 2, the A5–A8 and A12 skills are the pre-redesign text and still run through the old runner path, and the tests of their text, the generator, and A9 are skipped. The A4 skill directory still holds the old `scripts/` and `references/`, which the runner no longer stages for A4. The output language is a placeholder, the majority script of the assignment, until the manifests carry the language field.

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
- **Evaluation task sets (D12).** Re-select benchmark prompts by criteria fixed before any results: composition tasks with explicit requirements, without long-input summarization; also report the current hard100 subsets in full. Add LongGenBench-16K. Build a requirement-revision set with mid-draft requirement changes, seeded defects, and added checkable constraints, with a generator frozen before any scored run, separate dev and test splits, checkers hidden from the `Reviewer`, and a cross-family judge. Selection never uses observed win rates. The [decisions record](../docs/experiments/redesign/decisions.md) holds the full text.
- **Priority (D13).** First build a system that behaves as the paper describes; cost and the dataset protocol's open decisions wait until it works.
- **Smoke pool erratum.** Six of the specified smoke prompts were A10 calibration prompts. The pool is now ranks 105–112 below the calibration set plus three disjoint WritingBench prompts, as the Errata section of the [specification](../docs/experiments/redesign/design.md#errata) records.

## Working rules

- **Iteration target.** Iterate only on process fidelity and on whether mechanisms are exercised. Measure both from harness records, using non-evaluation prompts only. Never inspect or tune output quality. Freeze the design before the pilot.
- **Changelog.** Record every iteration in the changelog, with the metric and run IDs that motivated the change.
- **No ad hoc fixes.** Trace every change to the spec, a paper requirement, or an author decision. A change that alters a construct or an earlier decision goes to the author first.
- **Fidelity before interpretation.** Follow the "Experiment validity" section of [`AGENTS.md`](../AGENTS.md): check fidelity from harness logs before any scored run, and test an implementation defect first whenever a process metric looks surprising.
- **Merges.** A merge needs the author's explicit approval for that specific PR.
- **Public files.** Never put private paths, hostnames, or credentials in repository files.

## Next steps

1. Have an independent reviewer check slice 1 against the specification and the fidelity report.
2. Run slice 2 after the coordinator confirms, then slices 3 and 4, each with its own small smoke loop on the replacement smoke pool.
3. After every arm behaves as specified, settle the deferred decisions of the D12 dataset protocol draft and discuss cost with the author.
4. Pilot as specified, after the author approves the cost. Then freeze the design.
5. Before any scored run, discuss the scope and cost of the full rerun with the author.
