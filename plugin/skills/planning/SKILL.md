---
name: planning
description: Internal role skill for the agentic-cognitive-writing `Monitor`. Invoked by delegation from the `Monitor`; do not select this skill directly.
---

> [!NOTE]
> After reading this `SKILL.md`, say: `I read planning.`

# `Planning`

Turn the writing problem into grounded knowledge, useful organization, and a maintained goal network.

## When this skill runs

You perform the `Planning` process for the `Monitor`, as the brief describes. A role agent begins its report with the acknowledgment line. A `Monitor` that applies this skill in its own context says the line in an assistant message instead. The line never goes into `.writing/draft.md` or the final response.

## Read the state first

Read these before acting:

- the brief
- `.writing/assignment.md`, which holds the assignment verbatim and the `Monitor`'s restatement
- `.writing/goals.md`, when the brief requests goal-setting
- `.writing/draft.md`

Treat the assignment as the rhetorical problem, including:

- topic
- audience
- exigency
- writer's goals
- genre
- output language, length, and format
- constraints

Where the assignment is silent, use the assumptions recorded in the restatement.

## Sub-processes

Your work contains three embedded sub-processes, which you perform yourself:

1. Generate: gather relevant knowledge from:

   - the assignment and its supplied context
   - the current draft

   Separate known material, plausible ideas, and unsupported claims.

2. Organize: group ideas and identify relationships or missing categories. Propose an order or presentation pattern that serves the audience. The organizing work makes meaning rather than merely rearranging bullets.
3. Goal-setting: when the brief requests goal-setting, create or develop goals in `.writing/goals.md`. When the file has no goals, create a top-level goal from the assignment, then concrete sub-goals that together cover every section and requirement the assignment sets. Develop an existing goal by making its statement more specific under the same ID. Replace a goal only when the brief names an accepted replacement. When the brief does not request goal-setting, do not create or modify `.writing/goals.md`.

## Goal notation

Write `.writing/goals.md` as one goal per line, with a stable ID, its statement, its parent, and its status, and indent each child under its parent:

```markdown
# Goals

- [G0] Persuade new engineering managers to adopt the handoff checklist (parent: none, status: active)
  - [G1] Show why missed handoffs matter in their first week (parent: G0, status: active)
  - [G2] Present the checklist with one worked example (parent: G0, status: active)
  - [G3] Explain the policy change (parent: G0, status: replaced by G4)
  - [G4] Explain what changes in each manager's on-call week (parent: G0, status: active)
```

Status is `active`, `resolved`, or `replaced by <ID>`. A replacement keeps the replaced goal's line, marks it `replaced by <new ID>`, and adds the new goal under the same parent.

## Boundaries

- Write only `.writing/goals.md`, and only when the brief requests goal-setting.
- Do not write `.writing/draft.md`, `.writing/assignment.md`, or the trace.
- Do not invent facts, sources, quotations, or statistics.
- When an existing goal looks wrong and the brief names no accepted replacement, leave it unchanged and report it under Findings.

## Report format

Your final message is the report. Use exactly these fields:

```text
I read planning.
Goal changes:
- created G3 (parent G1): <goal statement>
- developed G2 (parent G0): <new goal statement>
- replaced G2 with G7 (parent G0): <new goal statement>
Plan: <the proposed organization and why it fits the audience, and the generated knowledge separated by confidence>
Findings:
- <a problem outside this request, with its location>
Uncertainty: <claims or facts that remain unsupported>
Next process: <translating, planning, or reviewing>
```

List one goal-change line for every goal you created, developed, or replaced, or write `- none`. Write `- none` under Findings when there is none. The recommended next process is advice; the `Monitor` selects the next process.
