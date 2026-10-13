---
name: reviewing
description: Internal role skill for the agentic-cognitive-writing `Monitor`. Invoked by delegation from the `Monitor`; do not select this skill directly.
---

> [!NOTE]
> After reading this `SKILL.md`, say: `I read reviewing.`

# `Reviewing`

Evaluate the draft against the rhetorical problem, revise only locally within the scope that the `Monitor` delegates, and report every remaining required change.

## When this skill runs

You perform the `Reviewing` process for the `Monitor`, as the brief describes. A role agent begins its report with the acknowledgment line. A `Monitor` that applies this skill in its own context says the line in an assistant message instead. The line never goes into `.writing/draft.md` or the final response.

## Read the state first

Read these before reviewing:

- the brief
- `.writing/assignment.md`, which holds the assignment verbatim and the `Monitor`'s restatement
- `.writing/goals.md`, when the brief lists active goals
- `.writing/draft.md`

## Sub-processes

Your work contains two embedded sub-processes, which you perform yourself.

1. Evaluate: test the draft against:

   - every requirement of the assignment, including required sections, output language, length, and format
   - the audience
   - the active goals, when the brief lists them
   - claim support
   - organization
   - coherence
   - tone
   - local wording

   Distinguish goal and evidence failures from organization and sentence failures.

2. Revise: make local revisions, such as wording, sentence, or paragraph fixes, only inside the brief's scope, in the output language. Do not add or remove sections, reorganize the draft, or rewrite a passage outside the scope. Report each such change under Findings instead.

## Boundaries

- Write only `.writing/draft.md`, and only inside the brief's scope.
- Do not write `.writing/goals.md`, `.writing/assignment.md`, or the trace.
- Do not invent citations or claims.
- If the draft reveals a more useful purpose for a goal, recommend its replacement with evidence; do not hide the change as copy-editing.

## Report format

Your final message is the report. Use exactly these fields:

```text
I read reviewing.
Verdict: <changes required, or no required change>
Revisions made: <the local revisions made, or none>
Findings:
- planning: <location>: <a structural or goal-level problem and the required change>
- translating: <location>: <a problem localized to a passage and the required change>
Goal verdicts:
- G1 — keep: <one sentence of evidence from the draft>
- G2 — develop: <one sentence of evidence and the refinement needed>
- G3 — regenerate: <one sentence of evidence>. Replacement: <the proposed new purpose>
Next process: <planning, translating, or stop>
```

Under Findings, start each line with the process that should handle it: `planning` for a missing required section, a wrong organization, or a goal that is unmet or wrong, and `translating` for a problem localized to a passage. Write `- none` when there is none.

Give one goal verdict for each active goal in the brief, identified by ID, using exactly one of the lowercase words `keep`, `develop`, or `regenerate`. Omit the Goal verdicts field when the brief lists no goals.

Write `Verdict: no required change` only when Findings is `- none`, every goal verdict is `keep`, and the draft meets every requirement of the assignment. The recommended next process is advice; the `Monitor` selects the next process.
