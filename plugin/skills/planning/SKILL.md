---
name: planning
description: Internal role skill for the agentic-cognitive-writing `Monitor`. Invoked by delegation from the `Monitor`; do not select this skill directly.
---

> [!NOTE]
> After reading this `SKILL.md`, say: `I read planning.`

# `Planning`

Turn the writing problem into grounded knowledge, useful organization, and a maintained goal network.

## When this skill runs

You perform the `Planning` process for the `Monitor`, as the brief describes. A role agent begins its report with the acknowledgment line. A `Monitor` that applies this skill in its own context says the line once, in an assistant message of its own immediately after reading this skill, and never repeats it in a written report. The line never goes into `.writing/draft.md` or the final response.

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
3. Goal-setting: when the brief requests goal-setting, create or develop goals in `.writing/goals.md`. When the file has no goals, create a top-level goal from the assignment, then concrete sub-goals that together cover every section and requirement the assignment sets. When the assignment sets a length, give each section goal a length target so that the targets add up to the requested length. Develop an existing goal by making its statement more specific under the same ID. Replace a goal only when the brief names an accepted replacement. When the brief does not request goal-setting, do not create or modify `.writing/goals.md`.

## Goal notation

Write `.writing/goals.md` as one goal per line, with a stable ID, its statement, its parent, its status, and an optional length target, and indent each child under its parent:

```markdown
# Goals

- [G1] Persuade new engineering managers to adopt the handoff checklist (parent: none, status: active, length: 900 words)
  - [G1.1] Show why missed handoffs matter in their first week (parent: G1, status: active, length: 300 words)
  - [G1.2] Explain the policy change (parent: G1, status: replaced by G1.4)
  - [G1.3] Present the checklist with one worked example (parent: G1, status: active, length: 400 words)
  - [G1.4] Explain what changes in each manager's on-call week (parent: G1, status: active, length: 200 words)
```

A top-level goal's ID is `G` and a number, such as `G1`. A child's ID is its parent's ID, a dot, and the next unused number, such as `G1.3` or `G1.3.1`. Never reuse an ID. Status is `active`, `resolved`, or `replaced by <ID>`. A replacement keeps the replaced goal's line, marks it `replaced by <new ID>`, and adds the new goal under the same parent.

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
- created G1.3 (parent G1): <goal statement>
- developed G1.1 (parent G1): <new goal statement>
- replaced G1.2 with G1.4 (parent G1): <new goal statement>
Plan: <the proposed organization and why it fits the audience, the length target of each section, and the generated knowledge separated by confidence>
Findings:
- <a problem outside this request, with its location>
Uncertainty: <claims or facts that remain unsupported>
Next process: <translating, planning, or reviewing>
```

List one goal-change line for every goal you created, developed, or replaced, or write `- none`. Write `parent none` for a top-level goal. Write `- none` under Findings when there is none. The recommended next process is advice; the `Monitor` selects the next process.
