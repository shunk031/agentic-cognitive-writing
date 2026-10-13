# Goal network format

The goal network in `.writing/goals.md` is the working representation of the writer's purpose. It connects the assignment's aims to concrete content goals, and the `Planning` process alone writes it. The goal history lives in the trace, not in this file.

## Notation

```markdown
# Goals

- [G0] Persuade new engineering managers to adopt the handoff checklist (parent: none, status: active)
  - [G1] Show why missed handoffs matter in their first week (parent: G0, status: active)
  - [G2] Present the checklist with one worked example (parent: G0, status: active)
  - [G3] Explain the policy change (parent: G0, status: replaced by G4)
  - [G4] Explain what changes in each manager's on-call week (parent: G0, status: active)
```

Each line holds one goal: a stable ID in brackets, the goal statement, its parent, and its status. A child is indented under its parent.

## Changes

| Change  | Who decides                                  | In the file                                                                       | In the trace       |
| ------- | -------------------------------------------- | --------------------------------------------------------------------------------- | ------------------ |
| Create  | `Planning`                                   | a new line with a new ID                                                          | `goal_created`     |
| Develop | `Planning`                                   | a more specific statement under the same ID                                       | `goal_developed`   |
| Replace | the `Monitor` accepts a `Reviewing` proposal | the old line marked `replaced by <new ID>` and the new goal under the same parent | `goal_regenerated` |
| Resolve | `Planning`                                   | status `resolved`                                                                 | none               |

Status is `active`, `resolved`, or `replaced by <ID>`.
