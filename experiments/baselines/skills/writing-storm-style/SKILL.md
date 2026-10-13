---
name: writing-storm-style
description: "Baseline STORM-style writing. Use a fixed perspective, simulated question-answering, outline, per-section draft, and polish sequence without retrieval or citation generation."
---

> [!NOTE]
> After reading this `SKILL.md`, say: `I read writing-storm-style.`
>
> Say the line in an assistant message of its own immediately after reading this skill. The line never appears in `.writing/draft.md` or in the final response.

# STORM[^1]-style writing

Run the STORM-style baseline in the fixed five-stage order:

`perspective discovery -> simulated question answering -> outline -> per-section draft -> polish`

The sequence adapts the released STORM[^1] pre-writing semantics to the experiment's equal-information policy. The perspective step identifies useful angles from the assignment and supplied context. The simulated question-answering step has a question-asker and an expert, but both roles can use only the supplied context. The outline step organizes those exchanges. The per-section draft expands the outline section by section. The polish step produces the final document.

## Equal-information and no-retrieval policy

The runner gives this condition the same assignment, supplied context, context-window policy, timeout, model settings, total output budget, and attempt budget as every comparison condition. The generator must not browse, search, call a retrieval tool, access the Internet, or use an unprovided source. The simulated expert must answer "not established by the supplied context" when the context does not support an answer. The question-asker must not use outside knowledge to manufacture a question premise.

Citation generation, retrieval, source gathering, evidence collection, and citation metrics are disabled. Retrieval, evidence, and citation traces are `N/A` by design, not zero. The runner records that policy in its run accounting rather than inventing trace events for work that did not occur.

The stages run in this session in the fixed order, and you perform every stage yourself, without subagents. You append each stage's trace event yourself with the trace recipe below.

## Procedure

1. Read the Assignment, Supplied context, and Requested output constraints sections of the prompt. Do not create `.writing/assignment.md`, do not create or modify `.writing/goals.md`, and do not create goal events.
2. Run one perspective-discovery pass. Save the discovered perspectives at `.writing/baselines/storm-style/perspectives.md`.
3. Run one simulated-question-answering pass. Play both the question-asker and the expert yourself; do not spawn subagents. Both use only the supplied context and must not retrieve information. Save the questions and answers at `.writing/baselines/storm-style/question-answering.md`.
4. Run one outline pass from the assignment, perspectives, and question-answering output. Save the outline at `.writing/baselines/storm-style/outline.md`.
5. Run one per-section-draft pass from the complete outline and the preceding supplied-context-only material. Draft every section yourself, without subagents; all section work belongs to this one stage. Save intermediate sections under `.writing/baselines/storm-style/sections/`.
6. Run one polish pass over the assembled section draft. Write the final document to `.writing/draft.md`.
7. Append exactly five schema-valid `process_switch` events, one for each stage entry: `null -> perspective-discovery`, `perspective-discovery -> simulated-question-answering`, `simulated-question-answering -> outline`, `outline -> per-section-draft`, and `per-section-draft -> polish`.

The trace contract is fixed at exactly five `process_switch` events, with `process` values `perspective-discovery`, `simulated-question-answering`, `outline`, `per-section-draft`, and `polish` in this order. Do not append retrieval, evidence, citation, goal, or hidden-reasoning events.

## Trace recipe

You append every trace event yourself, with this command and no other. Change only the first four lines: the stage's `process` token, the decision, the evidence list, and the open-uncertainty list. The command fills the timestamp and `from_process`, writes valid JSON, and appends nothing when a value is malformed.

```sh
python3 - <<'PY'
process = "perspective-discovery"
decision = "Identify useful perspectives from the assignment and supplied context."
evidence = [".writing/baselines/storm-style/perspectives.md"]
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

The five-stage mapping follows STORM[^1]'s separation of perspective-guided questioning, simulated conversation, outline creation, section-oriented writing, and polishing. The adaptation omits the released system's Internet research and citation behavior because those operations would violate the shared policy.

[^1]: Yijia Shao, Yucheng Jiang, Theodore Kanell, Peter Xu, Omar Khattab, and Monica Lam, "Assisting in Writing Wikipedia-like Articles From Scratch with Large Language Models," *Proceedings of the 2024 Conference of the North American Chapter of the Association for Computational Linguistics: Human Language Technologies* (NAACL 2024), 2024, https://doi.org/10.18653/v1/2024.naacl-long.347.
