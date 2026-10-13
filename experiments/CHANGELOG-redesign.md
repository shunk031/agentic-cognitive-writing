# Redesign changelog

This changelog records each change to the redesigned CogWriter arms during the smoke iterations of [the redesign specification](../docs/experiments/redesign/design.md). Each iteration makes one change and records the `fidelity.py` metric and run IDs that motivated it, the token counts of its runs, and the result. A run's token counts are its parent output (the budget statistic), its child-inclusive output, and its child-inclusive input, under the per-thread token rule. Run IDs are the runner's run directory names. Iterations target process fidelity and mechanism exercise only, measured from harness records on non-evaluation prompts.

## Slice 1

### Baseline build

- **Change.** `cw` with every command and invariant, the A4 `Monitor` skill and the three role skills, the runner's `task.md`, `cw` staging, snapshot scoring, A4 gates, `failure.kind`, and the per-thread token rule, and `fidelity.py`.
- **Spec erratum.** Six of the nine specified smoke prompts are A10 calibration prompts. Slice 1 runs only writingbench-0210, -0049, and -0051, which pass the disjointness check; later slices use the replacement pool recorded in the specification's Errata section.

### Iteration 1: the language line

- **Runs.** writingbench-0210 `3409cdedb82e49ec80b44eaf3e70fdfd` (tokens: parent output 2,227, child-inclusive output 5,231, input 340,158).
- **Motivation.** Run `3409cded`: `failure` `cw_failure:output`, path `t1:pp`, 2 failed steps. Both `Planning` attempts quoted "Output language: Chinese", which `task.md` held only as a heading and a value, so `cw` refused the requirements.
- **Change.** `task.md` and the prompt state the language as the single line `Output language: <language>`.
- **Result.** In iteration 2, no `Planning` step quoted the language line as a heading again; two of the three runs still failed on other source quotes.

### Iteration 2: three prompts after the language fix

- **Runs.** writingbench-0210 `c390432af52f47b38b50695e1e0d9580` (tokens: parent output 2,680, child-inclusive output 10,360, input 616,107), writingbench-0049 `365f3ae28e9342699a75f521b3ddc5f6` (tokens: parent output 1,814, child-inclusive output 6,604, input 347,321), writingbench-0051 `6dd3a290b0824b6e8b85e30846ee6776` (tokens: parent output 1,778, child-inclusive output 7,898, input 367,779).
- **Metrics.** One valid run (`a4-wb0210`: path `t1:pPTR`, stop `met`, first review 0 unmet and 0 findings). Two runs ended in `cw_failure:output` after both `Planning` attempts wrote `src` values that are not exact spans of `task.md`: two spans joined with "and" or ";", an ellipsis, a translated label, and backslash-escaped inner quotes. Five failed steps in three runs. In `a4-wb0049` the `Monitor` dropped `close_agent` from the delegation block, leaving 2 children unclosed and failing the `top_level_writes` gate.
- **Changes for iteration 3.** Two changes, each tied to its own metric. `Planning`: `src` is one span copied character for character, never translated, shortened, escaped, or joined, and each span is confirmed with `grep -F`. `Monitor`: the delegation block prints the child's final status after `close_agent` and runs as one call.

### Iteration 3: exact sources and closing children

- **Runs.** writingbench-0210 `4f4ba9ace6b3452387ba3539cf8f2068` (tokens: parent output 2,335, child-inclusive output 9,952, input 521,691), writingbench-0049 `9faebb87870045d7a8ea781bc2e1867c` (tokens: parent output 2,087, child-inclusive output 12,377, input 488,829), writingbench-0051 `1ca510232cc34926acf7f0b900d61ceb` (tokens: parent output 2,430, child-inclusive output 16,360, input 776,937).
- **Deviation.** This iteration made two changes, one per failure class, against the one-change rule.
- **Result.** Every gate holds in all three runs. Every spawn passed the printed line, every child was injected with its role skill and closed, and no child was forked or given model arguments. One failed step remains: in `a4-wb0051` the first `Planning` attempt indented `G1.1.1` under the wrong parent, and the reissue passed. Paths are `PTR`, `PTR`, and `pPTR`; every run stopped `met` after one pass.
- **Mechanism exercise.** Every first review found 0 unmet requirements and 0 findings, so no run returned from `Reviewing`, and no requirement was developed or regenerated. The logs show `Reviewing` met verdicts whose evidence is a short excerpt, such as a title, for requirements about the whole draft; one `Reviewer` measured the length before judging it.
- **Change for iteration 4.** `Reviewing` marks a requirement met only when the draft meets it fully, and measures whole-draft requirements, such as a length, a number of items, or every required section, before judging them, recording the measurement in `where`. A partial match is unmet. The change targets the `unmet` metric and adds no quality criterion.

