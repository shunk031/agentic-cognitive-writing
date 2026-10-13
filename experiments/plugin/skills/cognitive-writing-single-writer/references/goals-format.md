# Goal network format

The goal network in `.writing/goals.md` is the working representation of the writer's purpose. It connects the assignment's aims to concrete content goals, and the `Planning` process alone writes it. The goal history lives in the trace, not in this file.

## Notation

```markdown
# Goals

- [G1] Persuade new engineering managers to adopt the handoff checklist (parent: none, status: active, length: 900 words)
  - [G1.1] Show why missed handoffs matter in their first week (parent: G1, status: active, length: 300 words)
  - [G1.2] Explain the policy change (parent: G1, status: replaced by G1.4)
  - [G1.3] Present the checklist with one worked example (parent: G1, status: active, length: 400 words)
  - [G1.4] Explain what changes in each manager's on-call week (parent: G1, status: active, length: 200 words)
```

Each line holds one goal: a stable ID in brackets, the goal statement, its parent, its status, and an optional length target. A child is indented under its parent.

## Goal IDs

A top-level goal's ID is `G` and a number, such as `G1`. A child's ID is its parent's ID, a dot, and the next unused number, such as `G1.3` or `G1.3.1`. IDs are never reused. Every ID matches the regular expression `G\d+(\.\d+)*`.

## Changes

| Change  | Who decides                                  | In the file                                                                       | In the trace       |
| ------- | -------------------------------------------- | --------------------------------------------------------------------------------- | ------------------ |
| Create  | `Planning`                                   | a new line with a new ID                                                          | `goal_created`     |
| Develop | `Planning`                                   | a more specific statement under the same ID                                       | `goal_developed`   |
| Replace | the `Monitor` accepts a `Reviewing` proposal | the old line marked `replaced by <new ID>` and the new goal under the same parent | `goal_regenerated` |
| Resolve | `Planning`                                   | status `resolved`                                                                 | none               |

Status is `active`, `resolved`, or `replaced by <ID>`.
