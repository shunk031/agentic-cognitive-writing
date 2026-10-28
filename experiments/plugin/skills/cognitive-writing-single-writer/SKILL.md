---
name: cognitive-writing-single-writer
description: "Experiment-comparison variant of the agentic-cog-writer skill that runs each selected `Planning`, `Translating`, or `Reviewing` process in the Monitor's own context instead of a subagent and limits each `Translating` step to one paragraph. For internal comparison use only, not the recommended default. Use when a controlled single-writer comparison is explicitly requested."
---

Role: the Monitor. It selects the next writing process from the state, runs it in its own context, and records its decisions; outside a process it writes nothing but `.writing/history.md`.

State: the task in `.writing/task.md`, the draft in `.writing/draft.md` (the task may provide one), the goals in `.writing/goals.md`, and the history in `.writing/history.md`.

Kinds of work: Planning changes the goals; Translating adds one paragraph of prose for the goals; Reviewing corrects existing prose and reports what is needed next. A role reports work of another kind instead of doing it.

Procedure:

1. Read the four state files; a missing file counts as empty.
2. Choose the process from the kind of work the state calls for; a section without a goal needs Planning first. The Monitor reads the draft to choose; checking it against the task is Reviewing's work.
3. Append one line to `.writing/history.md`: the process, its scope, and the reason.
4. Run the process, with its scope, in your own context by following its role section below; do not spawn an agent. The Reviewing scope is this sentence and nothing more: check `.writing/draft.md` against `.writing/task.md` and the active goals, correct existing prose, and report what is needed next. The Planning scope is this sentence and nothing more: read `.writing/task.md`, `.writing/draft.md`, and `.writing/goals.md`, and create or develop the goals so that every requirement in the task has a goal.
5. When the Reviewer recommends replacing a goal, decide whether to accept it, record the decision in `.writing/history.md`, and run an accepted replacement as `Planning`; the `Monitor` edits `.writing/goals.md` only while running `Planning`.

Stop when no further process is needed; the draft in `.writing/draft.md` is the final document.

## Planning

Role: the Planner. Planning changes the goals, not the prose.
Read `.writing/task.md`, `.writing/draft.md`, and `.writing/goals.md`.
Organize the relevant material for the intended audience, and create or develop the writing goals as a hierarchy in `.writing/goals.md`, within the delegated scope. When a goal conflicts with `.writing/task.md`, the task governs: replace the goal.
Report what changed and any work of another kind that is needed.

## Translating

Role: the Translator. Translating adds prose for the goals; a section with no goal is reported, not written.
Read `.writing/task.md`, `.writing/draft.md`, and the active goals in `.writing/goals.md`.
Write one paragraph in `.writing/draft.md` within the delegated draft scope; each further paragraph is a new Translating step.
Report what was written and any structural problem that drafting exposes.

## Reviewing

Role: the Reviewer. Reviewing corrects existing prose; a missing goal or a missing section is reported, not written. Do not add sentences, classifications, or lists to supply missing content, even when related prose exists elsewhere in the draft.
First, for each requirement in `.writing/task.md`, name the goal in `.writing/goals.md` that covers it; a goal covers a requirement only if it names that requirement's section, and a requirement with no such goal is reported for planning.
Check `.writing/draft.md` against `.writing/task.md` and the active goals in `.writing/goals.md`.
Revise the draft within the delegated scope.
Report whether further planning, drafting, or review is needed: planning when a task requirement has no goal in `.writing/goals.md`, drafting when a goal has no prose yet, review when prose remains to check, and none when the draft meets the task and goals; you may also recommend replacing a goal.
