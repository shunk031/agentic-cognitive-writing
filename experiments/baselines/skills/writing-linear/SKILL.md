---
name: writing-linear
description: "Experiment condition A2. Run one fixed Pre-Write, Write, and Re-Write pass, handing each output to the next under a common output budget. Use only for the controlled linear comparison."
---

# Linear writing

Run condition A2 in the fixed order `Pre-Write -> Write -> Re-Write`. Each stage runs once. The output from one stage is the only process artifact handed to the next stage, together with the unchanged assignment and supplied context. The Re-Write output is the final document.

## Equal-information and no-retrieval policy

The runner gives this condition the same assignment, supplied context, context-window policy, timeout, model settings, total output budget, and attempt budget as every comparison condition. The runner allocates the same aggregate output-token budget to A2 as to A1; stage allocations are fixed before a run and sum to that budget. A stage may not obtain extra attempts or tokens because an earlier stage underperformed.

The generator may use only `.writing/assignment.md`, the supplied context, and the prior stage output. The generator must not browse, search, call a retrieval tool, or use an external source. Retrieval, evidence gathering, and citation generation are disabled. When the supplied context does not support a claim, preserve the uncertainty or omit the claim.

The user owns rhetorical intent, factual authority, final wording, and publication. The runner owns stage scheduling and trace recording. The three stage generators own their respective outputs. The runner must not infer hidden reasoning from stage text.

## Procedure

1. Read `.writing/assignment.md` and the supplied context. Leave `.writing/goals.md` untouched and do not create goal events.
2. Run one `Pre-Write` pass that converts the assignment into a compact document plan, requirements checklist, and section intent. Store its output at `.writing/baselines/linear/pre-write.md` or the runner-designated equivalent.
3. Append the first schema-valid `process_switch` event for `null -> pre-write`, naming the runner as the responsible actor and citing the assignment and pre-write handoff.
4. Run one `Write` pass using the assignment, supplied context, and complete Pre-Write output. Store the draft at `.writing/baselines/linear/write.md`.
5. Append the second event for `pre-write -> write`, citing both stage artifacts.
6. Run one `Re-Write` pass using the assignment, supplied context, and complete Write output. Store the final document at `.writing/draft.md`.
7. Append the third event for `write -> re-write`, citing the Write output and final draft.

Before sending the final response, write the final document to `.writing/draft.md`. The run is `INVALID` unless `.writing/draft.md` exists before the final response and the final response contains the complete final text. The final response cannot substitute for the required draft.

The trace contract is fixed at exactly three `process_switch` events. Every event's `process` must be one of `pre-write`, `write`, or `re-write`, in this exact order. The transitions are `null -> pre-write`, `pre-write -> write`, and `write -> re-write`. Append every event to `.writing/trace/process.jsonl`. Each event is a `process_switch` object with `timestamp`, `event_type`, `responsible_agent`, `process`, `decision`, `evidence`, `open_uncertainty`, `from_process`, and `to_process`, plus `artifacts` for stage files. In the JSON object, `timestamp`, `event_type`, `responsible_agent`, `process`, and `decision` are strings; `evidence` and `open_uncertainty` are arrays of strings; `from_process` and `to_process` are strings or `null`; and `artifacts` is an array of project-relative path strings. Use `responsible_agent: "runner"`, preserve the exact stage names in `process`, `from_process`, and `to_process`, and add stage artifacts to `artifacts`. Do not append goal, retrieval, evidence, citation, or hidden-reasoning events. For example:

```json
{"timestamp":"2026-01-15T09:00:00+09:00","event_type":"process_switch","responsible_agent":"runner","process":"pre-write","decision":"Convert the assignment into a document plan.","evidence":[".writing/assignment.md"],"open_uncertainty":[],"from_process":null,"to_process":"pre-write","artifacts":[".writing/baselines/linear/pre-write.md"]}
```

The stage outputs are handoffs, not optional notes. The Write pass must receive all of the Pre-Write output, and the Re-Write pass must receive all of the Write output. Do not replace a stage with a direct final generation or add a review loop.
