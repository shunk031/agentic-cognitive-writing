# Agentic CogWriter redesign, frozen implementation specification (v12)

This specification is final. Every design choice traces to the paper's requirements (C1–C39 in the paper-requirements contract derived from the manuscript), to an author decision (D1–D11 in [`decisions.md`](decisions.md)), or to a measured defect. The author accepted every recommended option of the 20 decisions in the previous specification draft, v11 (D10) and the working method (D11). An implementer can build from this document alone.

**System summary.**

- The LLM `Monitor` chooses each process and its scope (C7, C14, D9.4). It records each choice by calling `cw step`.
- `Planning` writes checkable requirements derived from the task text (D9.1).
- `Translating` drafts the scoped part (D9.2).
- `Reviewing` judges each requirement as met or unmet and quotes evidence. It does not edit (D9.3; D10/1).
- The scored artifact is the per-turn `draft.md` snapshot that `cw stop` writes (D9.5).
- Baselines keep their executed skill text. They receive only the operational changes listed in [Baselines](#baselines).

**Conventions.**

- `D10/n` means D10 resolved Decision n of the previous specification draft, v11, with its recommended option.
- Code paths are repository paths at PR head 27e5fe5 of [shunk031/agentic-cognitive-writing#144](https://github.com/shunk031/agentic-cognitive-writing/pull/144), unless marked `@<commit>`.
- Paper paths are relative to `paper/`.
- "Per review" marks a Codex source line or a smoke measurement that an independent review verified.

## Principles

| Principle              | Statement                                                                                                                                                                                                               |
| ---------------------- | ----------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| Duplication            | One fact lives in one place; everything else is derived from it.                                                                                                                                                        |
| Prose-only enforcement | A procedure that validity depends on is either code at the point of action or a runner gate on its harness trace.                                                                                                       |
| Self-reported facts    | The model never reports what the harness observes.                                                                                                                                                                      |
| Input trust            | Readers re-validate their inputs. Runner-written files are hash-gated by the runner and are excluded from `cw`'s allowance.                                                                                             |
| P-threat               | The threat model is a non-adversarial model that makes mistakes. Spoofing is out of scope, and any detection of it that costs nothing is report-only.                                                                   |
| P-baseline             | Each baseline keeps its executed text. It receives only operational lines without which its executed runs were invalid, D7's removals, the shared contracts, the D10/17 additions, and the artifact its method defines. |
| P-budget               | Every component closes an observed defect or implements a C or D item.                                                                                                                                                  |

## Settled decisions

| #   | Decision                                                                                                                                                                                                                                                                                             | Source                             |
| --- | ---------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- | ---------------------------------- |
| 1   | The `Reviewer` never edits. Any draft change during `Reviewing` is an allowance violation.                                                                                                                                                                                                           | D10/1; D9.3                        |
| 2   | `Planning` may replace requirements on its own initiative. `Reviewer` proposals need the `Monitor`'s `cw decide accept`. Every regeneration records its origin.                                                                                                                                      | D10/2; G10; `sec/03_method.tex:46` |
| 3   | In goal arms, the first step of turn 1 must be `planning --goals`. Turn 2 has a free first choice.                                                                                                                                                                                                   | D10/3                              |
| 4   | A pass is one `Reviewing` step.                                                                                                                                                                                                                                                                      | D10/4                              |
| 5   | The pass count resets per turn, with a cap of 4 per turn.                                                                                                                                                                                                                                            | D10/5; D1                          |
| 6   | The fixed order of A6 and A12 is enforced in `cw`.                                                                                                                                                                                                                                                   | D10/6                              |
| 7   | A step fails when its output check fails, when the allowance is violated, or when a retry marker follows it. An errored child whose output passes is accepted, and its status is reported.                                                                                                           | D10/7                              |
| 8   | A failed step gets one reissue. After that, only `stop --reason failure` is accepted.                                                                                                                                                                                                                | D10/8                              |
| 9   | "Developed" means a changed statement under the same ID.                                                                                                                                                                                                                                             | D10/9                              |
| 10  | No `assignment.md` restatement.                                                                                                                                                                                                                                                                      | D10/10; C4                         |
| 11  | The output language comes from a manifest field fixed before any run. Single-script prompts take their script. A person labels the 103 mixed-script WritingBench prompts, 11 of which are evaluation prompts, by D3's rule.                                                                          | D10/11; D3                         |
| 12  | Primary analysis: a failed run is a non-win. Sensitivity analysis: exclusion.                                                                                                                                                                                                                        | D10/12                             |
| 13  | Failures are classified by the typed `failure.kind` defined [below](#failure-classification). Pilot gate failures are adjudicated before the freeze.                                                                                                                                                 | D10/13                             |
| 14  | An implementation-caused failure is rerun once with the same prompt, budget, and information. A second implementation-caused failure is excluded and reported.                                                                                                                                       | D10/14; `sec/10_appendix.tex:132`  |
| 15  | Mechanism exercise is reported descriptively; there is no go/no-go threshold.                                                                                                                                                                                                                        | D10/15                             |
| 16  | Pilot: 9 non-evaluation prompts per condition, plus follow-ups. The A10 calibration is separate.                                                                                                                                                                                                     | D10/16                             |
| 17  | A3 and B1 keep the `fork_context: false` line and the fork gate, closing of every agent whose wait returned a final status, at most five open agents, and the brief prohibitions. #144's retry-and-continue, three-wait cap, and `Length:` line are reverted. Failed spawns are reported, not gated. Forked children inherited the coordinator prompt in 587 of 923 executed A3 runs (63.6% of runs, per the audit of the executed runs). | D10/17                             |
| 18  | A7's paragraph count uses `wc -w`.                                                                                                                                                                                                                                                                   | D10/18                             |
| 19  | A10 is recalibrated to A4's per-thread run-1 mean, with k ∈ {2, 4, 8, 12, 16}, after A4's scored run 1.                                                                                                                                                                                              | D10/19; `sec/10_appendix.tex:141`  |
| 20  | Budget: parent-only `output_tokens` ≤ 64,000, checked at each parent `turn.completed`. Child-inclusive totals are reported as a covariate.                                                                                                                                                           | D10/20; C36                        |
| 21  | A7 is A8 plus a one-paragraph-per-`Translating`-step unit, generated from the same template.                                                                                                                                                                                                         | D10 (A7); D5                       |
| 22  | Requirements are checkable, carry IDs, and come from the task text, never from rubrics. Derived history. Non-evaluation prompts only. No quality tuning.                                                                                                                                             | D9                                 |
| 23  | Iteration targets process fidelity and mechanism exercise only. The design freezes before the pilot.                                                                                                                                                                                                 | D11                                |

## Architecture of the CogWriter family (A4, A5, A6, A7, A8, A12)

### State

| Component | Path                                                                                                                                                                                                                        | Written by                                          |
| --------- | --------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- | --------------------------------------------------- |
| X         | `.writing/task.md`: the Assignment, Supplied context, and Requested output constraints, byte-identical to the prompt, plus the `information` contract and the manifest output language                                      | Runner; hash recorded in the run directory (C1; D3) |
| D_t       | `.writing/draft.md`                                                                                                                                                                                                         | `Translating`; in A7 only through `cw para`         |
| G_t       | `.writing/goals.md`                                                                                                                                                                                                         | `Planning` with `--goals`                           |
| H_t       | `.writing/history/`: `history.jsonl`, `step-NN/` (`brief.md`, `plan.md`, `review.json`, pre-step snapshots), and `final/turn-NN/draft.md`, all owned by `cw`; `turn-02-request.md` and `retry-NN`, both owned by the runner | `cw`; roles; runner                                 |

**Roles read the task from `task.md`,** and every brief gives its path. The `Monitor` never relays the task or the language (D3 mechanism).

### Requirements (`goals.md`)

```text
- [G1] The proposal states the gap the book fills | src: "What gap does the book seek to fill"
  - [G1.1] The gap is named in the first section | src: G1
- [G2] About 1000 words | src: "approximately 1000 words" | status: replaced by G3
```

Line grammar: `^( {2})*- \[(G\d+(\.\d+)*)\] (.+?) \| src: ("(.+?)"|G\d+(\.\d+)*)( \| status: replaced by (G\d+(\.\d+)*))?$`. `cw` rejects the file when any of the following holds:

- a quoted `src` does not occur in `task.md` after whitespace normalization;
- an ID-valued `src` names a goal that is not an ancestor whose own `src` traces back to a quote;
- a child ID does not extend its parent's ID;
- an ID that existed before has disappeared;
- a `replaced by` target does not exist.

"Checkable" is semantic. It lives in the `Planning` prose, and the fidelity report prints samples (D9.1).

### Roles

| Role          | Reads                                                      | May change while its step is open                   | Report                                     |
| ------------- | ---------------------------------------------------------- | --------------------------------------------------- | ------------------------------------------ |
| `Planning`    | brief, `task.md`, `goals.md`, `draft.md`                   | `goals.md` (with `--goals` only), `step-NN/plan.md` | Final message: findings, next process (D2) |
| `Translating` | brief, `task.md`, `goals.md`, latest `plan.md`, `draft.md` | `draft.md`; in A7, only through `cw para`           | Final message (D2)                         |
| `Reviewing`   | brief, `task.md`, `goals.md`, `draft.md`                   | Nothing                                             | `review.json` through `cw review`          |

The verdict (A5 and A12 omit `verdicts` and `proposals`):

```json
{
  "verdicts": [
    {
      "goal": "G1.1",
      "met": true,
      "evidence": "<non-empty quote found in draft.md>",
      "where": "...",
      "fix": ""
    }
  ],
  "proposals": [
    { "goal": "G2", "replacement": "<statement>", "reason": "..." }
  ],
  "findings": [
    { "kind": "structure|local", "where": "...", "fix": "<required change>" }
  ]
}
```

`cw review` refuses the verdict when any of the following holds:

- an active requirement has no verdict;
- a met verdict's evidence is empty or absent from `draft.md`;
- an unmet verdict has an empty `fix`;
- a finding has an empty `fix`;
- a proposal names an inactive requirement.

Findings list required changes only (D1).

### Commands

`cw` is one standard-library Python file at `.agents/cw/cw.py`, read with `.agents/cw/cw.json`. The sandbox keeps `.agents/` read-only, and `.agents/cw/` is not a skill root (both per the audit of the Codex 0.146 subagent mechanics). Each command prints its history entry as its first output line, because Codex caps the size of `aggregated_output`.

| Command                                                                                   | Caller                                                           | Effect                                                                                                                                                                                                  |
| ----------------------------------------------------------------------------------------- | ---------------------------------------------------------------- | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| `cw step <planning\|translating\|reviewing> [--scope ID-or-label …] [--goals] --why TEXT` | coordinator                                                      | Checks the invariants, snapshots, and appends a history entry with a nonce. Writes `step-NN/brief.md`. Prints the spawn line (delegated arms), or the brief plus the role skill text (in-context arms). |
| `cw review` (JSON on stdin)                                                               | the step's `Reviewer` thread; the coordinator in in-context arms | Validates the verdict and writes `review.json`                                                                                                                                                          |
| `cw decide <goal> accept\|reject --why TEXT`                                              | coordinator                                                      | Records a proposal decision                                                                                                                                                                             |
| `cw stop --reason met\|cap\|failure --why TEXT`                                           | coordinator                                                      | Checks the reason's precondition, then writes `final/turn-NN/draft.md` and the null switch                                                                                                              |
| `cw para --append \| --replace-last` (paragraph on stdin)                                 | A7 coordinator, during a `Translating` step                      | See [A7 paragraph unit](#a7-paragraph-unit)                                                                                                                                                             |

**Brief fields.** All fields are written by `cw`:

- step, attempt, and nonce;
- role and the role skill's absolute path (D4);
- the `task.md` path and the output language;
- scope;
- the active requirements with their latest verdicts;
- accepted proposals (for `Planning`);
- the latest `plan.md` path (for `Translating`);
- `Goal-setting: requested` or `not requested`;
- the prohibitions: no questions, no external sources, no spawning, no `codex`, no `cw step`/`decide`/`stop`.

`--why` text is recorded in history and never appears in a brief.

**Spawn line.** The line is `$<role> Read <absolute brief path> and follow it. [<nonce>]`.

### Invariants enforced by `cw`

| Invariant                                                                                                                                                                                                                                                                               | Source             |
| --------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- | ------------------ |
| **Caller.** The coordinator is the `CODEX_THREAD_ID` of the first `cw` call. `step`, `decide`, `stop`, and `para` require the coordinator. In delegated arms, `review` requires a non-coordinator thread, which `cw` records.                                                           | C14, C15; defect 1 |
| **Allowance.** `goals.md`, `draft.md`, and the `cw`-owned `history/**` each equal their last `cw` record, except what the open step may change. Runner-owned files are excluded, and other files under `.writing/` are free.                                                            | C10, C12, C13      |
| **Failed step.** Triggered by a failed output check, an allowance violation, or a following `retry-NN` marker. `cw` restores the files the step could change to the step snapshot. One reissue of the same process and scope is then allowed; after that, only `stop --reason failure`. | C17; D10/7, D10/8  |
| **Output checks.** `Planning`: `plan.md` non-empty, and `goals.md` valid and non-empty when `--goals` was set. `Translating`: `draft.md` changed. `Reviewing`: `review.json` present.                                                                                                   | C17                |
| **Order.** `process` is one of the three processes. Under fixed order, it must be the next process in P→T→R.                                                                                                                                                                            | C6; D10/6          |
| **First step.** In goal arms, the first step of turn 1 is `planning --goals`. In A5 and A12, `--goals` is refused.                                                                                                                                                                      | C3, C11; D10/3     |
| **Scope.** `Translating` requires at least one scope item. In goal arms, IDs must be active.                                                                                                                                                                                            | D9.2; C18          |
| **Proposals.** Every proposal of the latest review is decided before the next step.                                                                                                                                                                                                     | C23, C24           |
| **Cap.** After the fourth `Reviewing` step of a turn, only `stop` is allowed.                                                                                                                                                                                                           | D1; D10/4, D10/5   |
| **`stop met`.** Goal arms: last step `Reviewing`; at least one active requirement; every verdict met; no findings; every proposal rejected. A5 and A12: last step `Reviewing`; no findings.                                                                                             | D1; D9.4; C3       |
| **`stop cap`.** Four `Reviewing` steps in this turn.                                                                                                                                                                                                                                    | D1                 |
| **`stop failure`.** Only after a failed reissue. The runner marks the run failed.                                                                                                                                                                                                       | D10/8              |

### A7 paragraph unit

A7 is A8 with one change (D10; D5). Each `Translating` step writes exactly one paragraph through `cw para`:

- `--append` adds a paragraph. `--replace-last` replaces only the most recent paragraph. Both apply only inside a `Translating` step, once per step.
- Text containing a blank line, meaning more than one paragraph, is refused. Text over 200 words by `wc -w` is refused. Text over 120 words gets a warning.
- `cw para` records the new `draft.md` hash. In A7, any other change to `draft.md` is an allowance violation.

After each paragraph, the `Monitor` re-selects. Paragraph steps do not count toward the pass cap, because only `Reviewing` steps count (D10/4). Checking a paragraph inside a `Translating` step is not a `Reviewing` step; a pass happens only when the `Monitor` opens `cw step reviewing`. The 1800 s attempt clock bounds a long run of paragraph steps.

### Regeneration and ledger

The derived trace writes each `process_switch` whose `from_process` is `reviewing`, including the null switch at `stop`. Its decision begins `regeneration proposals: none.` or `regeneration proposals: G2 accepted (<why>); G5 rejected (<why>).`, the format `experiments/src/agentic_cogwriter/analysis/ledger.py:16-18,31-58` parses. Goal events come from snapshot diffs:

| Event              | Snapshot change                                                |
| ------------------ | -------------------------------------------------------------- |
| `goal_created`     | A new ID                                                       |
| `goal_developed`   | Same ID, changed statement                                     |
| `goal_regenerated` | `replaced by X`, credited to X; origin `proposal` or `planner` |

### Follow-up turn

The change request arrives inline, as before (`sec/10_appendix.tex:177`). The runner also writes `history/turn-02-request.md`. `cw` starts turn 2 when it sees that file: the pass count resets, and the first choice is free.

### Delegation

```js
const { agent_id } = await tools.multi_agent_v1__spawn_agent({
  fork_context: false,
  message: "<printed line, verbatim>",
});
let r;
do {
  r = await tools.multi_agent_v1__wait_agent({
    targets: [agent_id],
    timeout_ms: 300000,
  });
} while (r.timed_out);
await tools.multi_agent_v1__close_agent({ target: agent_id });
```

Only one role agent is open at a time. The runner's generated config sets `[agents] max_depth = 1` and `max_threads = 6` (`runner.py:294-296`).

A child that never reaches a final status holds its wait until the 1800 s clock ends the attempt. The runner then retries the attempt, writes `retry-NN`, and `cw` fails the open step. The runner reports this case as a hang.

### Arms (one template, one `cw.py`, three keys)

| Arm | goals | order    | execution                   |
| --- | ----- | -------- | --------------------------- |
| A4  | on    | adaptive | delegated                   |
| A5  | off   | adaptive | delegated                   |
| A6  | on    | fixed    | delegated                   |
| A8  | on    | adaptive | in_context                  |
| A7  | on    | adaptive | in_context + paragraph unit |
| A12 | off   | fixed    | in_context                  |

The template has three variable paragraphs:

- **goals.** When goals are off, the `Monitor` is told not to request goal-setting (`sec/09_prompt_configuration.tex:87`).
- **order.** When order is fixed, the cycle is stated (`sec/07_limitations.tex:42`).
- **execution.** Delegated arms spawn. In-context arms perform each role themselves from the brief and role skill that `cw step` prints. A7 adds the paragraph unit.

The `Guidance` block of each role skill is separable, as the generator requires for A9 (C20). Role skills are staged under `.agents/skills/` with `allow_implicit_invocation: false`.

## Baselines

| Baseline | Pin                                         | Changes                                                                                          | Scored        | Completeness                              |
| -------- | ------------------------------------------- | ------------------------------------------------------------------------------------------------ | ------------- | ----------------------------------------- |
| A1       | 42b06d0 (identical to the executed commits) | D7; prompt-section line; contracts                                                               | Final message | Non-empty message                         |
| A11      | 9f81cd0                                     | Contracts                                                                                        | Final message | Non-empty message                         |
| A2, B2   | 42b06d0                                     | D7; prompt-section lines; contracts                                                              | `draft.md`    | `draft.md` exists                         |
| A9       | 334de46                                     | As A2; role text regenerated from the `Guidance` blocks; Re-Write keeps A2's rewrite instruction | `draft.md`    | `draft.md` exists                         |
| A10      | c9dd388                                     | D7; prompt-section lines; contracts; k from D10/19                                               | `draft.md`    | `draft.md` exists                         |
| B1       | 42b06d0                                     | D7; D10/17 additions; contracts                                                                  | `draft.md`    | `draft.md` exists                         |
| A3       | 42b06d0                                     | D7; D10/17 additions; contracts                                                                  | `draft.md`    | Graph root `silent` and `draft.md` exists |

**Line edits.**

- **D7.** Delete the user-control sentence at `writing-single-shot:14`, `writing-linear:16`, `writing-storm-style:20`, `writing-adaptive-task-planning:20`, and `writing-cogwriter-style:22` (all @42b06d0), and at `writing-self-refine:14@c9dd388`.
- **Prompt sections.** Replace each reference to the missing `.writing/assignment.md` with "the Assignment, Supplied context, and Requested output constraints sections of the prompt". The references are at `writing-single-shot:8,18`, `writing-linear:14,20`, `writing-storm-style:24`, `writing-adaptive-task-planning:39`, and `writing-cogwriter-style:18,26` (@42b06d0), and at `writing-self-refine:12,18@c9dd388`.
- **D10/17 additions for A3 and B1.** Copy these lines from @27e5fe5:
  - the task-file copy (A3:91, B1:65);
  - the `fork_context: false` spawn (A3:93, B1:67);
  - "call `wait_agent` on every open agent with `timeout_ms: 300000` while it returns `timed_out`";
  - close every agent that reached a final status (A3:95 together with the close clause of A3:97; B1:69 together with B1:71);
  - "Keep at most five agents open at a time.";
  - the brief template (A3:99-109, B1:73-83) without its `Length:` line, and with `Output language:` set to the manifest value.
- **B1 fallback sentence.** Delete it (`writing-cogwriter-style:35@42b06d0`), because it contradicts the D10/17 delegation lines.
- **Acknowledgment notes.** None in any baseline.

## Runner

### Inputs and scoring

- **CogWriter arms.** The runner writes `task.md` and records its hash. The manifest language goes into the prompt and into `task.md` for every condition.
- **Scored artifact.**

  - CogWriter arms: `history/final/turn-NN/draft.md`.
  - Draft baselines: `draft.md`.
  - A1 and A11: the final message.

  The artifact goes to `output.normalized.txt`; any other final message goes to `final-message.txt`. Follow-up runs score each turn.

- **Deleted.** The 0.5 ratio gate and the acknowledgment check (`runner.py:84,312-326,338-345`). The empty-message rule for draft-scored arms (`runner.py:328-332`). `workspace.md`. Baseline trace gating.
- **Completeness.** Every arm requires `turn.completed` (`execution.py:176-179`). Beyond that:
  - CogWriter arms: `cw stop --reason met|cap`.
  - Baselines: the completeness column of the [Baselines](#baselines) table.
- **Retry marker.** On every attempt retry after a timeout or crash, the runner writes `history/retry-NN`. It does not write one for the follow-up resume.

### Gates

| Gate                                                                                                                          | A4, A5, A6 | A3, B1         | A7, A8, A12 | A1, A2, A9, A10, A11, B2 |
| ----------------------------------------------------------------------------------------------------------------------------- | ---------- | -------------- | ----------- | ------------------------ |
| Child has no parent prompt (fork)                                                                                             | gated      | gated (D10/17) | —           | —                        |
| No `model`, `reasoning_effort`, or `service_tier` in spawn arguments                                                          | gated      | gated          | —           | —                        |
| Spawn prompt equals the printed line; each nonce spawned exactly once (nonces failed by `retry-NN` exempt)                    | gated      | —              | —           | —                        |
| No `codex` command in a child; no `resume_agent` call                                                                         | gated      | —              | —           | —                        |
| No top-level `command_execution` or `file_change` between a spawn and its close; no top-level `file_change` under `.writing/` | gated      | —              | —           | —                        |
| Zero spawns                                                                                                                   | —          | —              | gated       | gated                    |
| Runner-file hashes unchanged; completeness                                                                                    | gated      | gated          | gated       | gated                    |
| Failed spawns (empty `receiver_thread_ids`); unclosed children; hangs                                                         | reported   | reported       | —           | —                        |

### Failure classification

The runner writes `failure.kind` into the manifest. The first matching row wins.

| `failure.kind`                           | Detection                                                                                                                                                                               | Class          |
| ---------------------------------------- | --------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- | -------------- |
| `harness_error`                          | Runner exception outside model execution: configuration, I/O, token or rollout collection                                                                                               | Implementation |
| `provider_error`                         | A stdout `turn.failed` event in the final attempt. Rollouts drop Error and StreamError (`rollout/src/policy.rs:122,158`, per review).                                                   | Implementation |
| `timeout_provider`                       | The attempt clock expired, and stdout carried a stream-error or reconnect event with no `item.completed` after it, within the last 1,500 s (the 300 s stream idle timeout × 5 retries). | Implementation |
| `timeout`                                | Any other clock expiry. Reported as `hang` when a delegated child had no final status.                                                                                                  | Model          |
| `cw_failure:<output\|allowance\|caller>` | `cw stop --reason failure`                                                                                                                                                              | Model          |
| `gate:<name>`                            | A gate in the table above                                                                                                                                                               | Model          |
| `budget`                                 | Decision 20                                                                                                                                                                             | Model          |
| `incomplete`                             | No completeness record                                                                                                                                                                  | Model          |

Implementation-class failures are rerun once (D10/14).

### Token accounting

The rule applies to every condition, before the A10 calibration and the budget report:

1. Build one usage series per unique thread ID from the attempt events and child rollouts, deduplicating `sessions/attempt-NNN` copies.
2. Split each series into segments at every drop in the running totals. A drop follows a context reset (`fill_to_context_window`, `codex-rs/protocol/src/protocol.rs:2113-2126`, per review).
3. For a forked child, subtract the parent's totals at the fork point from the child's first segment. A forked child starts from the parent's totals (`session/mod.rs:1353-1364`; `spawn.rs:79`, per review). This matters only for restating executed runs; it overcounted executed A3 by about 35%.
4. Per segment, take the maximum of `output_tokens`, `input_tokens`, and `cached_input_tokens`.
5. Sum over segments, then over threads. `output_tokens` already includes reasoning.

**Budget (D10/20).** The budget statistic is the parent's `output_tokens` at each `turn.completed`, against a limit of 64,000. A4's child tokens are not counted, while A10's tokens are all parent tokens. A10 recalibrated to the child-inclusive A4 mean may therefore approach the cap: across 19 smoke A4 runs, child-inclusive output was 1.67–4.36× the parent-only figure, with 7 of 19 below 2.0× (per review). The pre-registered check: the runner reports every A10 calibration or scored run whose parent output exceeds 90% of 64,000, and any `budget` failure in A10 is reported with the contrast.

## Measured defects of the executed study

The paper reports these; this design does not fix them in the executed data.

| #   | Defect                                                                                                                   | Evidence                                                                                             |
| --- | ------------------------------------------------------------------------------------------------------------------------ | ---------------------------------------------------------------------------------------------------- |
| T1  | Token accounting counted the parent only, for output and input (`execution.py:144-180`; `analysis/aggregate.py:829-841`) | `a4-wb0354`: parent output 8,914; children 9,212 (per review)                                        |
| T2  | Running totals summed across resumed and follow-up turns                                                                 | `a4-hbchat047`: 12,923 + 27,791 counted, where 27,791 is the true two-turn parent total (per review) |
| T3  | Reasoning counted twice in the budget statistic (`execution.py:175`)                                                     | `output_tokens` already includes reasoning                                                           |
| T4  | Child agents outside the 64,000 budget (`runner.py:955-960`)                                                             | `a4-hbchat047`: 121,265 per-thread output (per review)                                               |
| T5  | Forked children's totals included the parent's                                                                           | About 35% overcount in executed A3 (per review)                                                      |
| F1  | 218 "fallback" runs were forked children re-entering the `Monitor`                                                       | Audit of the executed runs, measured defect 1                                                          |

## Paper claims that change

| Location                                                                                                                                                                                                                                                                              | Change                                                                                                                                                                                                                      | Source                 |
| ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- | --------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- | ---------------------- |
| `sec/00_abstract.tex:7`; `sec/01_introduction.tex:28`; `sec/06_discussion.tex:1`                                                                                                                                                                                                      | "Role-guided pass" now means a pass ending in a non-editing `Reviewing` step                                                                                                                                                | D10/1, D10/4           |
| `sec/03_method.tex:43`                                                                                                                                                                                                                                                                | The `Reviewer` evaluates and does not revise                                                                                                                                                                                | D10/1                  |
| `sec/03_method.tex:20,23-24,41`; `tab/architecture-comparison.tex:180`; `tab/appendix-comparison.tex:42`                                                                                                                                                                              | Requirements; G_0 is created by the first step                                                                                                                                                                              | D9.1; D10/3            |
| `sec/03_method.tex:49`; `sec/10_appendix.tex:57`; `fig/tex/overview.tex`                                                                                                                                                                                                              | Stop rule; pass definition; per-turn cap                                                                                                                                                                                    | D1; D9.4; D10/4, D10/5 |
| `sec/03_method.tex:46`; Tables 6, 11, 26; `tab/process-dynamics.tex:22`; `tab/appendix-process.tex:25`; `sec/10_appendix.tex:181`                                                                                                                                                     | Regeneration counted by origin                                                                                                                                                                                              | D10/2                  |
| `sec/10_appendix.tex:47`; Table 11                                                                                                                                                                                                                                                    | "Developed"                                                                                                                                                                                                                 | D10/9                  |
| `sec/10_appendix.tex:48-49,205`; Tables 18, 27                                                                                                                                                                                                                                        | Ledger from `cw decide`                                                                                                                                                                                                     | C24                    |
| `sec/04_experiments.tex:15`; `sec/10_appendix.tex:46`                                                                                                                                                                                                                                 | Goal events derived in every goal arm                                                                                                                                                                                       | D5                     |
| `sec/10_appendix.tex:58,148`; `sec/07_limitations.tex:42-43`                                                                                                                                                                                                                          | Cycle enforced by `cw`                                                                                                                                                                                                      | D10/6                  |
| `sec/10_appendix.tex:53,55-57`; Figure 2; Table 6; `sec/05_results.tex:35,65-66`; `sec/10_appendix.tex:150`                                                                                                                                                                           | Paths, stop reasons, and A12 counts recomputed                                                                                                                                                                              | C29–C31; D10/4, D10/6  |
| `sec/10_appendix.tex:60-65`; `sec/07_limitations.tex:47`                                                                                                                                                                                                                              | Fallback removed (F1)                                                                                                                                                                                                       | D4                     |
| `sec/04_experiments.tex:19-20`; `sec/07_limitations.tex:46`; `sec/10_appendix.tex:106`; `tab/appendix-runtime-settings.tex:2`                                                                                                                                                         | A7 is A8 plus the paragraph unit. "Role context" no longer differs from A8; only decision granularity does.                                                                                                                 | D10 (A7)               |
| `sec/09_prompt_configuration.tex:34`                                                                                                                                                                                                                                                  | Interactive passages removed                                                                                                                                                                                                | D7                     |
| `sec/09_prompt_configuration.tex:6,29-30,43-97,87-88`; `sec/07_limitations.tex:26`; `sec/10_appendix.tex:156-162`                                                                                                                                                                     | Manifest language. The runner writes `task.md`, and roles receive its path instead of a `Monitor` relay (D3 mechanism). `$role` plus path. Displays add `cw.py` and the brief template. A5 findings only. Drift recomputed. | D3, D4, D5; D10/11     |
| `sec/10_appendix.tex:114,131,149`; `sec/07_limitations.tex:23`                                                                                                                                                                                                                        | A9 regenerated; B1 files differ from the consensus version; A12 built from configuration                                                                                                                                    | D10/17; D5             |
| `sec/10_appendix.tex:191`; `tab/appendix-example.tex`                                                                                                                                                                                                                                 | Example uses `task.md` and G1                                                                                                                                                                                               | D10/10                 |
| `sec/04_experiments.tex:25,44,48`; `sec/05_results.tex:17`; `sec/10_appendix.tex:134,141,151`; `sec/07_limitations.tex:17`; `tab/appendix-single-context.tex:31`; `tab/appendix-process.tex:12`; Table 11 tokens; `tab/appendix-runtime-settings.tex:27-36`; compute-matched analysis | Tokens recomputed (T1–T3, T5); budget restated as parent-only (T4)                                                                                                                                                          | C36; D10/19, D10/20    |
| `sec/05_results.tex:17`; `sec/10_appendix.tex:115,123,132,133,142,179`; `sec/07_limitations.tex:22,30-31`; `tab/appendix-runtime-settings.tex:14`                                                                                                                                     | Failed runs counted as non-wins; reruns; baseline completeness                                                                                                                                                              | D10/12–14              |
| Table 7                                                                                                                                                                                                                                                                               | Failure rule; gates; budget statistic                                                                                                                                                                                       | D10/7, D10/8, D10/20   |
| `docs/experiments/protocol.md:183`                                                                                                                                                                                                                                                    | Delegation rule                                                                                                                                                                                                             | D4                     |

## Implementation plan (D11)

Start a new branch from 27e5fe5 and open one PR that supersedes [shunk031/agentic-cognitive-writing#144](https://github.com/shunk031/agentic-cognitive-writing/pull/144). From #144, keep:

- the `[agents]` pins;
- role-skill staging;
- the contracts;
- `spawned_roles` (`experiments/src/agentic_cogwriter/runner/skill_checks.py:71-92`);
- the generator;
- the paragraph refusal logic (`writing_state.py:335-379`), moved into `cw para`.

Delete:

- `log`;
- `reports.md` and `paragraphs.jsonl`;
- the acknowledgment lines and checks (`skill_checks.py:31-57,152-190`);
- the per-variant references;
- `delegation_fallback.py`;
- leading-`Planning` reconstruction.

### Vertical slices

Each slice must pass a smoke test before the next slice starts.

| Slice | Builds                                                                                                              | Smoke exit criterion (`fidelity.py`)                                                                                                                                       |
| ----- | ------------------------------------------------------------------------------------------------------------------- | -------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| 1     | `cw.py` (all commands); A4 `Monitor` skill and role skills; runner writes `task.md` and the language; `fidelity.py` | A4 on 3 smoke prompts. Every A4-applicable gate in `fidelity.py` holds. At least one run has more than one `Reviewing` step, or the miss is explained from the logs.       |
| 2     | The generator emits A5, A6, A8, A7, and A12 from the same template                                                  | Each arm on 2 smoke prompts with every gate holding; A6 order is P→T→R; A7 makes one `cw para` write per `Translating` step                                                |
| 3     | Baselines reset to their pins, then the line edits                                                                  | Each baseline on 1 smoke prompt with completeness and its gates holding                                                                                                    |
| 4     | Runner: gate table, `failure.kind`, completeness, scoring, retry marker, token rule, budget                         | Replay of smoke round 4 logs reproduces 121,265 for `a4-hbchat047`. A forced-timeout probe writes `retry-NN` and fails the open step. A follow-up probe scores both turns. |

### Fidelity report

`experiments/src/agentic_cogwriter/analysis/fidelity.py <run-root>` prints a per-run table and a per-condition summary. It reads only harness records: attempt events, child rollouts, `history/`, `review.json`, snapshots, manifests, and stdout.

| Column      | Definition                                                                                                      |
| ----------- | --------------------------------------------------------------------------------------------------------------- |
| `gates`     | Pass or fail for each gate in the [gate table](#gates)                                                          |
| `spawn`     | Spawns; forked children; spawns with model arguments; failed spawns; unclosed children                          |
| `inject`    | Children with a `<skill>` block naming their role; in-context role-skill hash present in the `cw step` output   |
| `nonce`     | Each printed nonce spawned exactly once (yes/no; count of violations)                                           |
| `allowance` | `cw` allowance violations and restores                                                                          |
| `stop`      | Stop reason per turn                                                                                            |
| `path`      | Process sequence per turn, for example `PTRTR`                                                                  |
| `returns`   | R→T and R→P counts                                                                                              |
| `unmet`     | Unmet verdicts and findings in each review, first review shown separately                                       |
| `goals`     | Goals created, developed, and regenerated (by origin); proposals accepted and rejected                          |
| `lang`      | Majority script of the scored artifact against the manifest language                                            |
| `tokens`    | Parent `output_tokens` per turn (budget statistic); per-thread output, input, and cached; child-inclusive total |
| `failure`   | `failure.kind`                                                                                                  |
| `samples`   | Three requirement lines per run with their `src`, for reading "checkable"                                       |

### Iteration loop and rules

**Loop.** Change one thing, run the affected conditions on 1–3 smoke prompts each, run `fidelity.py`, and record the change.

**Smoke pool.** The pool is fixed:

- dolomites-349, -480, -530;
- hellobench-chat_047;
- writingbench-0210 and -0354 (Chinese);
- writingbench-0692;
- writingbench-0049 and -0051 (English instructions mentioning China, for the language check).

A check script asserts the following before every iteration:

- every smoke prompt lies outside the `hard`, `hard100`, and `pilot` lists in `experiments/prompts/prompt_sets.json`;
- no smoke prompt is one of the 12 A10 calibration prompts (`experiments/conditions/README.md:56`);
- the pilot draws its 9 prompts per condition from the remaining non-evaluation prompts, with a fixed seed before the pilot;
- the smoke, pilot, and calibration sets are pairwise disjoint.

**Rules (D11).**

- A change may target only a gate failure or a mechanism-exercise metric in `fidelity.py`: `returns`, `unmet`, `goals`, `path`, `inject`, or `nonce`.
- Each change goes in `experiments/CHANGELOG-redesign.md`, with the motivating run IDs and metric values.
- No one reads, scores, or judges output text for quality during iteration.
- Prompt changes are prose-only edits to the `Monitor` or role skills, or `cw` mechanics. Quality targets, word-count targets, and rubric language are never added.
- After the last slice, the design freezes: commits are tagged and their hashes recorded in manifests. The pilot follows; only an implementation-class gate failure may reopen the design. Then the scored runs.

**Baseline exercise reference.** The executed figures are proxies, measured from harness records under the old instruction, against which iteration progress is read:

- open findings in first reviews: 6 of 21 overall and 3 of 11 for A4 (smoke rounds 2–4);
- exact P→T→R turn 1: 12 of 17 delegated runs in rounds 2–4;
- R→T: 146 of 886 A4 runs and 56 of 874 A6 runs in the full runs.

### Unit tests

| Test                      | Asserts                                                                                                                                                                                       |
| ------------------------- | --------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| `test_cw_caller`          | `step`, `decide`, `stop`, and `para` from a non-coordinator `CODEX_THREAD_ID` are refused; delegated `review` from the coordinator is refused                                                 |
| `test_cw_allowance`       | A `draft.md` change during `Reviewing` triggers a restore and a reissue; a second violation allows only `stop failure`; runner files and `.writing/source.md` are ignored                     |
| `test_cw_output_check`    | Each process's missing output fails the step and restores the snapshot                                                                                                                        |
| `test_cw_retry_marker`    | `retry-NN` fails the open step; `turn-02-request.md` does not                                                                                                                                 |
| `test_cw_order`           | Fixed order refuses out-of-cycle processes; adaptive order accepts any                                                                                                                        |
| `test_cw_first_step`      | Goal arms refuse a non-`planning --goals` first step in turn 1 and accept any in turn 2; A5 refuses `--goals`                                                                                 |
| `test_cw_scope`           | `Translating` without scope, or with an inactive ID, is refused                                                                                                                               |
| `test_cw_goals_grammar`   | Bad `src` quote, missing ancestor, vanished ID, and bad `replaced by` are each refused                                                                                                        |
| `test_cw_review`          | Each refusal rule of `cw review`                                                                                                                                                              |
| `test_cw_proposals`       | The next step is refused until every proposal is decided; the ledger text parses with `ledger.py`                                                                                             |
| `test_cw_cap`             | A fifth `Reviewing` step in a turn is refused; the cap resets in turn 2                                                                                                                       |
| `test_cw_stop`            | `met`, `cap`, and `failure` preconditions for goal and no-goal arms                                                                                                                           |
| `test_cw_para`            | Append; replace-last; a second write in one step refused; a blank line inside refused; more than 200 `wc -w` refused; warning above 120; a non-`cw` change to `draft.md` in A7 is a violation |
| `test_cw_snapshot`        | `stop` writes `final/turn-NN/draft.md`; turn 2 does not overwrite turn 1                                                                                                                      |
| `test_token_rule`         | Resume with running totals; context reset with zeroed fields; forked child minus parent at the fork; `a4-hbchat047` gives 121,265                                                             |
| `test_failure_classifier` | Each `failure.kind` from synthetic stdout and manifests, including a recovered reconnect followed by a hang (`timeout`) and a terminal `turn.failed` (`provider_error`)                       |
| `test_generator_equality` | Every arm's skill equals the template except its three variable paragraphs; `--check` is clean; A9 stage files match the `Guidance` blocks                                                    |
| `test_gates`              | Every gate holds on the replayed smoke round 4 known-good runs                                                                                                                                |

## Risks

- **Lenient review.** If the `Reviewer` marks everything met, runs end after one pass. The fidelity report shows this; D11 allows mechanism changes only.
- **Ceiling and construct.** A single draft may already meet the requirements. A gain may reflect explicit checking rather than the process framing.
- **Length.** More steps lengthen outputs, and the length analyses are descriptive (`sec/07_limitations.tex:50`).
- **Failure asymmetry.** Exposure routes differ by arm. The report lists them per arm and route.
- **Residual write gap.** A top-level shell write to a state file can land between `cw step` and the spawn, or after the close and before the next `cw` call. Such a write is attributed to the step. It has not been observed.
- **Budget asymmetry.** The budget counts parent tokens only, so A4's children are uncounted. The A10 cap check reports any binding.
- **Platform.** Everything is pinned to Codex 0.146.
