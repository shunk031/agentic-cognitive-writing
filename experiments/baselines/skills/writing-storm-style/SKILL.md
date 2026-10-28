---
name: writing-storm-style
description: "Baseline STORM-style writing. Use a fixed perspective, simulated question-answering, outline, per-section draft, and polish sequence without retrieval or citation generation."
---

# STORM[^1]-style writing

Run the STORM-style baseline in the fixed five-stage order, each stage once, in this session; do not spawn an agent. The frozen stage prompts that follow this invocation give each stage's instructions.

`perspective discovery -> simulated question answering -> outline -> per-section draft -> polish`

The sequence adapts the released STORM[^1] pre-writing semantics to the experiment's equal-information policy. The perspective step identifies useful angles from the assignment and supplied context. The simulated question-answering step has a question-asker and an expert, but both roles can use only the supplied context. The outline step organizes those exchanges. The per-section draft expands the outline section by section. The polish step produces the final document.

## Equal-information and no-retrieval policy

The runner gives this condition the same assignment, supplied context, context-window policy, timeout, model settings, total output budget, and attempt budget as every comparison condition. The generator must not browse, search, call a retrieval tool, access the Internet, or use an unprovided source. The simulated expert must answer "not established by the supplied context" when the context does not support an answer. The question-asker must not use outside knowledge to manufacture a question premise.

Citation generation, retrieval, source gathering, evidence collection, and citation metrics are disabled. Retrieval, evidence, and citation traces are `N/A` by design, not zero. The runner records that policy in its run accounting rather than inventing trace events for work that did not occur.

The user owns rhetorical intent, factual authority, final wording, and publication. The skill fixes the stage schedule, and each stage owns its output.

## Procedure

1. Use the assignment, supplied context, and requested output constraints in this prompt. Do not create or modify `.writing/goals.md` and do not create goal events.
2. Run the perspective-discovery stage and write the discovered perspectives to `.writing/baselines/storm-style/perspectives.md`.
3. Run the simulated-question-answering stage. Play the question-asker and the expert in turn; both use only the supplied context. Write the questions and answers to `.writing/baselines/storm-style/question-answering.md`.
4. Run the outline stage from the assignment, perspectives, and question-answering output, and write the outline to `.writing/baselines/storm-style/outline.md`.
5. Run the per-section-draft stage from the complete outline and the preceding material, drafting one section at a time, and write the sections under `.writing/baselines/storm-style/sections/`.
6. Run the polish stage over the assembled section draft and write the polished document to `.writing/draft.md`. `.writing/draft.md` is the final document.

The five-stage mapping follows STORM[^1]'s separation of perspective-guided questioning, simulated conversation, outline creation, section-oriented writing, and polishing. The adaptation omits the released system's Internet research and citation behavior because those operations would violate the shared policy.

[^1]: Yijia Shao, Yucheng Jiang, Theodore Kanell, Peter Xu, Omar Khattab, and Monica Lam, "Assisting in Writing Wikipedia-like Articles From Scratch with Large Language Models," *Proceedings of the 2024 Conference of the North American Chapter of the Association for Computational Linguistics: Human Language Technologies* (NAACL 2024), 2024, https://doi.org/10.18653/v1/2024.naacl-long.347.
