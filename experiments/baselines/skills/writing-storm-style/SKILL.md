---
name: writing-storm-style
description: "Experiment condition A3. Use a fixed STORM-style perspective, simulated question-answering, outline, per-section draft, and polish sequence without retrieval or citation generation."
---

# STORM-style writing

Run condition A3 in the fixed five-stage order:

`perspective discovery -> simulated question answering -> outline -> per-section draft -> polish`

The sequence adapts the released STORM pre-writing semantics to the experiment's equal-information policy. The perspective step identifies useful angles from the assignment and supplied context. The simulated question-answering step has a question-asker and an expert, but both roles can use only the supplied context. The outline step organizes those exchanges. The per-section draft expands the outline section by section. The polish step produces the final document.

## Equal-information and no-retrieval policy

The runner gives this condition the same assignment, supplied context, context-window policy, timeout, model settings, total output budget, and attempt budget as every comparison condition. The generator must not browse, search, call a retrieval tool, access the Internet, or use an unprovided source. The simulated expert must answer "not established by the supplied context" when the context does not support an answer. The question-asker must not use outside knowledge to manufacture a question premise.

Citation generation, retrieval, source gathering, evidence collection, and citation metrics are disabled. Retrieval, evidence, and citation traces are `N/A` by design, not zero. The runner records that policy in its run accounting rather than inventing trace events for work that did not occur.

The user owns rhetorical intent, factual authority, final wording, and publication. The runner owns the fixed stage schedule and trace recording. Stage actors own the stage outputs. The runner must not infer hidden reasoning or sources from the prose.

## Procedure

1. Read `.writing/assignment.md` and the supplied context. Leave `.writing/goals.md` untouched and do not create goal events.
2. Run one perspective-discovery pass. Save the discovered perspectives at `.writing/baselines/storm-style/perspectives.md` or the runner-designated equivalent.
3. Run one simulated-question-answering pass. The question-asker and expert may be separate subagents, but both receive the same supplied context and must not retrieve information. Save the questions and answers at `.writing/baselines/storm-style/question-answering.md`.
4. Run one outline pass from the assignment, perspectives, and question-answering output. Save the outline at `.writing/baselines/storm-style/outline.md`.
5. Run one per-section-draft pass from the complete outline and the preceding supplied-context-only material. A section worker may draft one section, but all section work belongs to this one stage. Save intermediate sections under `.writing/baselines/storm-style/sections/`.
6. Run one polish pass over the assembled section draft. Write the final document to `.writing/draft.md`.
7. Append exactly five schema-valid `process_switch` events, one for each stage entry: `null -> perspective-discovery`, `perspective-discovery -> simulated-question-answering`, `simulated-question-answering -> outline`, `outline -> per-section-draft`, and `per-section-draft -> polish`.

Append every event to `.writing/trace/process.jsonl`. Each event includes `timestamp`, `event_type`, `responsible_agent`, `process`, `decision`, `evidence`, `open_uncertainty`, `from_process`, and `to_process`. Use `responsible_agent: "runner"`, cite the preceding inputs and current stage artifact in `evidence`, preserve unknowns in `open_uncertainty`, and list project-relative files in `artifacts`. The trace must contain exactly five stage events for a successful run. Do not append retrieval, evidence, citation, goal, or hidden-reasoning events.

The five-stage mapping follows STORM's separation of perspective-guided questioning, simulated conversation, outline creation, section-oriented writing, and polishing. The adaptation omits the released system's Internet research and citation behavior because those operations would violate the shared policy.
