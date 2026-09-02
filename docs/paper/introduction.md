# Introduction

Long-form large language model (LLM) writing requires systems to coordinate planning, drafting, and revision, but how these processes should be organized remains an open empirical question. A fixed-stage pipeline completes them in a predetermined sequence. A recursive architecture can instead revisit processes and goals as the text develops. We study whether this difference in process organization is associated with output quality and observable process behavior under a controlled comparison.

The comparison instantiates two fixed-stage baselines. A2 passes through Pre-Write, Write, and Re-Write, whereas A3 uses a STORM-style sequence of perspective discovery, simulated question answering, outlining, drafting, and polishing without retrieval under the equal-information policy. The comparison uses STORM[^2] as the research-to-draft reference for this stage sequence, while Flower and Hayes' theory[^1] was formulated in response to stage models of human composing. Neither baseline is treated as a universal description of LLM writing.

Flower and Hayes' Cognitive Process Theory of Writing[^1] treats composing as a goal-directed organization of thinking processes rather than a sequence of completed stages. Planning generates and organizes ideas and sets goals, Translating turns represented meanings into written language, and Reviewing evaluates and revises text or plans. A Monitor coordinates these processes, which may be embedded within one another, while a hierarchical network of goals connects broad rhetorical aims to more operational sub-goals. Writers may regenerate higher-level goals as the developing text and new understanding change the rhetorical problem.

We operationalize this account in an installable writing plugin for Claude Code and OpenAI Codex. The system maps the Monitor, Planning, Translating, and Reviewing to executable roles and project state. It externalizes the assignment, goals, draft, memory, and plans in project files and maintains an append-only JSON Lines decision trace containing process switches, decisions, evidence, and unresolved questions. This mapping is an implementation interpretation of the theory, not a claim that the 1981 paper specifies software files.

The experiment evaluates process organization under equal information and fixed resource policies. We define a goal network as a hierarchy of writing goals that the Monitor coordinates during drafting and pose four research questions:

1. **RQ1.** Does the theory-based recursive Monitor and goal-network architecture produce better writing than a single-shot system and linear-stage pipelines?
2. **RQ2.** Which components matter? We compare the full plugin with ablation conditions A5 and A6, which remove or constrain one component of the full design.
3. **RQ3.** Do agent traces, treated as an operational analogue of a thinking-aloud protocol that records observable writing actions rather than private cognition, show the goal creation and regeneration dynamics described by Flower and Hayes[^1]? Flower and Hayes predict that "an important difference between good and poor writers will be in both the quantity and quality of the middle range of goals they create."[^1] The analysis tests whether these goals, which connect broad rhetorical aims to local writing actions, relate to writing quality.
4. **RQ4.** Does the mapping replicate across platforms?

Our contributions are fourfold:

1. We present an executable operationalization of a cognitive writing-process theory in which process selection, goal changes, and revision can be inspected.
2. We instantiate the same process mapping for Claude Code and Codex through host-specific manifests and adapters.
3. We treat externalized project state and an append-only decision trace as objects of process analysis alongside final text quality.
4. To our knowledge, among the systems surveyed in the supporting system survey, no system maps Flower and Hayes' roles[^1] onto an installable plugin.

**Artifact availability.** The repository provides the [plugin installation and adapter documentation](../../plugin/README.md), the [theory-to-artifact mapping](../../README.md), the [experiment protocol](../../docs/experiments/protocol.md), and the [supporting system survey](../../docs/research/skill-subagent-survey.md).

[^1]: Linda S. Flower and John R. Hayes, "A Cognitive Process Theory of Writing," *College Composition and Communication* 32, no. 4 (1981): 365-387. DOI: [10.58680/ccc198115885](https://doi.org/10.58680/ccc198115885).
[^2]: Yijia Shao, Yucheng Jiang, Theodore A. Kanell, Peter Xu, Omar Khattab, and Monica S. Lam, "Assisting in Writing Wikipedia-like Articles From Scratch with Large Language Models," *Proceedings of the 2024 Conference of the North American Chapter of the Association for Computational Linguistics: Human Language Technologies* (2024). DOI: [10.18653/v1/2024.naacl-long.347](https://doi.org/10.18653/v1/2024.naacl-long.347) / [arXiv](https://arxiv.org/abs/2402.14207).
