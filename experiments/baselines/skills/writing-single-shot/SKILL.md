---
name: writing-single-shot
description: "Experiment condition A1. Generate the complete document in one pass from the assignment and supplied context, with no planning or review stage. Use only for the controlled single-shot comparison."
---

# Single-shot writing

Run condition A1 as one generation pass. The generator writes the complete document from `.writing/assignment.md` and the supplied context. The generator does not create a plan, ask a planning subagent, run a reviewer, or perform a second generation pass.

## Equal-information and no-retrieval policy

The runner gives this condition the same assignment, supplied context, context-window policy, timeout, model settings, output budget, and attempt budget as every comparison condition. The generator may read the assignment and supplied context, but it must not browse, search, call a retrieval tool, use an external source, or infer evidence that the supplied context does not provide. If the context does not establish a claim, preserve the uncertainty or omit the claim.

The user owns rhetorical intent, factual authority, final wording, and publication. The generator owns the single completion pass. The runner owns trace recording and must not infer hidden planning or review from the output.

## Procedure

1. Read `.writing/assignment.md` and the supplied context. Do not create or modify `.writing/goals.md`, planning notes, review notes, or memory files for this condition.
2. Generate the complete final document in one pass. Keep the requested audience, genre, structure, length, and other constraints visible in the prompt.
3. Return the complete final document in the final response. Do not write `.writing/draft.md` or another draft file.
4. Append exactly one event to `.writing/trace/process.jsonl`. The schema has no separate generation event type, so represent the generation as one `process_switch` object with `process: "generate"`, `from_process: null`, and `to_process: "generate"`.

The trace contract is fixed at exactly one `process_switch` event. Its only allowed `process` value is `generate`. The runner appends the event when the single pass starts or completes. The line must contain `timestamp`, `event_type`, `responsible_agent`, `process`, `decision`, `evidence`, `open_uncertainty`, `from_process`, and `to_process`, and may contain `artifacts`. In the JSON object, `timestamp`, `event_type`, `responsible_agent`, `process`, and `decision` are strings; `evidence` and `open_uncertainty` are arrays of strings; `from_process` and `to_process` are strings or `null`; and `artifacts`, when present, is an array of project-relative path strings. Use `responsible_agent: "runner"`, describe the assignment and supplied context in `evidence`, and list unresolved claims in `open_uncertainty`. Do not append goal events or invent internal reasoning.

Example shape:

```json
{"timestamp":"2026-01-15T09:00:00+09:00","event_type":"process_switch","responsible_agent":"runner","process":"generate","from_process":null,"to_process":"generate","decision":"Generate the complete document in one pass from the assignment and supplied context.","evidence":[".writing/assignment.md","supplied context"],"open_uncertainty":[],"artifacts":[]}
```

Do not add another trace line for a retry, formatting step, or hidden decision. A failed run is accounted for by the runner; the skill must not turn failure handling into an unplanned stage.