### Iteration 4: measured verdicts

- **Runs.** writingbench-0210 `558643bf9b474a3d92c8ff9e2dbf93cc` (tokens: parent output 3,021, child-inclusive output 10,633, input 598,500), writingbench-0049 `5ef36d24d32c46769cd9b45aa40e0e28` (tokens: parent output 2,078, child-inclusive output 13,176, input 486,172), writingbench-0051 `1a90b3eabcb14857abb5ac64b1958e7c` (tokens: parent output 1,907, child-inclusive output 13,109, input 526,618).
- **Result.** Every gate holds in all three runs. Paths are `pPTR`, `PTR`, and `PTR`. The one failed step is again a first `Planning` attempt whose child ID did not extend its parent's ID; the reissue passed. The `Reviewer`s now record measurements in `where`, such as 129 characters against a 100–150 character requirement, all 11 requested technical parameters, and all 12 chapters and 21 articles. Every requirement was still met at the first review, so no run returned from `Reviewing`.
- **Slice 1 exit criterion.** No run had more than one `Reviewing` step. The logs explain the miss: each first review measured the whole-draft requirements and found them met with verbatim evidence, so `stop met` was the correct move under the stop rule. The three prompts are short WritingBench tasks with explicit constraints that one draft already meets, which is the specification's ceiling risk. The iteration budget of four is spent.

### Tooling fix during slice 1

- `fidelity.py` skips refused `cw` entries when it counts reviews, decisions, and goal events; iteration 2's report failed on a refused `cw review` entry.

### Errata after slice 1

- **Reissue reason.** Motivated by the first `Planning` attempts that failed the goals grammar in writingbench-0051 `1ca510232cc34926acf7f0b900d61ceb` (iteration 3) and writingbench-0210 `558643bf9b474a3d92c8ff9e2dbf93cc` (iteration 4), 2 of 6 first attempts. A reissue brief now carries `cw`'s refusal reason verbatim. Not yet smoke-tested.
- **`stop cap`.** A cap no longer requires every proposal to be decided; the stop entry reports the undecided ones. Motivation: the coordinator's ruling on the slice 1 interpretations, not a run. No run of iterations 1–4 had more than one `Reviewing` step, so none reached the cap, and no metric or run ID motivated it.
- **Turn-2 requirement sources.** `Planning` may quote a runner-written turn request as well as `task.md`. Motivation: a specification gap found in review, before any follow-up smoke run; no slice 1 iteration 1–4 run had a second turn. The first follow-up run, dolomites-1453 `11f16a501a9b4d7390f09a29a875e220` (iteration 5), then quoted the request in 0 of its turn-2 requirements.

### Fixes from the independent review of slice 1

The review of 9609cf6 found these defects; none is a prompt iteration.

- **Stop after a failed reissue.** `cw` accepted `stop met` and `stop cap` after a failed reissue, and `met` checked the last successful step. Only `failure` is accepted after a failed reissue, and `met` requires the latest step of the turn to be a successful `Reviewing`.
- **`spawn_args` gate.** The gate compares each child's first-turn model, effort, and service tier with the parent's, instead of parsing the spawn code.
- **Per-turn completeness and scoring.** Every turn that ran needs its own `met` or `cap` stop, and each turn is scored from its own snapshot.
- **Single-turn contract.** The `.writing/assignment.md` and acknowledgment-line clauses are removed; no other shared contract carried either.
- **Token fixtures.** The token tests replay trimmed real records of a4-hbchat047 and of a forked A3 child. No executed rollout contains a context reset, so that case stays synthetic.
- **Returns.** `fidelity.py` counts R→T and R→P within each turn.
- **`cw_failure:retry`.** Kept and added to the specification's Errata.
- **Skills.** The `Monitor` and `Planning` skills point to `cw` instead of restating the first-step, scope, reissue, stop, and ID rules.

### Iteration 5: verification of the review fixes on the replacement pool

