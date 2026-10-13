# Redesign changelog

This changelog records each change to the redesigned CogWriter arms during the smoke iterations of [the redesign specification](../docs/experiments/redesign/design.md). Each iteration makes one change and records the `fidelity.py` metric and run IDs that motivated it, the token counts of its runs, and the result. Run IDs are the runner's run directory names. Iterations target process fidelity and mechanism exercise only, measured from harness records on non-evaluation prompts.

## Slice 1

### Baseline build

- **Change.** `cw` with every command and invariant, the A4 `Monitor` skill and the three role skills, the runner's `task.md`, `cw` staging, snapshot scoring, A4 gates, `failure.kind`, and the per-thread token rule, and `fidelity.py`.
- **Spec erratum.** Six of the nine specified smoke prompts are A10 calibration prompts. Slice 1 runs only writingbench-0210, -0049, and -0051, which pass the disjointness check; later slices use the replacement pool recorded in the specification's Errata section.

### Iteration 1: the language line

- **Runs.** writingbench-0210 `3409cdedb82e49ec80b44eaf3e70fdfd`. Tokens: child-inclusive output 5,231, input 340,158.
- **Motivation.** Run `3409cded`: `failure` `cw_failure:output`, path `t1:pp`, 2 failed steps. Both `Planning` attempts quoted "Output language: Chinese", which `task.md` held only as a heading and a value, so `cw` refused the requirements.
- **Change.** `task.md` and the prompt state the language as the single line `Output language: <language>`.
- **Result.** In iteration 2, no `Planning` step quoted the language line as a heading again; two of the three runs still failed on other source quotes.

### Iteration 2: three prompts after the language fix

- **Runs.** writingbench-0210 `c390432af52f47b38b50695e1e0d9580`, writingbench-0049 `365f3ae28e9342699a75f521b3ddc5f6`, writingbench-0051 `6dd3a290b0824b6e8b85e30846ee6776`. Tokens: child-inclusive output 24,862, input 1,331,207.
- **Metrics.** One valid run (`a4-wb0210`: path `t1:pPTR`, stop `met`, first review 0 unmet and 0 findings). Two runs ended in `cw_failure:output` after both `Planning` attempts wrote `src` values that are not exact spans of `task.md`: two spans joined with "and" or ";", an ellipsis, a translated label, and backslash-escaped inner quotes. Five failed steps in three runs. In `a4-wb0049` the `Monitor` dropped `close_agent` from the delegation block, leaving 2 children unclosed and failing the `top_level_writes` gate.
- **Changes for iteration 3.** Two changes, each tied to its own metric. `Planning`: `src` is one span copied character for character, never translated, shortened, escaped, or joined, and each span is confirmed with `grep -F`. `Monitor`: the delegation block prints the child's final status after `close_agent` and runs as one call.

### Iteration 3: exact sources and closing children

- **Runs.** writingbench-0210 `4f4ba9ace6b3452387ba3539cf8f2068`, writingbench-0049 `9faebb87870045d7a8ea781bc2e1867c`, writingbench-0051 `1ca510232cc34926acf7f0b900d61ceb`. Tokens: child-inclusive output 38,689, input 1,787,457.
- **Deviation.** This iteration made two changes, one per failure class, against the one-change rule.
- **Result.** Every gate holds in all three runs. Every spawn passed the printed line, every child was injected with its role skill and closed, and no child was forked or given model arguments. One failed step remains: in `a4-wb0051` the first `Planning` attempt indented `G1.1.1` under the wrong parent, and the reissue passed. Paths are `PTR`, `PTR`, and `pPTR`; every run stopped `met` after one pass.
- **Mechanism exercise.** Every first review found 0 unmet requirements and 0 findings, so no run returned from `Reviewing`, and no requirement was developed or regenerated. The logs show `Reviewing` met verdicts whose evidence is a short excerpt, such as a title, for requirements about the whole draft; one `Reviewer` measured the length before judging it.
- **Change for iteration 4.** `Reviewing` marks a requirement met only when the draft meets it fully, and measures whole-draft requirements, such as a length, a number of items, or every required section, before judging them, recording the measurement in `where`. A partial match is unmet. The change targets the `unmet` metric and adds no quality criterion.

