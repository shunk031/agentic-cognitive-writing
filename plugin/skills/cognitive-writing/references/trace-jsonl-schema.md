# Trace JSON Lines schema

The Monitor writes one JSON object per line to `.writing/trace/process.jsonl`. A line must be valid JSON on its own. The log is append-only so a later reader can reconstruct process switches, goal changes, evidence, and uncertainty without relying on a chat transcript.

## Fields

Every event has these fields:

| Field | Type | Meaning |
| --- | --- | --- |
| `timestamp` | string | Timestamp in the International Organization for Standardization 8601 standard with a timezone offset, recorded when the event is written. |
| `event_type` | string | One of `process_switch`, `goal_created`, `goal_developed`, or `goal_regenerated`. |
| `responsible_agent` | string | Actor responsible for the decision, such as `monitor`, `planner`, `translator`, `reviewer`, or `user`. |
| `process` | string | Process that made or owns the decision, such as `planning`, `generate`, `organize`, `goal-setting`, `translating`, `reviewing`, `evaluate`, or `revise`. |
| `decision` | string | Plain-language decision or action. State what changed or why the process moved. |
| `evidence` | array | Facts, file paths, draft excerpts, goal identifiers, or observations supporting the decision. Keep entries concrete. |
| `open_uncertainty` | array | Questions, unsupported claims, unresolved conflicts, or missing information left open after the decision. Use an empty array when none remains. |

Use these conditional fields when they apply:

| Field | Type | Meaning |
| --- | --- | --- |
| `from_process` | string or null | Process being left for a `process_switch`. Use `null` when starting the loop. |
| `to_process` | string or null | Process being entered for a `process_switch`. |
| `goal_id` | string | Goal affected by the event. |
| `parent_goal_id` | string or null | Immediate parent in the goal network. |
| `artifacts` | array | Project-relative files read or changed because of the event. |

`process_switch` entries must include `from_process` and `to_process`. Goal events must include `goal_id` and `parent_goal_id`. Every process switch and every goal creation, development, or regeneration must include `responsible_agent`, `decision`, `evidence`, and `open_uncertainty`.

## Example

```json
{"timestamp":"2026-01-15T09:00:00+09:00","event_type":"process_switch","responsible_agent":"monitor","process":"planning","from_process":null,"to_process":"planning","decision":"Explore the audience's likely objection before drafting the opening.","evidence":[".writing/assignment.md: audience is first-year students",".writing/goals.md: G0 has no audience-specific sub-goal"],"open_uncertainty":["Which objection matters most to this audience?"],"goal_id":"G0","parent_goal_id":null,"artifacts":[".writing/assignment.md",".writing/goals.md"]}
{"timestamp":"2026-01-15T09:04:00+09:00","event_type":"goal_developed","responsible_agent":"planner","process":"goal-setting","decision":"Add a sub-goal to answer the audience's objection with one concrete example.","evidence":["Planner grouped three notes in .writing/memory/audience.md"],"open_uncertainty":["The example still needs a source."],"goal_id":"G1","parent_goal_id":"G0","artifacts":[".writing/goals.md",".writing/memory/audience.md"]}
```
