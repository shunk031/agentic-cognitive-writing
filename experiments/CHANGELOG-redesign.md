# Redesign changelog

This changelog records each change to the redesigned CogWriter arms during the smoke iterations of [the redesign specification](../docs/experiments/redesign/design.md). Each entry gives the change, the `fidelity.py` metric and run IDs that motivated it, and the result. Iterations target process fidelity and mechanism exercise only, measured from harness records on non-evaluation prompts.

## Slice 1

### Baseline build

- **Change.** `cw` with every command and invariant, the A4 `Monitor` skill and the three role skills, the runner's `task.md`, `cw` staging, snapshot scoring, A4 gates, `failure.kind`, and the per-thread token rule, and `fidelity.py`.
- **Spec erratum.** Six of the nine specified smoke prompts are A10 calibration prompts. Slice 1 runs only writingbench-0210, -0049, and -0051, which pass the disjointness check; later slices use the replacement pool recorded in the specification's Errata section.

### Iteration 1: the language line

- **Motivation.** Run `a4-wb0210` (`it1`): `failure` `cw_failure:output`, path `t1:pp`, 2 failed steps. Both `Planning` attempts quoted "Output language: Chinese", which `task.md` held only as a heading and a value, so `cw` refused the requirements.
- **Change.** `task.md` and the prompt state the language as the single line `Output language: <language>`.
- **Result.** In iteration 2, no `Planning` step quoted the language line as a heading again; two of the three runs still failed on other source quotes.

### Iteration 2: three prompts after the language fix

- **Runs.** `a4-wb0210`, `a4-wb0049`, `a4-wb0051` (`it2`). Tokens: child-inclusive output 24,862, input 1,331,207.
- **Metrics.** One valid run (`a4-wb0210`: path `t1:pPTR`, stop `met`, first review 0 unmet and 0 findings). Two runs ended in `cw_failure:output` after both `Planning` attempts wrote `src` values that are not exact spans of `task.md`: two spans joined with "and" or ";", an ellipsis, a translated label, and backslash-escaped inner quotes. Five failed steps in three runs. In `a4-wb0049` the `Monitor` dropped `close_agent` from the delegation block, leaving 2 children unclosed and failing the `top_level_writes` gate.
- **Changes for iteration 3.** Two changes, each tied to its own metric. `Planning`: `src` is one span copied character for character, never translated, shortened, escaped, or joined, and each span is confirmed with `grep -F`. `Monitor`: the delegation block prints the child's final status after `close_agent` and runs as one call.

### Iteration 3: exact sources and closing children

- **Runs.** `a4-wb0210`, `a4-wb0049`, `a4-wb0051` (`it3`). Tokens: child-inclusive output 38,689, input 1,787,457.
- **Result.** Every gate holds in all three runs. Every spawn passed the printed line, every child was injected with its role skill and closed, and no child was forked or given model arguments. One failed step remains: in `a4-wb0051` the first `Planning` attempt indented `G1.1.1` under the wrong parent, and the reissue passed. Paths are `PTR`, `PTR`, and `pPTR`; every run stopped `met` after one pass.
- **Mechanism exercise.** Every first review found 0 unmet requirements and 0 findings, so no run returned from `Reviewing`, and no requirement was developed or regenerated. The logs show `Reviewing` met verdicts whose evidence is a short excerpt, such as a title, for requirements about the whole draft; one `Reviewer` measured the length before judging it.
- **Change for iteration 4.** `Reviewing` marks a requirement met only when the draft meets it fully, and measures whole-draft requirements, such as a length, a number of items, or every required section, before judging them, recording the measurement in `where`. A partial match is unmet. The change targets the `unmet` metric and adds no quality criterion.

### Iteration 4: measured verdicts

- **Runs.** `a4-wb0210`, `a4-wb0049`, `a4-wb0051` (`it4`). Tokens: child-inclusive output 36,918, input 1,611,290.
- **Result.** Every gate holds in all three runs. Paths are `pPTR`, `PTR`, and `PTR`. The one failed step is again a first `Planning` attempt whose child ID did not extend its parent's ID; the reissue passed. The `Reviewer`s now record measurements in `where`, such as 129 characters against a 100–150 character requirement, all 11 requested technical parameters, and all 12 chapters and 21 articles. Every requirement was still met at the first review, so no run returned from `Reviewing`.
- **Slice 1 exit criterion.** No run had more than one `Reviewing` step. The logs explain the miss: each first review measured the whole-draft requirements and found them met with verbatim evidence, so `stop met` was the correct move under the stop rule. The three prompts are short WritingBench tasks with explicit constraints that one draft already meets, which is the specification's ceiling risk. The iteration budget of four is spent.

### Tooling fix during slice 1

- `fidelity.py` skips refused `cw` entries when it counts reviews, decisions, and goal events; iteration 2's report failed on a refused `cw review` entry.
