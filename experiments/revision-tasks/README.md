# Revision-requiring task experiment

This exploratory experiment tests whether adaptive process selection helps when a task requires revision. On the length-selected benchmark subsets, the full system's `Monitor` (A4) rarely departs from one `Planning`, `Translating`, and `Reviewing` cycle, and its quality is not separable from the Fixed-order ablation (A6). Here each system first completes a benchmark task and then, in the same session, receives a mid-task change that forces a revision. The key contrast is A4 against A6 on the revised document.

This file is the pre-specified plan. It was committed before any change text or system output was generated, and the analysis follows it as written. Any deviation is reported with the results.

## Prompts

The sample contains 60 prompts, 20 from each benchmark's `hard100` subset in [`prompt_sets.json`](../prompts/prompt_sets.json): WritingBench, HelloBench, and DoLoMiTes. [`make_changes.py`](make_changes.py) draws the sample with `random.Random(20260908)`, visiting benchmarks in the order `writingbench`, `hellobench`, `dolomites` and calling `sample(sorted(hard100), 20)` for each. The script then shuffles each benchmark's 20 prompts with the same generator and assigns change types cyclically, which gives seven, seven, and six prompts of the three types per benchmark.

## Mid-task change

Each prompt receives exactly one change of one of three types:

| Type         | Change                                                                                                          |
| ------------ | --------------------------------------------------------------------------------------------------------------- |
| `constraint` | A new or changed constraint on audience, scope, a required section, or format                                   |
| `evidence`   | New evidence the document must incorporate, or evidence that contradicts a premise the assignment invites       |
| `conflict`   | A requirement that conflicts with part of the original assignment and forces the writer to restructure the text |

`gpt-5.6-sol` writes each change once, before any system runs, from a fixed instruction in [`make_changes.py`](make_changes.py) with seed 20260908 and medium reasoning effort. The instruction asks for two to five sentences in the assignment's language, phrased as the requester's message, self-contained so that no outside research is needed, and substantive enough to require revising the document. The changes are frozen in [`changes.jsonl`](changes.jsonl), and every condition receives the identical turn-2 message stored in that file's `followup_message` field:

```text
The requester sent a change to the assignment after reading your first version.

[Change]
<change text>

Revise your document so that it satisfies the original assignment as modified by this change. Where the change conflicts with the original assignment, the change takes precedence. The final response must contain the complete revised text itself, not a summary of the edits or a link to a workspace artifact.
```

## Conditions and turns

The conditions are A4 (Agentic CogWriter), A6 (Fixed-order), and A2 (Staged). A1 (Single-pass) is added only if the first three conditions finish all 60 prompts before 2026-10-13 03:00 JST. Generation uses the paper's Codex settings: `gpt-5.6-luna` at medium reasoning effort, Codex CLI 0.146.0 in the experiment Docker image, the shared timeout, retry, no-retrieval, and output-budget rules, and generation seed 20260908.

Each run has two turns in one Codex session:

- Turn 1 is the unchanged benchmark run. The runner validates its product, trace contract, and delegation exactly as in the main experiment, and a run that fails turn-1 validation gets no turn 2.
- Turn 2 resumes the same session with `codex exec resume <session_id>` and sends the condition-independent turn-2 message. The runner applies the final-product check to the turn-2 response and records the turn-2 trace events without applying the turn-1 trace contract, because A2's three-event contract describes one turn.

The runner keeps the turn-1 response, the turn-1 trace, and the turn-2 message beside the final run artifacts, and the run manifest's `followup` block records their hashes and the turn-1 trace length. Two prompts are run end to end, including judging, as a smoke test before the full run. Smoke runs count toward the results only when no code, prompt, or configuration changed between the smoke test and the full run.

## Judging

The judge is `gpt-5.6-sol` at medium reasoning effort with seed 20260908. The pairwise template [`pairwise-revision-v1.md`](../prompts/judges/pairwise-revision-v1.md) adapts [`pairwise-v1.md`](../prompts/judges/pairwise-v1.md): the assignment shown to the judge is the original task followed by the turn-2 message, and the judge chooses the final document that better satisfies the task as changed. Both presentation orders are judged with presentation seed 20260908. A prompt whose two presentations disagree, including a winner against a tie, counts as a tie. The generator and judge share the GPT family, so the judge configuration records the family audit as exploratory same-family scoring.

The contrasts are A4 against A6, the key contrast, and A4 against A2. Each contrast reports prompt-level wins, losses, and ties for A4, the win rate over non-tied prompts, and an exact two-sided sign test over non-tied prompts, overall and per benchmark. No multiplicity correction is applied; the experiment is exploratory and two contrasts are reported.

## Process traces

For A4 and A6, the analysis splits each completed trace at the recorded turn-1 length and applies the existing process-sequence extraction in [`process_sequences.py`](../src/agentic_cogwriter/analysis/process_sequences.py) to the turn-2 events. It reports the share of runs whose turn 2 switches to `Planning`, records a `goal_regenerated` event, or records no process events, together with the turn-2 process sequences.

## Reproduction

[`run_revision.py`](run_revision.py) runs every prompt and condition through the Docker runner with the `--followup-file` option, scores the pairs, and writes the sanitized results JSON. The results file under [`paper/results/revision-tasks/`](../../paper/results/revision-tasks/) replaces local run paths with labels.
