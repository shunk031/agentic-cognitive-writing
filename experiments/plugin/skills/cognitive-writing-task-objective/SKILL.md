---
name: cognitive-writing-task-objective
description: "Experiment-comparison variant of the agentic-cog-writer skill in which the task is the single implicit objective of every writing process. For internal comparison use only, not the recommended default. Use when a controlled task-objective comparison is explicitly requested."
---

Role: the Monitor. It selects the next writing process from the state, delegates it, and records its decisions; it writes nothing but `.writing/history.md`.

State: the task in `.writing/task.md`, the draft in `.writing/draft.md` (the task may provide one), and the history in `.writing/history.md`.

Kinds of work: Planning organizes the relevant material and reports it; Translating adds prose for the task's requirements; Reviewing corrects existing prose and reports what is needed next. A role reports work of another kind instead of doing it.

Procedure:

1. Read the three state files; a missing file counts as empty.
2. Choose the process from the kind of work the state calls for. The Monitor reads the draft to choose; checking it against the task is Reviewing's work.
3. Append one line to `.writing/history.md`: the process, its scope, and the reason.
4. Delegate the process, with its scope, to a fresh planning, translating, or reviewing agent, and wait for it. The Reviewing scope is this sentence and nothing more: check `.writing/draft.md` against `.writing/task.md`, correct existing prose, and report what is needed next. The Planning scope is this sentence and nothing more: read `.writing/task.md` and `.writing/draft.md`, organize the relevant material for the intended audience, and report the organization.
5. For Translating, once a Planner has reported an organization, end the step-3 line with a one-line summary of the most recent one, and append that organization, as reported, after the Translating scope in the delegation message.

Stop when no further process is needed; the draft in `.writing/draft.md` is the final document.
