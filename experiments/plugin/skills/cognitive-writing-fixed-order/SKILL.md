---
name: cognitive-writing-fixed-order
description: "Experiment-comparison variant of the agentic-cog-writer skill for testing a fixed `Planning`, `Translating`, then `Reviewing` order. For internal comparison use only, not the recommended default. Use when a controlled fixed-order comparison is explicitly requested."
---

Role: the Monitor. It selects the next writing process from the fixed order, delegates it, and records its decisions; it writes nothing but `.writing/history.md`.

State: the task in `.writing/task.md`, the draft in `.writing/draft.md` (the task may provide one), the goals in `.writing/goals.md`, and the history in `.writing/history.md`.

Kinds of work: Planning changes the goals; Translating adds prose for the goals; Reviewing corrects existing prose and reports what is needed next. A role reports work of another kind instead of doing it.

Procedure:

1. Read the four state files; a missing file counts as empty.
2. Take the next process in the fixed `Planning`, `Translating`, then `Reviewing` order; each pass starts again with `Planning`. Checking the draft against the task is Reviewing's work.
3. Append one line to `.writing/history.md`: the process, its scope, and the reason.
4. Delegate the process, with its scope, to a fresh planning, translating, or reviewing agent, and wait for it. The Reviewing scope is this sentence and nothing more: check `.writing/draft.md` against `.writing/task.md` and the active goals, correct existing prose, and report what is needed next. The Planning scope is this sentence and nothing more: read `.writing/task.md`, `.writing/draft.md`, and `.writing/goals.md`, and create or develop the goals so that every requirement in the task has a goal.
5. When the Reviewer recommends replacing a goal, decide whether to accept it, record the decision in `.writing/history.md`, and delegate an accepted replacement to the next pass's `Planning`; the `Monitor` does not edit `.writing/goals.md`.

Stop only after `Reviewing`, when no further process is needed; the draft in `.writing/draft.md` is the final document.
