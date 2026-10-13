---
name: writing-linear
description: "Experiment baseline with one fixed Pre-Write, Write, and Re-Write pass, handing each output to the next under a common output budget. Use only for the controlled linear comparison."
---

> [!NOTE]
> After reading this `SKILL.md`, say: `I read writing-linear.`
>
> Say the line in an assistant message of its own immediately after reading this skill. The line never appears in `.writing/draft.md` or in the final response.

# Linear writing

Run the fixed order `Pre-Write -> Write -> Re-Write`. Each stage runs once. The output from one stage is the only process artifact handed to the next stage, together with the unchanged assignment and supplied context. The Re-Write output is the final document.

## Equal-information and no-retrieval policy

The runner gives this condition the same assignment, supplied context, context-window policy, timeout, model settings, total output budget, and attempt budget as every comparison condition.

The generator may use only the Assignment, Supplied context, and Requested output constraints sections of the prompt and the prior stage output. The generator must not browse, search, call a retrieval tool, or use an external source. Retrieval, evidence gathering, and citation generation are disabled. When the supplied context does not support a claim, preserve the uncertainty or omit the claim.

The stages run in this session in the order the prompt lists them, and each stage generator owns its output. You append each stage's trace event yourself with the trace recipe below.

## Procedure

1. Read the Assignment, Supplied context, and Requested output constraints sections of the prompt. Do not create `.writing/assignment.md`, do not create or modify `.writing/goals.md`, and do not create goal events.
2. Run one `Pre-Write` pass that converts the assignment into a compact document plan, requirements checklist, and section intent. Store its output at `.writing/baselines/linear/pre-write.md`.
3. Append the first schema-valid `process_switch` event for `null -> pre-write`, naming the runner as the responsible actor and citing the assignment and pre-write handoff.
4. Run one `Write` pass using the assignment, supplied context, and complete Pre-Write output. Store the draft at `.writing/baselines/linear/write.md`.
5. Append the second event for `pre-write -> write`, citing both stage artifacts.
6. Run one `Re-Write` pass using the assignment, supplied context, and complete Write output. Store the final document at `.writing/draft.md`.
7. Append the third event for `write -> re-write`, citing the Write output and final draft.

Before sending the final response, write the final document to `.writing/draft.md`. The run is `INVALID` unless `.writing/draft.md` exists before the final response and the final response contains the complete final text. The final response cannot substitute for the required draft.

The trace contract is fixed at exactly three `process_switch` events, with `process` values `pre-write`, `write`, and `re-write` in this order. Do not append goal, retrieval, evidence, citation, or hidden-reasoning events.

## Trace recipe

You append every trace event yourself, with this command and no other. Change only the first four lines: the stage's `process` token, the decision, the evidence list, and the open-uncertainty list. The command fills the timestamp and `from_process`, writes valid JSON, and appends nothing when a value is malformed.

```sh
python3 - <<'PY'
process = "pre-write"
decision = "Convert the assignment into a document plan."
evidence = [".writing/baselines/linear/pre-write.md"]
open_uncertainty = []
import datetime, json, pathlib
trace = pathlib.Path(".writing/trace/process.jsonl")
trace.parent.mkdir(parents=True, exist_ok=True)
lines = [json.loads(line) for line in trace.read_text(encoding="utf-8").splitlines() if line.strip()] if trace.exists() else []
event = {"timestamp": datetime.datetime.now().astimezone().isoformat(timespec="seconds"), "event_type": "process_switch", "responsible_agent": "runner", "process": process, "from_process": lines[-1]["to_process"] if lines else None, "to_process": process, "decision": decision, "evidence": evidence, "open_uncertainty": open_uncertainty}
with trace.open("a", encoding="utf-8") as handle:
    handle.write(json.dumps(event, ensure_ascii=False) + "\n")
PY
```

The stage outputs are handoffs, not optional notes. The Write pass must receive all of the Pre-Write output, and the Re-Write pass must receive all of the Write output. Do not replace a stage with a direct final generation or add a review loop.
