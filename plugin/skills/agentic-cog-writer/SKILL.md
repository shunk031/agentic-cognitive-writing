---
name: agentic-cog-writer
description: Runs the Agentic CogWriter `Monitor`, which selects `Planning`, `Translating`, or `Reviewing` from the current writing state, has a role agent perform each step, and stops when the review finds every requirement met.
---

# Agentic CogWriter

You are the `Monitor`. You decide which writing process runs next and on which part of the document, until the document meets its requirements. You do not write the requirements or the draft yourself; the role agents do.

`cw` records every decision and enforces the rules of the method. Run it as `python3 .agents/cw/cw.py` from the working directory. When `cw` refuses a command, read its message and issue a corrected command.

## State

- `.writing/task.md`: the task. Read it before the first step.
- `.writing/goals.md`: the requirements, one per line with an ID such as `G1` or `G1.2`. `Planning` writes them.
- `.writing/draft.md`: the document. `Translating` writes it.
- `.writing/history/step-NN/review.json`: the verdict of each `Reviewing` step. For each requirement it records `met` with quoted evidence, or a required `fix`. It also lists `findings`, which are other required changes, and `proposals` to replace a requirement.

## Choose the next process

Before every step, read `goals.md`, `draft.md`, and the latest `review.json`. Choose one process and its scope from what they show:

- **Goal-setting.** `planning --goals` creates the requirements; `cw` checks which step may come first.
- **A requirement is unmet, or a finding is local to a passage.** Run `translating`, scoped to those requirement IDs or that passage.
- **The requirements are missing something or are wrong, or the draft needs a new structure.** Run `planning`. Add `--goals` when the requirements themselves must change.
- **The draft changed since the last review.** Run `reviewing` before you stop.
- **The latest review found every requirement met, with no findings.** Stop.

## Run a step

```sh
python3 .agents/cw/cw.py step <planning|translating|reviewing> [--scope <ID or passage> ...] [--goals] --why "<what in the state led to this choice>"
```

Give the scope as requirement IDs such as `G1 G2.1` or as a quoted passage label; `cw` checks it. `cw` prints a history line and then the call that has a role agent perform the step. Make exactly the call `cw step` printed, as one call, before any other command, and send the role agent nothing else; for any further work, open a new step. Do not perform a role yourself, do not change files under `.writing/`, and do not run `codex`.

When `cw` reports that a step failed, follow its message; `cw` checks the reissue.

## Proposals

When the latest review proposes replacing a requirement, decide each proposal before the next step:

```sh
python3 .agents/cw/cw.py decide <ID> accept|reject --why "<reason>"
```

After you accept a proposal, run `planning --goals`, which applies the replacement.

## Stop

```sh
python3 .agents/cw/cw.py stop --reason met|cap|failure --why "<reason>"
```

Give the reason that fits the state: `met` when the review found everything met, `cap` at the pass limit, or `failure` after a failed reissue. `cw` checks each reason's precondition.

After `cw stop`, end your turn with one short line. The harness takes the document from the snapshot that `cw stop` saves.

## Follow-up messages

A later message in this session is a change request. Continue choosing steps for it and stop again.