- **Deviation.** This iteration tested several changes at once: the review fixes and the three errata above. It is a verification run, not a one-change iteration.
- **Change under test.** The review fixes and errata above; no prompt change. Prompts from ranks 105–112 of the replacement pool.
- **Runs.** dolomites-1453 with a turn-2 change request `11f16a501a9b4d7390f09a29a875e220` (tokens: parent output 9,541, child-inclusive output 55,166, input 4,074,064), writingbench-0519, whose topic is Chinese law, `1ac3a6e5282d4db5992ded2c4131a85a` (tokens: parent output 4,384, child-inclusive output 43,808, input 2,014,560), and writingbench-0838 `8c5953b3343e408a8fe8b4120327e7de` (tokens: parent output 1,816, child-inclusive output 13,860, input 569,676).
- **Mechanism exercise.** For the first time, reviews found unmet requirements and findings. writingbench-0519 followed `PTRTRTRTR`, with 4 unmet requirements and 2 findings in its first review and three R→T returns, and stopped `met` after four passes. dolomites-1453 stopped `met` in each turn; turn 2 followed `PtTRTRPR`, with one R→T and one R→P return. No requirement was developed or regenerated, and no proposal was made.
- **Reissue reason.** Three reissue briefs carried `cw`'s refusal reason. Two reissues passed: a `Planning` source quote in dolomites-1453 step 2, and an unchanged draft in its step 7. One failed: in writingbench-0838 the reissued `Planning` fixed the reported `G8.4` source but wrote a backslash-escaped quote in `G11.2`, so the run ended `cw_failure:output`.
- **Follow-up path.** The runner wrote `turn-02-request.md`, each turn stopped on its own, and both snapshots exist. Turn 2's new requirements took ancestor IDs as their `src`, so no requirement quoted the turn request.
- **Gate failure.** dolomites-1453 failed `gate:nonce`. After step 7 closed, the `Monitor` spawned a second agent with a message it wrote around the step-7 spawn line, then sent that agent its own instructions through `send_input`. The child was not injected with its role skill (12 of 13 injected). The gate caught an off-protocol spawn as designed.
- **Candidates for the next iteration, one change each.** (1) `Monitor`: spawn only with a spawn line that `cw step` has just printed, send a role agent no other message, and run a new step for further work. (2) `cw`: report every invalid requirement line in one refusal, so that a reissue can fix them all.

### Iteration 6: spawn only with the printed line

- **Motivation.** Run `11f16a501a9b4d7390f09a29a875e220` (iteration 5) failed `gate:nonce`: the `Monitor` spawned a second agent with a message built around an already-used spawn line and then sent it instructions through `send_input`, so 12 of 13 children were injected with their role skill.
- **Change.** `Monitor` skill only: spawn a role agent only with the exact spawn line that `cw step` has just printed, send it no other message, and open a new step for any further work.
- **Runs.** dolomites-1453 with the iteration 5 turn-2 change request `da6b05afce914b8a90a6174a5c8ed720` (tokens: parent output 3,489, child-inclusive output 27,153, input 1,397,267), writingbench-0519 `7379279c36f94fdc8247ada5fdf41a28` (tokens: parent output 1,867, child-inclusive output 10,219, input 471,085), and writingbench-0838 `1cd80c9657ea4719ba816be723209854` (tokens: parent output 2,087, child-inclusive output 20,239, input 856,410). The prompts are iteration 5's, for comparison.
- **Result on the target.** The nonce gate held in all three runs: 10 spawns, each with the printed line, each child injected with its role skill, none forked, given model arguments, or left open, and no `send_input`.
- **Other outcomes.** Two runs ended `cw_failure:output` on `Planning` requirements, so only writingbench-0838 is valid (path `PTR`, stop `met`, first review 0 unmet and 0 findings). In writingbench-0519, both attempts quoted a task span with backslash-escaped inner quotes; the reissue brief named `G1`, and the reissue repeated the same quote. In dolomites-1453 turn 2, the first attempt indented `G1.1` under the wrong parent and the reissue dropped four existing IDs. No review returned the draft in this iteration.

### Iteration 7: list every invalid requirement line

