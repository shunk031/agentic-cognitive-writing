# Trace JSON Lines schema

The `Monitor` alone writes `.writing/trace/process.jsonl`, one JSON object per line, through the skill's `scripts/writing_state.py log --no-goals` command, which builds each line with a JSON encoder, validates it, and refuses goal events. The log is append-only, so a reader can reconstruct the process path and the evidence for each decision without the chat transcript.

## Fields

Every event is a process switch with these fields:

| Field | Type | Meaning |
| --- | --- | --- |
| `timestamp` | string | ISO 8601 time with a UTC offset, written by the logging script at append time |
| `event_type` | string | `process_switch` |
| `responsible_agent` | string | `monitor` |
| `process` | string | The process entered, or the process left when the run stops |
| `decision` | string | The decision and its reason in plain language |
| `evidence` | array of strings | File paths, draft excerpts, or report fields that support the decision |
| `open_uncertainty` | array of strings | Questions or unsupported claims left open; empty when none remains |
| `from_process` | string or null | The previous switch's `to_process`; `null` for the first switch |
| `to_process` | string or null | `planning`, `translating`, or `reviewing`; `null` when the run stops |

## Reading the trace

The process path is the sequence of `to_process` values of the process switches, in line order.

## Example

```json
{"timestamp":"2026-01-15T09:00:00+09:00","event_type":"process_switch","responsible_agent":"monitor","process":"planning","from_process":null,"to_process":"planning","decision":"Plan the document from the assignment.","evidence":[".writing/assignment.md"],"open_uncertainty":[]}
{"timestamp":"2026-01-15T09:04:00+09:00","event_type":"process_switch","responsible_agent":"monitor","process":"translating","from_process":"planning","to_process":"translating","decision":"Draft the opening section, which has no draft text yet.","evidence":[".writing/draft.md has no opening section"],"open_uncertainty":[]}
```
