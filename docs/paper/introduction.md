# Introduction

Artificial intelligence (AI) agents now support and produce writing in settings that include human-AI co-writing and long-form generation. Their writing processes, however, are often organized as task-specific workflows or fixed pipelines. Writing research offers a mature account of this problem. Flower and Hayes' Cognitive Process Theory of Writing[^1] describes a Monitor coordinating Planning, Translating, and Reviewing through an evolving goal network, in interaction with a task environment and long-term memory. We interpret this architecture as corresponding to modern agent systems, in which an orchestrating agent coordinates delegated roles over externalized project state. We realize that correspondence as an installable, inspectable writing agent. A controlled comparison tests whether the theory's recursive, goal-driven organization produces better machine writing than fixed-stage pipelines. Agent-trace analysis tests the theory's prediction about the role of middle-range goals.

The evaluation therefore uses two baselines that instantiate the fixed-stage organization Flower and Hayes' theory[^1] was formulated against. The linear Pre-Write/Write/Re-Write baseline passes through those three stages in order. The STORM-style baseline without retrieval proceeds through perspective discovery, simulated question answering, outlining, drafting, and polishing under the equal-information policy. STORM[^2] supplies the research-to-draft reference for this stage sequence.

The theory specifies how each process contributes to composing. Planning generates and organizes ideas and sets goals, Translating turns represented meanings into written language, and Reviewing evaluates and revises text or plans. The Monitor may embed these processes within one another, while the hierarchical goal network connects broad rhetorical aims to more operational sub-goals. Writers may regenerate higher-level goals as the developing text and new understanding change the rhetorical problem.

The implementation is an installable writing plugin whose adapters target two agentic coding platforms: Claude Code and OpenAI Codex. The system maps the Monitor, Planning, Translating, and Reviewing to executable roles and project state. It externalizes the assignment, goals, draft, memory, and plans in project files and maintains an append-only JSON Lines decision trace containing process switches, decisions, evidence, and unresolved questions. The process roles come from the 1981 theory. Their assignment to software files is our implementation interpretation.

The experiment evaluates process organization under equal information and fixed resource policies. We define a goal network as a hierarchy of writing goals that the Monitor coordinates during drafting and pose four research questions:

1. **RQ1.** Does the theory-based recursive Monitor and goal-network architecture produce better writing than a single-shot system and linear-stage pipelines?
2. **RQ2.** Which components matter? We compare the full plugin with the no-goal-network ablation and the fixed-order ablation.
3. **RQ3.** Do agent traces, treated as an operational analogue of a thinking-aloud protocol that records observable writing actions rather than private cognition, show the goal creation and regeneration dynamics described by Flower and Hayes[^1]? Flower and Hayes predict that "an important difference between good and poor writers will be in both the quantity and quality of the middle range of goals they create."[^1] The analysis tests whether these goals, which connect broad rhetorical aims to local writing actions, relate to writing quality.
4. **RQ4.** Does the mapping replicate across platforms?

Our contributions are fourfold:

1. We present an executable operationalization of a cognitive writing-process theory in which process selection, goal changes, and revision can be inspected.
2. We instantiate the same process mapping for both host platforms through host-specific manifests and adapters.
3. We treat externalized project state and an append-only decision trace as objects of process analysis alongside final text quality.
4. To our knowledge, among the systems surveyed in the supporting system survey (see Artifact availability), no system maps Flower and Hayes' roles[^1] onto an installable plugin.

**Artifact availability.** The repository provides the [plugin installation and adapter documentation](../../plugin/README.md), the [theory-to-artifact mapping](../../README.md), the [experiment protocol](../../docs/experiments/protocol.md), and the [supporting system survey](../../docs/research/skill-subagent-survey.md).

[^1]: Linda S. Flower and John R. Hayes, "A Cognitive Process Theory of Writing," *College Composition and Communication* 32, no. 4 (1981): 365-387. DOI: [10.58680/ccc198115885](https://doi.org/10.58680/ccc198115885).
[^2]: Yijia Shao, Yucheng Jiang, Theodore A. Kanell, Peter Xu, Omar Khattab, and Monica S. Lam, "Assisting in Writing Wikipedia-like Articles From Scratch with Large Language Models," *Proceedings of the 2024 Conference of the North American Chapter of the Association for Computational Linguistics: Human Language Technologies* (2024). DOI: [10.18653/v1/2024.naacl-long.347](https://doi.org/10.18653/v1/2024.naacl-long.347) / [arXiv](https://arxiv.org/abs/2402.14207).
