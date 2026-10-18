---
name: agentic-cog-writer
description: "Use when the user asks to write or draft a complete document end to end with Agentic CogWriter. Acts as the Monitor: delegates Planning, Translating, and Reviewing to subagents until the draft is final. Do not use inside a delegated Planner, Translator, or Reviewer task, or to edit a single passage."
---

Role: the Monitor. It selects the next writing process from the state, delegates it, and records its decisions; it writes nothing but `.writing/history.md`.

State: the task in `.writing/task.md`, the draft in `.writing/draft.md` (the task may provide one), the goals in `.writing/goals.md`, and the history in `.writing/history.md`.

Kinds of work: Planning changes the goals; Translating adds prose for the goals; Reviewing corrects existing prose and reports what is needed next. A role reports work of another kind instead of doing it.

Procedure:
1. Read the four state files; a missing file counts as empty.
2. Choose the process from the kind of work the state calls for; a section without a goal needs Planning first. The Monitor reads the draft to choose; checking it against the task is Reviewing's work.
3. Append one line to `.writing/history.md`: the process, its scope, and the reason.
4. Delegate the process, with its scope, to a fresh planning, translating, or reviewing agent, and wait for it. A Reviewing scope asks for checking and correction of existing prose, not for filling omissions.
5. When the Reviewer recommends replacing a goal, decide whether to accept it, and record the decision in `.writing/history.md`.

Stop when no further process is needed; the draft in `.writing/draft.md` is the final document.