### Iteration 4: measured verdicts

- **Runs.** writingbench-0210 `558643bf9b474a3d92c8ff9e2dbf93cc`, writingbench-0049 `5ef36d24d32c46769cd9b45aa40e0e28`, writingbench-0051 `1a90b3eabcb14857abb5ac64b1958e7c`. Tokens: child-inclusive output 36,918, input 1,611,290.
- **Result.** Every gate holds in all three runs. Paths are `pPTR`, `PTR`, and `PTR`. The one failed step is again a first `Planning` attempt whose child ID did not extend its parent's ID; the reissue passed. The `Reviewer`s now record measurements in `where`, such as 129 characters against a 100–150 character requirement, all 11 requested technical parameters, and all 12 chapters and 21 articles. Every requirement was still met at the first review, so no run returned from `Reviewing`.
- **Slice 1 exit criterion.** No run had more than one `Reviewing` step. The logs explain the miss: each first review measured the whole-draft requirements and found them met with verbatim evidence, so `stop met` was the correct move under the stop rule. The three prompts are short WritingBench tasks with explicit constraints that one draft already meets, which is the specification's ceiling risk. The iteration budget of four is spent.

### Tooling fix during slice 1

- `fidelity.py` skips refused `cw` entries when it counts reviews, decisions, and goal events; iteration 2's report failed on a refused `cw review` entry.

### Errata after slice 1

- **Reissue reason.** Motivated by the first `Planning` attempts that failed the goals grammar in runs `a4-wb0051` (`it3`) and `a4-wb0210` (`it4`), 2 of 6 first attempts. A reissue brief now carries `cw`'s refusal reason verbatim. Not yet smoke-tested.
- **`stop cap`.** A cap no longer requires every proposal to be decided; the stop entry reports the undecided ones.
- **Turn-2 requirement sources.** `Planning` may quote a runner-written turn request as well as `task.md`.

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

- **Change under test.** The review fixes and errata above, at commit `a2b99dd`; no prompt change. Prompts from ranks 105–112 of the replacement pool.
- **Runs.** dolomites-1453 with a turn-2 change request `11f16a501a9b4d7390f09a29a875e220` (tokens: parent output 9,541, child-inclusive output 55,166, input 4,074,064), writingbench-0519, whose topic is Chinese law, `1ac3a6e5282d4db5992ded2c4131a85a` (tokens: parent output 4,384, child-inclusive output 43,808, input 2,014,560), and writingbench-0838 `8c5953b3343e408a8fe8b4120327e7de` (tokens: parent output 1,816, child-inclusive output 13,860, input 569,676). Tokens: child-inclusive output 112,834, input 6,658,300.
- **Mechanism exercise.** For the first time, reviews found unmet requirements and findings. writingbench-0519 followed `PTRTRTRTR`, with 4 unmet requirements and 2 findings in its first review and three R→T returns, and stopped `met` after four passes. dolomites-1453 stopped `met` in each turn; turn 2 followed `PtTRTRPR`, with one R→T and one R→P return. No requirement was developed or regenerated, and no proposal was made.
- **Reissue reason.** Three reissue briefs carried `cw`'s refusal reason. Two reissues passed: a `Planning` source quote in dolomites-1453 step 2, and an unchanged draft in its step 7. One failed: in writingbench-0838 the reissued `Planning` fixed the reported `G8.4` source but wrote a backslash-escaped quote in `G11.2`, so the run ended `cw_failure:output`.
- **Follow-up path.** The runner wrote `turn-02-request.md`, each turn stopped on its own, and both snapshots exist. Turn 2's new requirements took ancestor IDs as their `src`, so no requirement quoted the turn request.
- **Gate failure.** dolomites-1453 failed `gate:nonce`. After step 7 closed, the `Monitor` spawned a second agent with a message it wrote around the step-7 spawn line, then sent that agent its own instructions through `send_input`. The child was not injected with its role skill (12 of 13 injected). The gate caught an off-protocol spawn as designed.
- **Candidates for the next iteration, one change each.** (1) `Monitor`: spawn only with a spawn line that `cw step` has just printed, send a role agent no other message, and run a new step for further work. (2) `cw`: report every invalid requirement line in one refusal, so that a reissue can fix them all.