- **Motivation.** Reissued `Planning` steps fixed only the line named in the refusal and failed on another: writingbench-0838 `8c5953b3343e408a8fe8b4120327e7de` (iteration 5, fixed `G8.4`, failed `G11.2`) and dolomites-1453 `da6b05afce914b8a90a6174a5c8ed720` (iteration 6). `cw` stopped at the first defect.
- **Change.** `cw` only: a refused `Planning` step lists every invalid requirement line in one refusal, covering grammar, indentation, ID, source, replacement, and vanished-ID defects. The reissue brief carries the full list. A unit test checks a goals file with four defects.
- **Runs.** dolomites-1453 with the iteration 5 turn-2 change request `0d2a76f7c08c4374a4d9d7f8a9ea95ec` (tokens collected before the stop: parent output 2,587, child-inclusive output 18,110, input 794,884), writingbench-0519 `238f8ecffb4146808422d008bbc28b39` (tokens: parent output 4,907, child-inclusive output 55,635, input 2,888,308), and writingbench-0838 `9816f8c4d39f4916b4859d4e5a3190e7` (tokens: parent output 1,808, child-inclusive output 13,228, input 489,630).
- **Result on the target.** Both reissues passed: the reissued `Planning` step in writingbench-0519 after a refused source quote, and a reissued `Translating` step in dolomites-1453 turn 2. No refusal in this iteration held more than one defect, so the multi-line listing was exercised only by the unit test.
- **Mechanism exercise.** writingbench-0519 followed `pPTRTRTRTR`, found 3 unmet requirements in its first review, returned three times from `Reviewing` to `Translating`, and stopped `cap` after four passes. writingbench-0838 stopped `met` after `PTR`. dolomites-1453 developed one requirement and returned twice from `Reviewing` to `Planning` in turn 2.
- **Stopped run.** I stopped dolomites-1453 during turn 2, after step 13, because the iteration's projected token use exceeded its budget. The runner never wrote turn 2's event stream, so for this run the fidelity table's nonce violations (10), missing turn-2 stop, and token counts reflect the stop, not the model.

### Iteration 8: un-escape quote characters before matching a source

- **Motivation.** Backslash-escaped inner quotes in `src` caused refused `Planning` attempts in writingbench-0838 `8c5953b3343e408a8fe8b4120327e7de` (iteration 5), writingbench-0519 `7379279c36f94fdc8247ada5fdf41a28` (iteration 6, both attempts), and writingbench-0519 `238f8ecffb4146808422d008bbc28b39` (iteration 7, first attempt).
- **Change.** `cw` only: before matching a quoted `src`, `\"` becomes `"` and `\'` becomes `'`; the match stays exact otherwise. A unit test checks an escaped quote that matches and an exact mismatch that still fails. The specification's Errata section records the change.
- **Runs.** dolomites-1453 with the iteration 5 turn-2 change request `8a2a0f68b31a4b9c93a856973bc43f22` (tokens: parent output 8,229, child-inclusive output 51,230, input 3,503,963), writingbench-0519 `aae0d9beb97043d8942d8289af03d8cd` (tokens: parent output 4,098, child-inclusive output 39,347, input 1,892,770), and writingbench-0838 `8defa6c769d6466aa5ec89ca7cff174a` (tokens: parent output 3,068, child-inclusive output 21,467, input 997,522).
- **Result on the target.** No `Planning` attempt was refused in this iteration, and no step failed.
- **Mechanism exercise.** Every first review was open, so every run returned from `Reviewing`: writingbench-0519 `PTRTRTRTR` (stop `met`), writingbench-0838 `PTRTR` (stop `met`), and dolomites-1453 turn 2 `PTRTTRPR`, with 6 R→T returns, 1 R→P return, and 1 developed requirement in total.
- **Gate failures in a run the model ended.** dolomites-1453 failed two gates in turn 2. For `fork`, the `Monitor` spawned 3 of its 8 turn-2 children with `fork_context:true`, and those children carry the runner prompt. For `completeness`, the `Monitor` ended turn 2 with a final message after `cw` refused `stop --reason met` because the latest review listed findings, so turn 2 has no stop. Its `failure.kind` is `incomplete`.
- **Harness defect found.** `cw_run` read refused `cw stop` entries as stops, so the gate evaluation of dolomites-1453 raised `KeyError` and the runner recorded the run as `incomplete` through its exception path. The harness readers now skip refused entries, with a unit test. The run is model-class `incomplete` either way. Its gates above are recomputed from its records with the fix.

### Iteration 9: cw prints the delegation call

