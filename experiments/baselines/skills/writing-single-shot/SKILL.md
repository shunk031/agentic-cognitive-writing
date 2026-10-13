---
name: writing-single-shot
description: "Experiment condition A1. Generate the complete document in one pass from the assignment and supplied context, with no planning or review stage. Use only for the controlled single-shot comparison."
---

> [!NOTE]
> After reading this `SKILL.md`, say: `I read writing-single-shot.`
>
> Say the line in an assistant message of its own immediately after reading this skill. The line never appears in `.writing/draft.md` or in the final response.

# Single-shot writing

Run condition A1 as one generation pass. The generator writes the complete document from the Assignment, Supplied context, and Requested output constraints sections of the prompt. The generator does not create a plan, ask a planning subagent, run a reviewer, or perform a second generation pass.

## Equal-information and no-retrieval policy

The runner gives this condition the same assignment, supplied context, context-window policy, timeout, model settings, output budget, and attempt budget as every comparison condition. The generator may read the assignment and supplied context, but it must not browse, search, call a retrieval tool, use an external source, or infer evidence that the supplied context does not provide. If the context does not establish a claim, preserve the uncertainty or omit the claim.

The generator owns the single completion pass and appends the one trace event itself.

## Procedure

1. Read the Assignment, Supplied context, and Requested output constraints sections of the prompt. Do not create `.writing/assignment.md`, and do not create or modify `.writing/goals.md`, planning notes, review notes, or memory files for this condition.
2. Generate the complete final document in one pass. Keep the requested audience, genre, structure, length, and other constraints visible in the prompt.
3. Return the complete final document in the final response. Do not write `.writing/draft.md` or another draft file.
4. Append exactly one `process_switch` event with `process` `generate` to `.writing/trace/process.jsonl`, using the trace recipe below.

The trace contract is fixed at exactly one `process_switch` event, whose only allowed `process` value is `generate`. List unresolved claims in its open-uncertainty list. Do not append goal events or invent internal reasoning.

## Trace recipe

You append every trace event yourself, with this command and no other. Change only the first four lines: the stage's `process` token, the decision, the evidence list, and the open-uncertainty list. The command fills the timestamp and `from_process`, writes valid JSON, and appends nothing when a value is malformed.

```sh
python3 - <<'PY'
process = "generate"
decision = "Generate the complete document in one pass from the assignment and supplied context."
evidence = ["assignment and supplied context in the prompt"]
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

Do not add another trace line for a retry, formatting step, or hidden decision. A failed run is accounted for by the runner; the skill must not turn failure handling into an unplanned stage.
