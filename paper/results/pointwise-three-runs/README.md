# Pointwise and native scores across three generation runs

These files extend the benchmark-native and generic pointwise scores, previously judged on generation run 1 only, to generation runs 2 and 3 for the four primary conditions: Single-pass (A1), Staged (A2), Task-planning (A3), and Agentic CogWriter (A4).

- [`three-run-summary.json`](three-run-summary.json) holds, per run, benchmark, and condition, the native mean, the generic pointwise composite, the raw dimension means, and the scored count, plus the mean and sample standard deviation across the three runs. The composite here is z-scored within each run and benchmark over the same four conditions, so the three runs are comparable; the run-1 composite reported elsewhere was z-scored over seven conditions.
- [`run2-aggregation.json`](run2-aggregation.json) and [`run3-aggregation.json`](run3-aggregation.json) are the production aggregator outputs for runs 2 and 3, with cost fields removed.

The judge settings follow run 1: `gpt-5.6-sol`, seed 20260908, two retries, and the `pointwise-v1`, `writingbench-native-v1`, and `hellobench-native-v1` prompts in [`experiments/prompts/judges/`](../../../experiments/prompts/judges/). Run 1 requests omitted the reasoning-effort field and used the documented medium default, as for the run-1 pairwise judgments; runs 2 and 3 pin medium explicitly. DoLoMiTes has no native score. Outputs from runs whose generation did not complete are not scored: 26 in run 1, 3 in run 2, and 5 in run 3.
