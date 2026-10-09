# Pointwise and native scores across three generation runs

These files extend the benchmark-native and generic pointwise scores, previously judged on generation run 1 only, to generation runs 2 and 3 for all seven pre-specified systems (A1 to A7).

- [`three-run-summary.json`](three-run-summary.json) holds, per run, benchmark, and condition, the native mean, the generic pointwise composite, the raw dimension means, and the scored count, plus the mean and sample standard deviation across the three runs. As in run 1, the composite is z-scored within each run and benchmark over the outputs of all seven systems.
- [`paired-bootstrap.json`](paired-bootstrap.json) holds paired prompt-level bootstrap intervals for Agentic CogWriter minus Single-pass, Staged, and Task-planning on each Table 3 score; each prompt's runs are averaged per system first, so the prompt is the resampling unit. It is produced by [`paired_quality_ci.py`](../../scripts/paired_quality_ci.py).
- [`run2-aggregation.json`](run2-aggregation.json) and [`run3-aggregation.json`](run3-aggregation.json) are the production aggregator outputs for runs 2 and 3, with cost fields removed.

The judge settings match run 1: `gpt-5.6-sol` at medium reasoning effort, seed 20260908, two retries, and the `pointwise-v1`, `writingbench-native-v1`, and `hellobench-native-v1` prompts in [`experiments/prompts/judges/`](../../../experiments/prompts/judges/). DoLoMiTes has no native score. Outputs from runs whose generation did not complete are not scored: 26 in run 1, 3 in run 2, and 5 in run 3.
