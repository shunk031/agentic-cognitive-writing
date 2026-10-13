# Trace JSON Lines schema

The `Monitor` alone writes `.writing/trace/process.jsonl`, one JSON object per line, through the skill's `scripts/writing_state.py log` command, which builds each line with a JSON encoder and validates it. The log is append-only, so a reader can reconstruct the process path, the goal changes, and the evidence for each decision without the chat transcript.

## Fields

Every event has these fields:

| Field               | Type             | Meaning                                                                                                                                                        |
| ------------------- | ---------------- | -------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| `timestamp`         | string           | ISO 8601 time with a UTC offset, written by the logging script at append time                                                                                  |
| `event_type`        | string           | `process_switch`, `goal_created`, `goal_developed`, or `goal_regenerated`                                                                                      |
| `responsible_agent` | string           | `planner` for `goal_created` and `goal_developed` from a `Planning` report; `monitor` for every other event, including a `goal_created` event logged at Finish |
| `process`           | string           | For a process switch, the process entered, or the process left when the run stops; for a goal event, `planning`                                                |
| `decision`          | string           | The decision and its reason in plain language                                                                                                                  |
| `evidence`          | array of strings | File paths, draft excerpts, goal IDs, or report fields that support the decision                                                                               |
| `open_uncertainty`  | array of strings | Questions or unsupported claims left open; empty when none remains                                                                                             |

A process switch also has these fields:

| Field          | Type           | Meaning                                                              |
| -------------- | -------------- | -------------------------------------------------------------------- |
| `from_process` | string or null | The previous switch's `to_process`; `null` for the first switch      |
| `to_process`   | string or null | `planning`, `translating`, or `reviewing`; `null` when the run stops |

A goal event also has these fields:

| Field            | Type           | Meaning                                                                                               |
| ---------------- | -------------- | ----------------------------------------------------------------------------------------------------- |
| `goal_id`        | string         | The created or developed goal, or the replacement goal for `goal_regenerated`, such as `G1` or `G1.2` |
| `parent_goal_id` | string or null | The goal's parent; for `goal_regenerated`, the replaced goal's parent; `null` for a top-level goal    |

## Reading the trace

- The process path is the sequence of `to_process` values of the process switches, in line order.
- The decision of the first process switch after each `Reviewing` report begins with the post-`Reviewing` ledger, which the logging script writes: `regeneration proposals: none.`, or one `accepted` or `rejected` entry per proposed replacement.
- A goal event follows the `Planning` report that made the change, except a `goal_created` event that the `Monitor` logs at Finish for a goal that had none.

## Example

```json
{"timestamp":"2026-01-15T09:00:00+09:00","event_type":"process_switch","responsible_agent":"monitor","process":"planning","from_process":null,"to_process":"planning","decision":"Create the goals from the assignment; .writing/goals.md has none.","evidence":[".writing/assignment.md"],"open_uncertainty":[]}
{"timestamp":"2026-01-15T09:04:00+09:00","event_type":"goal_created","responsible_agent":"planner","process":"planning","decision":"Planning created G1.1 under G1.","evidence":["Planning report: created G1.1 (parent G1)"],"open_uncertainty":[],"goal_id":"G1.1","parent_goal_id":"G1"}
{"timestamp":"2026-01-15T09:04:00+09:00","event_type":"process_switch","responsible_agent":"monitor","process":"translating","from_process":"planning","to_process":"translating","decision":"Draft G1.1, which has no draft text yet.","evidence":[".writing/goals.md: G1.1 is active"],"open_uncertainty":[]}
{"timestamp":"2026-01-15T09:12:00+09:00","event_type":"process_switch","responsible_agent":"monitor","process":"reviewing","from_process":"reviewing","to_process":null,"decision":"regeneration proposals: none. Reviewing listed no open findings.","evidence":["Reviewing report: Open findings - none"],"open_uncertainty":[]}
```