- **Motivation.** In dolomites-1453 `8a2a0f68b31a4b9c93a856973bc43f22` (iteration 8), the `Monitor` wrote its own spawn code in turn 2 and passed `fork_context:true` for 3 of 8 children, failing `gate:fork`.
- **Change.** `cw` only, at the point of action: `cw step` prints the complete code-mode call (`spawn_agent` with `fork_context: false` and the exact message, the wait loop, and the close) ready to copy. The `Monitor` skill's duplicated code block is replaced by "make exactly the call `cw step` printed". A unit test checks the printed call.
- **Runs.** dolomites-1453 with the iteration 5 turn-2 change request `15b829fb3ccc4f76bcdd6e7d6704707a` (tokens: parent output 4,834, child-inclusive output 24,850, input 1,588,233), writingbench-0519 `7bf534b473174754b2eab30b1a1a5839` (tokens: parent output 3,033, child-inclusive output 28,877, input 1,127,894), and writingbench-0838 `a0c3af1c404748029b361a89cbcdea3f` (tokens: parent output 1,911, child-inclusive output 18,331, input 727,436).
- **Result.** Every gate held in all three runs, in both turns of dolomites-1453: 15 spawns, none forked or overridden, every child injected and closed, every nonce spawned once, and a `met` stop for each turn. No step failed and no `cw` stop was refused.
- **Mechanism exercise.** writingbench-0519 returned once from `Reviewing` (`PTRTR`, 2 unmet requirements in its first review); dolomites-1453 developed one requirement in turn 2 (`PTTR`); writingbench-0838 stopped `met` after `PTR`.

### Iteration 10: a refused stop says the turn is not over

- **Motivation.** In dolomites-1453 `8a2a0f68b31a4b9c93a856973bc43f22` (iteration 8), `cw` refused `stop --reason met` in turn 2 because the latest review listed findings, and the `Monitor` ended the turn with a final message, so turn 2 had no stop and the run failed `completeness`.
- **Change.** `cw` only, at the point of action: a refused `stop` now says that the turn is not over, names the unmet requirements and findings of the turn's latest review with their fixes, and tells the `Monitor` to open the next step with `cw step`. After a failed reissue, the refusal still points to `--reason failure`. A unit test checks the refusal text.
- **Runs.** dolomites-1453 with the iteration 5 turn-2 change request `ee698d78d2314edbb4610cd79fa6a9eb` (tokens: parent output 6,219, child-inclusive output 38,634, input 2,814,203), writingbench-0519 `13332b693c9e47f493d547026ff70519` (tokens: parent output 4,018, child-inclusive output 31,986, input 1,477,786), and writingbench-0838 `c35ee0f4c5ae4626b34096cf4e20278b` (tokens: parent output 2,508, child-inclusive output 15,153, input 619,401).
- **Result.** Every gate held in all three runs, in both turns of dolomites-1453. No step failed. No `cw` stop was refused, so the new refusal text was exercised only by the unit test.
- **Mechanism exercise.** writingbench-0519 returned twice from `Reviewing` (`PTRTRTR`, 2 unmet requirements and 1 finding over its reviews); dolomites-1453 turn 2 returned once (`PTRTTR`); writingbench-0838 stopped `met` after `PTR`.

### Slice 1 closed

Iterations 9 and 10 each ran all three smoke prompts, including the follow-up, with every gate holding in both turns of every run. Slice 1 is complete and awaits its independent re-review.

### Iteration 11: one list of requirement sources

- **Motivation.** The second review found that the change request never reached the role agents: briefs named only `task.md`, no child read `history/turn-02-request.md`, and in dolomites-1453 `ee698d78d2314edbb4610cd79fa6a9eb` (iteration 10) `goals.md` was unchanged by turn 2's `Planning` while the `Monitor` relayed the request through scope labels and `--why`. The new `fidelity.py` metric gives 0 of 0 turn-2 requirements quoting the request for that run.
- **Change.** One source list for requirement sources. `cw` builds it from `task.md` and every `history/turn-NN-request.md`; every brief names each source, the check of `src` quotes uses the same list, and the role skills read every file the brief names. `Planning` quotes the request for a requirement that the request adds or alters, and its skill no longer tells it to `grep` `task.md` only. `fidelity.py` reports, per follow-up turn, the requirements changed in that turn and how many quote its request. Unit tests cover the brief and the metric.
