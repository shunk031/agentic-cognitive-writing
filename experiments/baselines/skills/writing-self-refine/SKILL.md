---
name: writing-self-refine
description: "Experiment condition A10. Write one draft, then run a fixed number of Feedback and Refine rounds on it in one session, following Self-Refine. Use only for the controlled budget-matched Self-Refine comparison."
---

> [!NOTE]
> After reading this `SKILL.md`, say: `I read writing-self-refine.`
>
> Say the line immediately after reading this skill, in the same response as your next tool call. The line never appears in `.writing/draft.md` or in the final response.

# Self-Refine writing

Run condition A10 as one Draft pass followed by a fixed number of Feedback and Refine rounds, following Self-Refine (Madaan et al., 2023). The same generator writes the draft, gives feedback on its own current draft, and refines the draft using that feedback. The frozen stage list in the prompt fixes the number of rounds; run every listed stage once, in order, and never stop early or add a round.

## Equal-information and no-retrieval policy

The runner gives this condition the same assignment, supplied context, context-window policy, timeout, model settings, total output budget, and attempt budget as every comparison condition. The generator may use only the Assignment, Supplied context, and Requested output constraints sections of the prompt and the earlier stage outputs in this session. The generator must not browse, search, call a retrieval tool, use an external source, or spawn subagents. When the supplied context does not support a claim, preserve the uncertainty or omit the claim.

The stages run in this session in the order the prompt lists them, and the generator owns each stage output. You append each stage's trace event yourself with the trace recipe below.

## Procedure

1. Read the Assignment, Supplied context, and Requested output constraints sections of the prompt. Do not create `.writing/assignment.md`, do not create or modify `.writing/goals.md`, and do not create goal events.
2. Append the `draft` event with the trace recipe, then run the `Draft` stage. Store the draft at `.writing/baselines/self-refine/draft.md`.
3. For round `n` from 1 to the number of rounds in the stage list:
   1. Append the `feedback` event, then run the `Feedback` stage on the current draft. Store the feedback at `.writing/baselines/self-refine/feedback-n.md`.
   2. Append the `refine` event, then run the `Refine` stage on the current draft and that feedback. Store the refined draft at `.writing/baselines/self-refine/refine-n.md` and make it the current draft.
4. Write the last refined draft to `.writing/draft.md` and return exactly its contents as the final response, with nothing before or after it.

Before sending the final response, write the final document to `.writing/draft.md`. The run is `INVALID` unless `.writing/draft.md` exists before the final response and the final response contains the complete final text. The final response cannot substitute for the required draft.

The trace contract is one `process_switch` event per stage, in stage order, with `process` values `draft`, `feedback`, and `refine`. Do not append goal, retrieval, evidence, citation, or hidden-reasoning events.

## Trace recipe

You append every trace event yourself, with this command and no other. Run it once per stage, immediately when that stage starts, never afterwards and never from a loop or script that writes several events. Change only the first four lines: the `process` token, the decision, the evidence list, and the open-uncertainty list. The command checks the process token and the field types, fills the timestamp and `from_process`, writes valid JSON, and appends nothing when a value is invalid.

```sh
python3 - <<'PY'
process = "draft"
decision = "Write the first complete draft."
evidence = [".writing/baselines/self-refine/draft.md"]
open_uncertainty = []
allowed = ("draft", "feedback", "refine")
import datetime, json, pathlib, sys
if process not in allowed or not isinstance(decision, str) or not decision.strip() or not all(isinstance(v, list) and all(isinstance(x, str) for x in v) for v in (evidence, open_uncertainty)):
    sys.exit("invalid trace event; nothing was appended")
trace = pathlib.Path(".writing/trace/process.jsonl")
trace.parent.mkdir(parents=True, exist_ok=True)
lines = [json.loads(line) for line in trace.read_text(encoding="utf-8").splitlines() if line.strip()] if trace.exists() else []
event = {"timestamp": datetime.datetime.now().astimezone().isoformat(timespec="seconds"), "event_type": "process_switch", "responsible_agent": "runner", "process": process, "from_process": lines[-1]["to_process"] if lines else None, "to_process": process, "decision": decision, "evidence": evidence, "open_uncertainty": open_uncertainty}
with trace.open("a", encoding="utf-8") as handle:
    handle.write(json.dumps(event, ensure_ascii=False) + "\n")
PY
```

The stage outputs are handoffs, not optional notes. Each Feedback stage must read the complete current draft, and each Refine stage must read the complete current draft and the complete feedback from the same round.
