# Goal network format

The goal network in `.writing/goals.md` is the working representation of the writer's purpose. It connects abstract rhetorical aims to concrete content and process goals. It is hierarchical, can be expanded while composing, and can be regenerated when writing changes the author's understanding.

## Network notation

Use stable IDs, one goal per line, and indentation for parent-child relationships:

```markdown
# Goal network

## Active network

- [G0] Explain the policy change to new team members (kind: content, status: active, parent: none)
  - [G1] Establish why the change matters to their first week (kind: content, status: active, parent: G0)
    - [G2] Open with a concrete first-day scenario (kind: process, status: resolved, parent: G1)
  - [G3] Give one example of the new workflow (kind: content, status: pending, parent: G0)

## Goal history

| Timestamp | Event | Goal | Parent | Rationale | Evidence |
| --- | --- | --- | --- | --- | --- |
| 2026-01-15T09:04:00+09:00 | created | G1 | G0 | Make the audience impact explicit. | assignment.md |
| 2026-01-15T09:18:00+09:00 | regenerated | G0 | none | The opening revealed that the real purpose is adoption, not explanation. | draft.md, reviewer note |
```

`kind` may be `content`, `process`, or `criterion`. Use `status` values `pending`, `active`, `blocked`, `resolved`, or `superseded`. Keep a regenerated goal's original ID in history and give the replacement a new ID when its meaning materially changes. A small wording refinement can stay under the same ID, but record it as `developed` in the history.

## Update rules

- Add a history row whenever a goal is created, developed, or regenerated.
- Keep the immediate parent ID on every goal so the Monitor can pop back after a sub-goal resolves.
- Put evaluation criteria such as audience fit, claim support, or tone in `criterion` goals when they guide a writing choice.
- Mark a goal `superseded` rather than deleting it when a new goal replaces it.
- If a goal depends on an unresolved fact or user decision, mark it `blocked` and name the uncertainty in the trace.
