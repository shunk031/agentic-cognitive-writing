# Redesign changelog

This changelog records each change to the redesigned CogWriter arms during the smoke iterations of [the redesign specification](../docs/experiments/redesign/design.md). Each entry gives the change, the `fidelity.py` metric and run IDs that motivated it, and the result. Iterations target process fidelity and mechanism exercise only, measured from harness records on non-evaluation prompts.

## Slice 1

### Baseline build

- **Change.** `cw` with every command and invariant, the A4 `Monitor` skill and the three role skills, the runner's `task.md`, `cw` staging, snapshot scoring, A4 gates, `failure.kind`, and the per-thread token rule, and `fidelity.py`.
- **Spec erratum.** Six of the nine specified smoke prompts are A10 calibration prompts. Slice 1 runs only writingbench-0210, -0049, and -0051, which pass the disjointness check; later slices use the replacement pool recorded in the specification's Errata section.
