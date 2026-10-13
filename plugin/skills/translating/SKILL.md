---
name: translating
description: Internal role skill for the agentic-cognitive-writing `Monitor`. Invoked by delegation from the `Monitor`; do not select this skill directly.
---

> [!NOTE]
> After reading this `SKILL.md`, say: `I read translating.`

# `Translating`

Turn selected meanings and plans into prose within the draft scope that the `Monitor` delegates.

## When this skill runs

You perform the `Translating` process for the `Monitor`, as the brief describes. A role agent begins its report with the acknowledgment line. A `Monitor` that applies this skill in its own context says the line once, in an assistant message of its own immediately after reading this skill, and never repeats it in a written report. The line never goes into `.writing/draft.md` or the final response.

## Read the state first

Read these before editing:

- the brief
- `.writing/assignment.md`, which holds the assignment verbatim and the `Monitor`'s restatement
- `.writing/goals.md`, when the brief lists active goals
- `.writing/draft.md`

Translate the selected ideas into prose while treating the current wording as provisional. Keep the scope's goals visible while drafting. Preserve a useful existing sentence when it serves those goals; do not let fluent wording override the rhetorical purpose.

## Drafting rules

- Write in the output language that the brief names.
- Write only the brief's scope in `.writing/draft.md` and leave the rest of the file unchanged.
- Meet the length target that the goals or the plan set for each part of the scope, and the format constraints that apply to it.
- Preserve useful supplied text.
- Do not invent sources, quotations, statistics, or facts. Mark a gap in the report rather than filling it.
- Do not write `.writing/goals.md`, `.writing/assignment.md`, or the trace.

## Report format

A role agent's final message is the report. A `Monitor` that applies this skill in its own context writes the report where its own skill says instead, without the acknowledgment line. Use exactly these fields:

```text
I read translating.
Scope written: <goal IDs or sections written>
Changes: <what prose was added or changed>
Findings:
- <a structural, goal-level, or passage-level problem that drafting exposed, with its location>
Uncertainty: <claims that need evidence>
Next process: <reviewing, planning, or translating>
```

Write `- none` under Findings when there is none. The recommended next process is advice; the `Monitor` selects the next process.
