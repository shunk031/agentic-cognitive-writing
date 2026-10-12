# Pairwise sensitivity analyses across three generation runs

These files hold the output-length, compute-matched, prompt-level, and judge-agreement analyses of the primary pairwise judgments (`gpt-5.6-sol-pairwise-v1`) over generation runs 1, 2, and 3. All reuse existing judgments; no generation or judge call is made.

- [`length-control.json`](length-control.json) is the output of [`length_control.py`](../../../experiments/src/agentic_cogwriter/analysis/length_control.py) run with one `--runs-root` and `--run-label` per generation run. `per_run` holds each run's analysis, and `across_runs` holds the same analysis over the three runs together. The tighter and wider bands keep pairs whose output-unit ratio, longer over shorter, is at most 1.05 and 1.10.
- [`compute-stratified.json`](compute-stratified.json) is the output of [`compute_control.py`](../../../experiments/src/agentic_cogwriter/analysis/compute_control.py) run with one `--runs-root` and `--replication-label` per generation run. `pooled` holds the three runs together and `per_replication` holds each run.
- [`pairwise-robustness.json`](pairwise-robustness.json) is the output of [`pairwise_robustness.py`](../../../experiments/src/agentic_cogwriter/analysis/pairwise_robustness.py) run with one `--runs-root` and `--run-label` per generation run and the generation run 1 root for the cross-family judge. `prompt_level` gives, for Agentic CogWriter against each alternative, the tie-as-half win rate with each prompt averaged over generation runs, a prompt bootstrap interval (10,000 resamples), and an exact sign test over prompts. `length_logistic` fits a logistic model of the order-consistent decided outcome on the log length ratio (focal over compared system); the intercept gives the preference at equal length, with intervals from a prompt-cluster bootstrap (2,000 resamples). `judge_agreement` gives Cohen's kappa between the primary and cross-family judges over their shared prompt-level outcomes and over pairs both judges decided.

Run roots appear only as the labels `run-1`, `run-2`, and `run-3`. The per-pair `pairs` lists are removed to keep the files small; every other field is the analysis output unchanged.

## Prompt as the unit of the sign tests

The three generation runs re-generate the same prompts, so a summary that combines runs contains up to three pairs per prompt. Every outcome summary therefore carries two tests. `sign_test_p` is the exact sign test over pairs and is kept for reference. `prompt_sign_test_p` is the exact sign test over prompts: each prompt's outcomes in the summary (win 1, tie 0.5, loss 0) are averaged, and the prompt counts as a win above 0.5, a loss below 0.5, and a tie at 0.5. The manuscript reports `prompt_sign_test_p` for the compute-matched table and the `Single-writer` length-band tests, matching the prompt-clustered ablation summary in the Results. Within a single run each prompt appears once per contrast, so the two tests agree there.

## Regenerating the manuscript macros

Run from `paper/`:

```bash
python3 scripts/make_numbers.py --length-control results/pairwise-sensitivity/length-control.json
python3 scripts/make_numbers.py --compute-stratified-sensitivity results/pairwise-sensitivity/compute-stratified.json
python3 scripts/make_numbers.py --pairwise-robustness results/pairwise-sensitivity/pairwise-robustness.json
```

Each command replaces only its own block in [`numbers.tex`](../../numbers.tex).
