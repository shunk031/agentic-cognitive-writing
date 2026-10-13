---
name: writing-self-refine
description: "Experiment condition A10. Write one draft, then run a fixed number of Feedback and Refine rounds on it in one session, following Self-Refine. Use only for the controlled budget-matched Self-Refine comparison."
---

> [!NOTE]
> After reading this `SKILL.md`, say: `I read writing-self-refine.`
>
> Say the line in an assistant message of its own immediately after reading this skill. The line never appears in `.writing/draft.md` or in the final response.

# Self-Refine writing

Run condition A10 as one Draft pass followed by a fixed number of Feedback and Refine rounds, following Self-Refine (Madaan et al., 2023). The same generator writes the draft, gives feedback on its own current draft, and refines the draft using that feedback. The frozen stage list in the prompt fixes the number of rounds; run every listed stage once, in order, and never stop early or add a round.

## Equal-information and no-retrieval policy

The runner gives this condition the same assignment, supplied context, context-window policy, timeout, model settings, total output budget, and attempt budget as every comparison condition. The generator may use only `.writing/assignment.md`, the supplied context, and the earlier stage outputs in this session. The generator must not browse, search, call a retrieval tool, use an external source, or spawn subagents. When the supplied context does not support a claim, preserve the uncertainty or omit the claim.

The runner owns stage scheduling and trace recording. The generator owns each stage output. The runner must not infer hidden reasoning from stage text.

## Procedure

1. Read `.writing/assignment.md` and the supplied context. Do not create or modify `.writing/goals.md` and do not create goal events.
2. Run the `Draft` stage. Store the draft at `.writing/baselines/self-refine/draft.md` and append the first `process_switch` event for `null -> draft`.
3. For round `n` from 1 to the number of rounds in the stage list:
   1. Run the `Feedback` stage on the current draft. Store the feedback at `.writing/baselines/self-refine/feedback-n.md` and append the event for `draft -> feedback` in round 1 or `refine -> feedback` in later rounds.
   2. Run the `Refine` stage on the current draft and that feedback. Store the refined draft at `.writing/baselines/self-refine/refine-n.md`, make it the current draft, and append the event for `feedback -> refine`.
4. Write the last refined draft to `.writing/draft.md` and return it as the final response.

Before sending the final response, write the final document to `.writing/draft.md`. The run is `INVALID` unless `.writing/draft.md` exists before the final response and the final response contains the complete final text. The final response cannot substitute for the required draft.

The trace contract is one `process_switch` event per stage, in stage order. Every event's `process` must be one of `draft`, `feedback`, or `refine`. Append every event to `.writing/trace/process.jsonl`. Each event is a `process_switch` object with `timestamp`, `event_type`, `responsible_agent`, `process`, `decision`, `evidence`, `open_uncertainty`, `from_process`, and `to_process`, plus `artifacts` for stage files. In the JSON object, `timestamp`, `event_type`, `responsible_agent`, `process`, and `decision` are strings; `evidence` and `open_uncertainty` are arrays of strings; `from_process` and `to_process` are strings or `null`; and `artifacts` is an array of project-relative path strings; set `timestamp` to the current wall-clock time obtained from the shell at write time, for example `date -Is`, and never copy example timestamps. Use `responsible_agent: "runner"`, set `process` equal to `to_process`, and add stage artifacts to `artifacts`. Do not append goal, retrieval, evidence, citation, or hidden-reasoning events. For example:

```json
{
  "timestamp": "2026-01-15T09:00:00+09:00",
  "event_type": "process_switch",
  "responsible_agent": "runner",
  "process": "feedback",
  "decision": "Give round 1 feedback on the draft.",
  "evidence": [".writing/baselines/self-refine/draft.md"],
  "open_uncertainty": [],
  "from_process": "draft",
  "to_process": "feedback",
  "artifacts": [".writing/baselines/self-refine/feedback-1.md"]
}
```

The stage outputs are handoffs, not optional notes. Each Feedback stage must read the complete current draft, and each Refine stage must read the complete current draft and the complete feedback from the same round.
