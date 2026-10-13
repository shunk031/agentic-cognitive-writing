---
name: reviewing
description: Internal role skill for the agentic-cognitive-writing `Monitor`. Invoked by delegation from the `Monitor`; do not select this skill directly.
---

> [!NOTE]
> After reading this `SKILL.md`, say: `I read reviewing.`

# `Reviewing`

Evaluate the draft against the rhetorical problem, revise only locally within the scope that the `Monitor` delegates, and report every remaining required change.

## When this skill runs

You perform the `Reviewing` process for the `Monitor`, as the brief describes. Say the acknowledgment line immediately after reading this skill, in the same response as your next tool call, and begin your report with it. The line never goes into `.writing/draft.md` or the final response.

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

2. Revise: make local revisions only inside the brief's scope, in the output language. A local revision fixes wording, mechanics, or a single sentence. Adding content, cutting content, or rewriting a passage is not a local revision; report it as a `translating` open finding. Adding or removing a section or reorganizing the draft is a `planning` open finding.

## Boundaries

- Write only `.writing/draft.md`, and only inside the brief's scope.
- Do not write `.writing/goals.md`, `.writing/assignment.md`, or the trace.
- Do not invent citations or claims.
- If the draft reveals a more useful purpose for a goal, recommend its replacement with evidence; do not hide the change as copy-editing.

## Report format

Your final message is the report. Use exactly these fields:

```text
I read reviewing.
Revisions made:
- <a local revision already made, with its location>
Open findings:
- planning: <location>: <a structural or goal-level problem and the required change>
- translating: <location>: <a problem localized to a passage and the required change>
Goal verdicts:
- G1 — keep: <one sentence of evidence from the draft>
- G1.1 — develop: <one sentence of evidence and the refinement needed>
- G1.2 — regenerate: <one sentence of evidence>. Replacement: <the proposed new purpose>
Verdict: <no required change when Open findings is - none; otherwise changes required>
Next process: <planning, translating, or stop>
```

Revisions made lists only changes already applied; they are not findings. Open findings lists every required change that remains. Start each open finding with the process that should handle it: `planning` for a missing required section, a wrong organization, or a goal that is unmet or wrong, and `translating` for content to add, cut, or rewrite in a passage. List each `develop` goal verdict also as a `planning` open finding. Report a `regenerate` verdict only under Goal verdicts, never as an open finding, because the `Monitor` decides whether to accept it. Write `- none` for an empty list.

Give one goal verdict for each active goal in the brief, identified by ID, using exactly one of the lowercase words `keep`, `develop`, or `regenerate`. Omit the Goal verdicts field when the brief lists no goals. Do not propose again, as a goal verdict or an open finding, a replacement that the brief lists under Rejected proposals, unless you give new evidence that its stated reason does not answer.

Write the Verdict after the open findings and compute it from them alone: no open findings means `no required change`, and any open finding means `changes required`. The recommended next process is advice; the `Monitor` selects the next process.
