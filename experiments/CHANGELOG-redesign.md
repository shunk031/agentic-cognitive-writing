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
